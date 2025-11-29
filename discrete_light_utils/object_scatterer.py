import bpy
import random
import math
from mathutils import Vector, Euler

from utils.random_utils import get_random_point_on_surface
from utils.bbox_utils import get_bbox_extrema, bboxes_intersect


class ObjectScatterer:
    """Handles random placement and rotation of objects on a surface."""
    
    def __init__(self, scatter_plane_name: str = "scatter_plane", seed: int = None, min_distance: float = 1.5):
        self.scatter_plane_name = scatter_plane_name
        self.seed = seed
        self.min_distance = min_distance
        self.placed_positions: list[Vector] = []
        self.placed_objects: list[bpy.types.Object] = []
        if seed is not None:
            self.rng = random.Random(seed)
        else:
            self.rng = random
    
    def _is_valid_position(self, pos: Vector) -> bool:
        """Check if a position is far enough from all previously placed objects."""
        for placed_pos in self.placed_positions:
            dist = (pos - placed_pos).length
            if dist < self.min_distance:
                return False
        return True
    
    def _would_intersect_placed_objects(self, obj: bpy.types.Object, new_position: Vector) -> bool:
        """
        Check if placing obj at new_position would cause its bbox to intersect
        with any already-placed objects' bboxes.
        """
        if not self.placed_objects:
            return False
        
        # Save original location
        original_location = obj.location.copy()
        obj.location = new_position
        bpy.context.view_layer.update()
        
        # Get the bbox of the object at the new position
        try:
            obj_min, obj_max = get_bbox_extrema(obj)
        except Exception:
            obj.location = original_location
            return False
        
        # Restore original location
        obj.location = original_location
        
        # Check against all placed objects
        for placed_obj in self.placed_objects:
            if placed_obj is None or not placed_obj.name:
                continue
            try:
                placed_min, placed_max = get_bbox_extrema(placed_obj)
                if bboxes_intersect(obj_min, obj_max, placed_min, placed_max):
                    return True
            except Exception:
                continue
        
        return False
    
    def _get_random_point_with_spacing(self, plane, max_attempts: int = 50) -> Vector:
        """Get a random point that respects minimum distance from other objects."""
        for _ in range(max_attempts):
            if plane:
                random_point = get_random_point_on_surface(plane)
            else:
                # Fallback: random point in a 10x10 area
                random_point = Vector((
                    self.rng.uniform(-5, 5),
                    self.rng.uniform(-5, 5),
                    0
                ))
            
            if self._is_valid_position(random_point):
                return random_point
        
        # If we couldn't find a valid position, just return the last attempt
        print(f"Warning: Could not find position with min_distance={self.min_distance} after {max_attempts} attempts.")
        return random_point
    
    def scatter_and_rotate(self, obj: bpy.types.Object, check_bbox_intersection: bool = True, max_attempts: int = 50) -> bool:
        """
        Places object at a random point on the scatter plane and applies random Z rotation.
        
        Args:
            obj: The object to scatter
            check_bbox_intersection: If True, checks for bbox collision and tries multiple attempts
            max_attempts: Maximum number of placement attempts when checking bbox intersection
            
        Returns:
            True if placement succeeded, False if all attempts failed (only relevant when check_bbox_intersection=True)
        """
        if not obj:
            print("Warning: No object provided to scatter.")
            return False
        
        # Get scatter plane
        plane = bpy.data.objects.get(self.scatter_plane_name)
        if not plane:
            print(f"Warning: Scatter plane '{self.scatter_plane_name}' not found. Using random area.")
        
        # Try multiple placements
        for attempt in range(max_attempts):
            # Get a candidate position
            if plane:
                candidate_pos = get_random_point_on_surface(plane)
            else:
                candidate_pos = Vector((
                    self.rng.uniform(-5, 5),
                    self.rng.uniform(-5, 5),
                    0
                ))
            
            # Check minimum distance constraint
            if not self._is_valid_position(candidate_pos):
                continue
            
            # Check bbox intersection if requested
            if check_bbox_intersection and self._would_intersect_placed_objects(obj, candidate_pos):
                continue
            
            # Valid position found - place the object
            obj.location = candidate_pos
            self.placed_positions.append(candidate_pos.copy())
            self.placed_objects.append(obj)
            
            # Apply random Z rotation
            rand_angle = self.rng.uniform(0, 2 * math.pi)
            if obj.rotation_mode == 'XYZ':
                obj.rotation_euler.z = rand_angle
            elif obj.rotation_mode == 'QUATERNION':
                quat_rot = Euler((0, 0, rand_angle), 'XYZ').to_quaternion()
                obj.rotation_quaternion = quat_rot @ obj.rotation_quaternion
            else:
                obj.rotation_mode = 'XYZ'
                obj.rotation_euler.z = rand_angle
            
            bpy.context.view_layer.update()
            return True
        
        print(f"Warning: Could not find valid position for object after {max_attempts} attempts.")
        return False
    
    def scatter_multiple(self, objects: list) -> None:
        """Scatter multiple objects, ensuring minimum distance between them."""
        for obj in objects:
            self.scatter_and_rotate(obj)
    
    def reset_positions(self):
        """Clear the list of placed positions and objects."""
        self.placed_positions.clear()
        self.placed_objects.clear()
    
    def register_placed_object(self, obj: bpy.types.Object) -> None:
        """Register an object as placed (for bbox collision checking)."""
        if obj and obj not in self.placed_objects:
            self.placed_objects.append(obj)
            self.placed_positions.append(obj.location.copy())
    
    def set_seed(self, new_seed: int):
        """Update the random seed."""
        self.seed = new_seed
        self.rng = random.Random(new_seed)
