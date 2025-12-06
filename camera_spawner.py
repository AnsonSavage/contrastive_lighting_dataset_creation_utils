import bpy
import mathutils
import random
from utils.random_utils import get_random_point_in_mesh
from rendering.log import Logger
from utils.visibility_utils import check_visibility, is_point_inside_mesh


class CameraSpawner:
    def __init__(self, look_from_volume_name, look_at_volume_name, camera_name, use_look_at_volume_exact_location=False):
        """ Initialize CameraSpawner class

        Args:
            look_from_volume_name (str): Name of the volume object to look from.
            look_at_volume_name (str): Name of the volume object to look at.
            camera_name (str): Name of the camera object.
            use_look_at_volume_exact_location (bool, optional): Whether to use the exact location of the look_at volume. Defaults to False.
        """

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
        self.use_look_at_volume_exact_location = use_look_at_volume_exact_location

    def update(self, update_seed, pass_criteria=None, restore_hidden_state=False, required_visible_target_name=None, max_attempts=80, required_percentage_of_surface_visible=None):
        if required_percentage_of_surface_visible is not None:
            assert required_visible_target_name is not None, "If required_percentage_of_surface_visible is set, required_visible_target_name must also be set."

        self.logger.log(f"update() started with seed={update_seed}", is_verbose=True)
        look_at_was_hidden = self.look_at_volume.hide_get()
        look_from_was_hidden = self.look_from_volume.hide_get()
        try:
            assert update_seed is not None, "Seed must be provided."
            rng = random.Random(update_seed)
            has_good_sample = False
            attempts = 0
            look_at = None
            look_from = None
            while not has_good_sample and attempts < max_attempts:
                # Ensure volumes are visible for sampling
                if look_at_was_hidden:
                    self.look_at_volume.hide_set(False)
                if look_from_was_hidden:
                    self.look_from_volume.hide_set(False)

                attempts += 1
                if self.use_look_at_volume_exact_location:
                    look_at = self.look_at_volume.location
                else:
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
                
                has_good_sample = True
                if pass_criteria is not None:
                    has_good_sample = has_good_sample and pass_criteria(look_from, look_at)
                
                if has_good_sample and required_visible_target_name is not None:
                    assert required_percentage_of_surface_visible is not None, "required_percentage_of_surface_visible must be set when required_visible_target_name is provided."
                    has_good_sample = self.validate_camera_can_see_target_object(look_from, required_visible_target_name, required_percentage_of_surface_visible=required_percentage_of_surface_visible)

                if pass_criteria is not None or required_visible_target_name is not None:
                    self.logger.log(
                        f"Attempt {attempts}: validation returned {has_good_sample}",
                        is_verbose=True,
                    )

            if not has_good_sample:
                error_msg = f"Failed to find valid camera positions after {max_attempts} attempts."
                self.logger.log(error_msg)
                raise RuntimeError(error_msg)

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
            if restore_hidden_state:
                if look_at_was_hidden:
                    self.look_at_volume.hide_set(True)
                if look_from_was_hidden:
                    self.look_from_volume.hide_set(True)

    def validate_camera_can_see_target_object(self, look_from: mathutils.Vector, object_name: str, required_percentage_of_surface_visible: float) -> bool:
        """
        Validates that the camera position allows visibility of the specified object
        and that the camera is not inside the object.

        Args:
            look_from (mathutils.Vector): The candidate camera position.
            look_at (mathutils.Vector): The point the camera is looking at.
            object_name (str): The name of the object to check visibility for.

        Returns:
            bool: True if the object is visible and camera is not inside it, False otherwise.
        """
        target_obj = bpy.data.objects.get(object_name)
        if target_obj is None:
            self.logger.log(f"Validation failed: Object '{object_name}' not found.", is_verbose=True)
            return False

        # Hide the look_at and look_from volumes to avoid interference with ray casting
        # BUT: Do not hide the look_at_volume if it IS the target object
        look_at_was_hidden = self.look_at_volume.hide_get()
        look_from_was_hidden = self.look_from_volume.hide_get()
        
        should_hide_look_at = (self.look_at_volume != target_obj)

        try:
            if should_hide_look_at:
                self.look_at_volume.hide_set(True)
            
            self.look_from_volume.hide_set(True)
            
            # Check visibility
            return check_visibility(look_from, target_obj, minimum_percentage_of_surface_visible=required_percentage_of_surface_visible) and not is_point_inside_mesh(target_obj, look_from)
        finally:
            # Restore visibility state
            if should_hide_look_at:
                self.look_at_volume.hide_set(look_at_was_hidden)
            
            self.look_from_volume.hide_set(look_from_was_hidden)

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
