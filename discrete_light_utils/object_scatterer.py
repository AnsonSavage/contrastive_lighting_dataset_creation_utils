import bpy
import random
import math
from mathutils import Vector, Euler

from utils.random_utils import get_random_point_on_surface


class ObjectScatterer:
    """Handles random placement and rotation of objects on a surface."""
    
    def __init__(self, scatter_plane_name: str = "scatter_plane", seed: int = None, min_distance: float = 1.5):
        self.scatter_plane_name = scatter_plane_name
        self.seed = seed
        self.min_distance = min_distance
        self.placed_positions: list[Vector] = []
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
    
    def scatter_and_rotate(self, obj: bpy.types.Object) -> None:
        """Places object at a random point on the scatter plane and applies random Z rotation."""
        if not obj:
            print("Warning: No object provided to scatter.")
            return
        
        # Get scatter plane
        plane = bpy.data.objects.get(self.scatter_plane_name)
        if not plane:
            print(f"Warning: Scatter plane '{self.scatter_plane_name}' not found. Using random area.")
        
        # Get position with spacing
        random_point = self._get_random_point_with_spacing(plane)
        
        # Set location
        obj.location = random_point
        self.placed_positions.append(random_point.copy())
        
        # Apply random Z rotation
        rand_angle = self.rng.uniform(0, 2 * math.pi)
        
        if obj.rotation_mode == 'XYZ':
            obj.rotation_euler.z = rand_angle
        elif obj.rotation_mode == 'QUATERNION':
            quat_rot = Euler((0, 0, rand_angle), 'XYZ').to_quaternion()
            obj.rotation_quaternion = quat_rot @ obj.rotation_quaternion
        else:
            # Fallback to Euler
            obj.rotation_mode = 'XYZ'
            obj.rotation_euler.z = rand_angle
    
    def scatter_multiple(self, objects: list) -> None:
        """Scatter multiple objects, ensuring minimum distance between them."""
        for obj in objects:
            self.scatter_and_rotate(obj)
    
    def reset_positions(self):
        """Clear the list of placed positions."""
        self.placed_positions.clear()
    
    def set_seed(self, new_seed: int):
        """Update the random seed."""
        self.seed = new_seed
        self.rng = random.Random(new_seed)
