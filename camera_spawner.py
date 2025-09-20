import bpy
import mathutils
import random
from random_utils import get_random_point_in_mesh

class CameraSpawner:
    def __init__(self, look_from_volume_name, look_at_volume_name, camera_name):
        self.look_at_volume = bpy.data.objects.get(look_at_volume_name)
        assert self.look_at_volume is not None, f"Look at volume '{look_at_volume_name}' not found in the scene."
        self.look_from_volume = bpy.data.objects.get(look_from_volume_name)
        assert self.look_from_volume is not None, f"Look from volume '{look_from_volume_name}' not found in the scene."
        self.camera_name = camera_name

    def update(self, update_seed, pass_criteria = None):
        assert update_seed is not None, "Seed must be provided."
        # Initialize a deterministic RNG for this update call
        rng = random.Random(update_seed)
        has_good_sample = False
        max_attempts = 3000
        attempts = 0
        while not has_good_sample and attempts < max_attempts:
            # Generate seeds deterministically from the per-update RNG
            attempts += 1
            look_at_seed = rng.getrandbits(64)
            look_at = get_random_point_in_mesh(self.look_at_volume, seed=look_at_seed)
            if look_at is None:
                continue
            look_from_seed = rng.getrandbits(64)
            look_from = get_random_point_in_mesh(self.look_from_volume, seed=look_from_seed)
            if look_from is None:
                continue
            if pass_criteria is not None:
                has_good_sample = pass_criteria(look_from, look_at)
            else:
                has_good_sample = True

        if not has_good_sample:
            print(f"Failed to find valid camera positions after {max_attempts} attempts.")
            return

        camera = bpy.data.objects.get(self.camera_name)
        assert camera is not None, f"Camera '{self.camera_name}' not found in the scene."
        
        look_at_matrix = self.compute_look_at_matrix(look_from, look_at)
        
        camera.matrix_world = look_at_matrix
        
        print(f"Camera '{self.camera_name}' moved to coordinate: {look_from}")
        print(f"Camera '{self.camera_name}' now looking at: {look_at}")

    def compute_look_at_matrix(self, camera_position: mathutils.Vector, target_position: mathutils.Vector):
        """
        Computes a look-at transformation matrix for a camera.
        Args:
            camera_position (mathutils.Vector): The position of the camera.
            target_position (mathutils.Vector): The position the camera is looking at.
        Returns:
            mathutils.Matrix: The look-at transformation matrix.
        """
        camera_direction = (target_position - camera_position).normalized()

        up = mathutils.Vector((0, 0, 1))
        camera_right = camera_direction.cross(up).normalized()
        
        camera_up = camera_right.cross(camera_direction).normalized()

        rotation_transform = mathutils.Matrix([camera_right, camera_up, -camera_direction]).transposed().to_4x4()

        translation_transform = mathutils.Matrix.Translation(camera_position)
        print(translation_transform)
        look_at_transform = translation_transform @ rotation_transform
        return look_at_transform