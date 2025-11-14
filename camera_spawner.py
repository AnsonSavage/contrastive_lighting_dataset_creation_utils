import bpy
import mathutils
import random
from random_utils import get_random_point_in_mesh
from rendering.log import Logger


class CameraSpawner:
    def __init__(self, look_from_volume_name, look_at_volume_name, camera_name):
        self.logger = Logger(prefix="CameraSpawner", verbose=True)
        self.logger.log(
            f"Initializing CameraSpawner with look_from='{look_from_volume_name}', "
            f"look_at='{look_at_volume_name}', camera='{camera_name}'",
            is_verbose=True,
        )
        self.look_at_volume = bpy.data.objects.get(look_at_volume_name)
        assert self.look_at_volume is not None, f"Look at volume '{look_at_volume_name}' not found in the scene."
        self.look_from_volume = bpy.data.objects.get(look_from_volume_name)
        assert self.look_from_volume is not None, f"Look from volume '{look_from_volume_name}' not found in the scene."
        self.camera_name = camera_name

    def update(self, update_seed, pass_criteria = None):
        self.logger.log(f"update() started with seed={update_seed}", is_verbose=True)
        look_at_was_hidden = self.look_at_volume.hide_get()
        look_from_was_hidden = self.look_from_volume.hide_get()
        try:
            if look_at_was_hidden:
                self.look_at_volume.hide_set(False)
            if look_from_was_hidden:
                self.look_from_volume.hide_set(False)

            assert update_seed is not None, "Seed must be provided."
            rng = random.Random(update_seed)
            has_good_sample = False
            max_attempts = 300
            attempts = 0
            look_at = None
            look_from = None
            while not has_good_sample and attempts < max_attempts:
                attempts += 1
                look_at_seed = rng.getrandbits(64)
                look_at = get_random_point_in_mesh(self.look_at_volume, seed=look_at_seed)
                if look_at is None:
                    continue
                look_from_seed = rng.getrandbits(64)
                look_from = get_random_point_in_mesh(self.look_from_volume, seed=look_from_seed)
                if look_from is None:
                    self.logger.log(
                        f"Attempt {attempts}: Failed to sample look_from point (seed={look_from_seed})",
                        is_verbose=True,
                    )
                    continue
                if pass_criteria is not None:
                    has_good_sample = pass_criteria(look_from, look_at)
                    self.logger.log(
                        f"Attempt {attempts}: pass_criteria returned {has_good_sample}",
                        is_verbose=True,
                    )
                else:
                    has_good_sample = True

            if not has_good_sample:
                self.logger.log(f"Failed to find valid camera positions after {max_attempts} attempts.")
                return

            camera = bpy.data.objects.get(self.camera_name)
            assert camera is not None, f"Camera '{self.camera_name}' not found in the scene."

            self.logger.log(
                f"Computing look-at matrix for camera '{self.camera_name}'",
                is_verbose=True,
            )
            look_at_matrix = self.compute_look_at_matrix(look_from, look_at)
            camera.matrix_world = look_at_matrix
            self.logger.log(f"Camera '{self.camera_name}' moved to coordinate: {look_from}")
            self.logger.log(f"Camera '{self.camera_name}' now looking at: {look_at}")
            self.logger.log("update() completed successfully", is_verbose=True)
        finally:
            if look_at_was_hidden:
                self.look_at_volume.hide_set(True)
            if look_from_was_hidden:
                self.look_from_volume.hide_set(True)

    def compute_look_at_matrix(self, camera_position: mathutils.Vector, target_position: mathutils.Vector):
        self.logger.log(
            f"compute_look_at_matrix() called with camera_position={camera_position}, "
            f"target_position={target_position}",
            is_verbose=True,
        )
        if (camera_position - target_position).length_squared < 0.0001:
            self.logger.log("Warning: Camera and target are at the same position.")
            return mathutils.Matrix.Translation(camera_position)

        camera_direction = (target_position - camera_position).normalized()
        up = mathutils.Vector((0, 0, 1))
        if abs(camera_direction.dot(up)) > 0.999:
            camera_right = mathutils.Vector((1, 0, 0))
            camera_up = camera_right.cross(camera_direction).normalized()
            camera_right = camera_direction.cross(camera_up).normalized()
        else:
            camera_right = camera_direction.cross(up).normalized()
            camera_up = camera_right.cross(camera_direction).normalized()

        rotation_transform = mathutils.Matrix([
            (*camera_right, 0),
            (*camera_up, 0),
            (*-camera_direction, 0),
            (0, 0, 0, 1)
        ]).transposed()

        translation_transform = mathutils.Matrix.Translation(camera_position)
        look_at_transform = translation_transform @ rotation_transform
        self.logger.log("compute_look_at_matrix() completed", is_verbose=True)
        return look_at_transform
