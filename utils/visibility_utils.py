import bpy
import math
from abc import ABC, abstractmethod
from mathutils import Vector
from random_utils import get_random_point_on_surface

def is_point_inside_mesh(obj, point_world) -> bool:
    """
    Determines if a given point in world space is inside the volume of the specified mesh object.

    Args:
        obj (bpy.types.Object): The mesh object to test against.
        point_world (mathutils.Vector): The point in world space to test.

    Returns:
        bool: True if the point is inside the mesh, False otherwise.
    """
    assert obj.type == 'MESH' and obj.data is not None, "Object must be a mesh with valid data."

    # Define ray direction in world space
    ray_direction = Vector((1, 0, 0)) # We can choose any arbitrary direction

    current_point_local = obj.matrix_world.inverted() @ point_world

    intersections = 0
    while True:
        # Cast in local space using the object's own ray_cast
        hit, location_local, normal_local, index = obj.ray_cast(current_point_local, ray_direction)

        if not hit:
            # No more hits along this ray in local space
            break

        intersections += 1
        # Advance slightly in local space to continue the ray
        current_point_local = location_local + ray_direction * 0.0001

    if intersections % 2 == 1:
        # Return the original world-space point
        return True
    return False

class VisibilityStrategy(ABC):
    def __init__(self, scene, depsgraph, target_obj):
        self.scene = scene
        self.depsgraph = depsgraph
        self.target_obj = target_obj

    def check(self, origin) -> bool:
        """Template method for checking visibility."""
        
        # 1. Optimization: Check center first
        # If the center is visible, we may be able to exit early.
        if self._is_satisfied_by_center():
            if self._check_center(origin):
                return True
        
        # 2. Determine how many samples we need
        total_samples = self._get_sample_count()
        
        # 3. Get points to test (batch sampling for efficiency)
        points = self._get_sample_points(total_samples)
        
        visible_samples = 0
        for i, point in enumerate(points):
            # 4. Raycast
            if self._raycast(origin, point):
                visible_samples += 1
                # 5. Early Exit Success
                if self._check_early_success(visible_samples, i + 1, total_samples):
                    return True
            else:
                # 6. Early Exit Failure
                if self._check_early_fail(visible_samples, i + 1, total_samples):
                    return False
                    
        # 7. Final Decision
        return self._finalize(visible_samples, total_samples)

    def _check_center(self, origin):
        center = self.target_obj.matrix_world.translation
        return self._raycast(origin, center)

    def _raycast(self, origin, target_point):
        direction = target_point - origin
        dist = direction.length
        if dist < 1e-4: 
            return True
            
        # Raycast with slight bias to avoid self-intersection at the target surface
        success, location, normal, index, object, matrix = self.scene.ray_cast(
            self.depsgraph, origin, direction.normalized(), distance=dist + 0.001
        )
        
        # We consider it visible if we hit the target object
        return success and object == self.target_obj

    @abstractmethod
    def _is_satisfied_by_center(self) -> bool: pass

    @abstractmethod
    def _get_sample_count(self) -> int: pass

    @abstractmethod
    def _get_sample_points(self, count) -> list[Vector]: pass

    @abstractmethod
    def _check_early_success(self, hits, processed, total) -> bool: pass

    @abstractmethod
    def _check_early_fail(self, hits, processed, total) -> bool: pass

    @abstractmethod
    def _finalize(self, hits, total) -> bool: pass


class AnyVisibilityStrategy(VisibilityStrategy):
    """Returns True if ANY part of the object is visible."""
    
    def _is_satisfied_by_center(self) -> bool:
        return True

    def _get_sample_count(self) -> int:
        # Heuristic: check a fixed number of random points if center is occluded
        return 20

    def _get_sample_points(self, count) -> list[Vector]:
        # get_random_point_on_surface returns a list if num_points > 1
        points = get_random_point_on_surface(self.target_obj, num_points=count)
        if not isinstance(points, list):
            points = [points] if points else []
        return points

    def _check_early_success(self, hits, processed, total) -> bool:
        return hits > 0

    def _check_early_fail(self, hits, processed, total) -> bool:
        return False

    def _finalize(self, hits, total) -> bool:
        return hits > 0


class PercentageVisibilityStrategy(VisibilityStrategy):
    """Returns True if a specific percentage of the object is visible."""
    
    def __init__(self, scene, depsgraph, target_obj, min_percentage, confidence_level):
        super().__init__(scene, depsgraph, target_obj)
        self.min_percentage = min_percentage
        if confidence_level is None:
            confidence_level = 0.8
        self.confidence_level = confidence_level

    def _is_satisfied_by_center(self) -> bool:
        # Seeing the center is not enough to prove percentage
        return False

    def _get_sample_count(self) -> int:
        # Calculate sample size based on confidence level
        # Formula: n = (Z^2 * p * (1-p)) / E^2
        # p = 0.5 (worst case variance)
        # E = 0.10 (10% margin of error)
        
        z_map = {
            0.70: 1.04,
            0.80: 1.28,
            0.90: 1.645,
            0.95: 1.96,
            0.99: 2.576
        }
        # Default to 1.04 (70%) if exact key not found, or use closest logic
        z = z_map.get(self.confidence_level, 1.04) 
        
        margin_of_error = 0.10
        p = 0.5
        
        n = (z**2 * p * (1 - p)) / (margin_of_error**2)
        return max(10, math.ceil(n)) # Ensure at least some samples

    def _get_sample_points(self, count) -> list[Vector]:
        points = get_random_point_on_surface(self.target_obj, num_points=count)
        if not isinstance(points, list):
            points = [points] if points else []
        return points

    def _check_early_success(self, hits, processed, total) -> bool:
        # If we have already hit enough to satisfy the percentage
        return (hits / total) >= self.min_percentage

    def _check_early_fail(self, hits, processed, total) -> bool:
        # If even if all remaining samples are hits, we can't reach the percentage
        remaining = total - processed
        max_possible_hits = hits + remaining
        return (max_possible_hits / total) < self.min_percentage

    def _finalize(self, hits, total) -> bool:
        return (hits / total) >= self.min_percentage


def check_visibility(origin, target_obj, pre_update_view_layer=True, minimum_percentage_of_surface_visible=None, confidence_level=None):
    if pre_update_view_layer:
        bpy.context.view_layer.update()
    
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    
    if minimum_percentage_of_surface_visible is None:
        assert confidence_level is None, "Confidence level should be None when using AnyVisibilityStrategy."
        strategy = AnyVisibilityStrategy(scene, depsgraph, target_obj)
    else:
        strategy = PercentageVisibilityStrategy(
            scene, depsgraph, target_obj, 
            minimum_percentage_of_surface_visible, 
            confidence_level
        )
        
    return strategy.check(origin)
