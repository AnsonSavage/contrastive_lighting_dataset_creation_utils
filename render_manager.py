# Assumes that Blender is loaded up with the relevant scene... Although loading the scene here wouldn't be bad.

import os
import pickle
import math
import random
import bpy
# Add this file's directory to the Python path for imports
import mathutils
from mathutils import Vector, Matrix
import sys
import pathlib
current_dir = pathlib.Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))
from data.image_text_instructions_task import ImageTextInstructSignatureVector
from data.signature_vector.light_attribute import LightIntensity, BlackbodyLightColor, LightDirection, VirtualLight
from camera_spawner import CameraSpawner
import base64
from configure_camera_collections import PROCEDURAL_CAMERA_OBJ, LOOK_FROM_VOLUME_OBJ, LOOK_AT_VOLUME_OBJ
import argparse
import tempfile

should_log = True

def log(msg: str) -> None:
    if should_log:
        print(f"[render_manager] {msg}", flush=True)

class HDRIManager:
    """Manages HDRI environment texture setup in Blender's World settings."""
    
    def set_hdri(self, hdri_path: str, strength: float = 1.0, rotation_degrees: float = 0.0) -> None:
        """
        Set an HDRI environment texture in Blender's World settings.
        
        :param hdri_path: Full path to the HDRI image file
        :param strength: Strength/intensity of the HDRI lighting
        :param rotation_degrees: Z-axis rotation offset in degrees
        """
        # Clear existing world nodes
        bpy.context.scene.world.node_tree.nodes.clear()
        
        # Create new World output node
        world_output = bpy.context.scene.world.node_tree.nodes.new(type='ShaderNodeOutputWorld')
        
        # Create Environment Texture node
        env_texture = bpy.context.scene.world.node_tree.nodes.new(type='ShaderNodeTexEnvironment')
        
        # Set the image for the Environment Texture
        env_texture.image = bpy.data.images.load(str(hdri_path))
        
        # Create Background node
        background = bpy.context.scene.world.node_tree.nodes.new(type='ShaderNodeBackground')

        # Create Mapping node
        mapping = bpy.context.scene.world.node_tree.nodes.new(type='ShaderNodeMapping')
        mapping.vector_type = 'POINT'
        mapping.inputs['Rotation'].default_value[2] = math.radians(rotation_degrees)

        # Create texture coordinate node
        tex_coord = bpy.context.scene.world.node_tree.nodes.new(type='ShaderNodeTexCoord')
        
        # Link nodes
        links = bpy.context.scene.world.node_tree.links
        links.new(env_texture.outputs["Color"], background.inputs["Color"])
        links.new(background.outputs["Background"], world_output.inputs["Surface"])
        links.new(mapping.outputs["Vector"], env_texture.inputs["Vector"])
        links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
        
        background.inputs["Strength"].default_value = strength

class SceneManager:
    """Interface for scene setup logic (camera, lights, world, etc.)."""

    def setup_scene(self, *args, **kwargs) -> None:  # noqa: D401 (simple interface)
        """Set up scene-specific elements before rendering."""
        raise NotImplementedError("SceneManager.setup_scene() must be implemented by subclasses")


class RenderManager:
    """
    Core render manager that configures render settings and triggers the render.
    Compose this with a SceneManager which is responsible for scene setup.
    """
    def __init__(self):
        self.is_render_settings_configured = False

    @staticmethod
    def set_gpu():
        log("Attempting to configure GPU rendering...")
        try:
            bpy.context.scene.render.engine = "CYCLES"
            bpy.context.scene.cycles.device = "GPU"

            prefs = bpy.context.preferences.addons["cycles"].preferences

            # Try to set OPTIX
            try:
                prefs.compute_device_type = "OPTIX"
                prefs.get_devices() # This will error if 'OPTIX' is not a valid type
            except Exception as e:
                # If OPTIX fails, fall back to CUDA
                try:
                    prefs.compute_device_type = "CUDA"
                    prefs.get_devices()
                except Exception as e2:
                    log(f"Warning: Could not set OPTIX or CUDA: {e2}")

            log(f"Set compute backend to: {prefs.compute_device_type}")

            # Call get_devices() again to populate the list for the chosen backend
            prefs.get_devices()

            # Enable all devices (GPU and CPU) following your example's structure
            # This iterates over the `preferences.devices` collection
            if not prefs.devices:
                raise Exception("No devices found for the selected backend.")

            log("Enabling devices...")
            for d in prefs.devices:
                d.use = True # Set device to be used
                log(f"Enabled: {d.name}, Type: {d.type}, Use: {d.use}")

        except Exception as e:
            log(f"Warning: Could not configure GPU rendering preferences: {e}")
            log("Will attempt to render with default scene settings.")
    
    def set_render_settings(
        self,
        output_path: str = os.path.join(tempfile.gettempdir(), "render.png"),
        resolution: tuple[int, int] = (384, 384),
        use_denoising: bool = True,
        use_denoising_gpu: bool = True,
        samples: int = 128,
        use_gpu_rendering: bool = True
    ) -> None:
        """Configure render settings for Cycles."""
        scene = bpy.context.scene
        scene.render.filepath = output_path
        scene.render.resolution_x = resolution[0]
        scene.render.resolution_y = resolution[1]
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_mode = 'RGB'
        scene.render.resolution_percentage = 100
        scene.cycles.use_denoising = use_denoising
        scene.cycles.denoising_use_gpu = use_denoising_gpu
        scene.cycles.samples = samples
        if use_gpu_rendering:
            RenderManager.set_gpu()

        # Color management settings
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'None' # You can change this to 'Medium Contrast', etc.
        scene.view_settings.exposure = 0.0
        scene.view_settings.gamma = 1.0
        self.is_render_settings_configured=True
    
    def render(self, output_path=None) -> str:
        """
        Main render entry point.
        
        :param output_path: Where to save the rendered image (use None to use the previous render settings)
        :return: Path to the rendered image
        """
        # Scene setup is handled by a SceneManager. We don't assert here to keep responsibilities separated.
        if not self.is_render_settings_configured:
            log("Warning: render settings have not been configured")

        scene = bpy.context.scene
        if output_path is not None:
            scene.render.filepath = output_path

        bpy.ops.render.render(write_still=True)
        log(f"Render complete: {scene.render.filepath}")
        return scene.render.filepath

class ImageImageSceneManager(SceneManager):
    """
    Sets up scenes using camera seeds and HDRI environments.
    Suitable for image-to-image tasks.
    """
    def __init__(self):
        self.hdri_manager = HDRIManager()

    def setup_scene(
        self,
        camera_seed: int,
        hdri_path: str,
        hdri_z_rotation_offset: float,
    ) -> None:
        """
        Set up camera and HDRI before rendering.
        
        :param camera_seed: Seed for camera randomness
        :param hdri_path: Path to HDRI file
        :param hdri_z_rotation_offset: Z rotation offset in degrees
        """
        camera_spawner = CameraSpawner(
            look_from_volume_name=LOOK_FROM_VOLUME_OBJ,
            look_at_volume_name=LOOK_AT_VOLUME_OBJ,
            camera_name=PROCEDURAL_CAMERA_OBJ
        )
        
        camera = bpy.data.objects.get(PROCEDURAL_CAMERA_OBJ)
        camera_z_rotation_before = math.degrees(camera.rotation_euler.z)
        log(f"Camera Z rotation before updating seed: {camera_z_rotation_before} degrees")
        
        camera_spawner.update(update_seed=camera_seed)

        # Get Camera's Z rotation after update
        camera = bpy.data.objects.get(PROCEDURAL_CAMERA_OBJ)
        assert camera is not None, f"Camera '{PROCEDURAL_CAMERA_OBJ}' not found in the scene."
        assert camera.rotation_mode == 'XYZ', "Camera rotation mode must be 'XYZ' to extract Z rotation."
        camera_z_rotation = math.degrees(camera.rotation_euler.z)
        log(f"Camera Z rotation after update: {camera_z_rotation} degrees")
        
        hdri_rotation = (camera_z_rotation + hdri_z_rotation_offset) % 360
        log(f"HDRI rotation set to: {hdri_rotation} degrees (Camera Z: {camera_z_rotation}, Offset: {hdri_z_rotation_offset})")

        # Set the scene active camera
        bpy.context.scene.camera = camera

        # Set HDRI
        self.hdri_manager.set_hdri(hdri_path, strength=1.0, rotation_degrees=hdri_rotation)

class ImageTextSceneManager(SceneManager):
    """
    Sets up scenes using virtual lights and signature vectors.
    Suitable for image-text instruction tasks.
    """
    
    @staticmethod
    def _sample_cone(normal: Vector, theta_max_deg: float) -> Vector:
        theta_max = math.radians(theta_max_deg)
        u = random.random()
        v = random.random()
        cos_theta = (1 - u) + u * math.cos(theta_max)
        sin_theta = math.sqrt(1 - cos_theta * cos_theta)
        phi = 2 * math.pi * v
        # Local direction (cone axis is +Z)
        dir_local = Vector((sin_theta * math.cos(phi), sin_theta * math.sin(phi), cos_theta))
        # Build orthonormal basis
        def basis_from_normal(n):
            n = n.normalized()
            if abs(n.z) < 0.999:
                t = n.cross(Vector((0,0,1))).normalized()
            else:
                t = n.cross(Vector((0,1,0))).normalized()
            b = n.cross(t)
            return Matrix((t, b, n)).transposed()
        M = basis_from_normal(normal)
        return (M @ dir_local).normalized()
    
    def _sample_gaussian_in_range(self, intensity_range: tuple[float, float], rng: random.Random) -> float:
        mu = (intensity_range[0] + intensity_range[1]) / 2
        single_standard_deviation = (intensity_range[1] - intensity_range[0]) / 4  # 95% of values will fall within the range
        random_gaussian_distributed_value = rng.gauss(mu=mu, sigma=single_standard_deviation)
        clamped_value = max(intensity_range[0], min(intensity_range[1], random_gaussian_distributed_value))
        return clamped_value
    
    def _sample_light_intensity(self, light_name: str, distance_from_object: float, intensity: LightIntensity, sample_seed: int) -> None:
        light = bpy.data.lights.get(light_name)
        if light is None:
            raise ValueError(f"Light '{light_name}' not found in the scene.")
        
        light.normalize = True  # Ensure the light uses normalized intensity to account for light scale

        rng = random.Random(sample_seed)
        # First we'll compute the base intensity, then we'll map that to what it should be after normalizing for distance between focus object
        base_intensity = None
        low_range = (5, 15)
        medium_range = (15, 70)
        high_range = (90, 200)

        if intensity == LightIntensity.LOW:
            base_intensity = self._sample_gaussian_in_range(low_range, rng)
        elif intensity == LightIntensity.MEDIUM:
            base_intensity = self._sample_gaussian_in_range(medium_range, rng)
        elif intensity == LightIntensity.HIGH:
            base_intensity = self._sample_gaussian_in_range(high_range, rng)
        else:
            raise ValueError(f"Unknown LightIntensity value: {intensity}")
        
        # Base intensity values were computed with a 1x1m area light at 2m distance from the focus object. So, to normalize for distance, we can use the inverse square law:
        original_distance = 2.0
        original_ratio = base_intensity / (original_distance ** 2)
        adjusted_intensity = original_ratio * (distance_from_object ** 2)

        light.energy = adjusted_intensity
        log(f"Set light '{light_name}' intensity to {light.energy} (base: {base_intensity}, distance: {distance_from_object})")
    
    def _sample_light_color_blackbody(self, light_name: str, blackbody_color: BlackbodyLightColor, sample_seed: int) -> None:
        rng = random.Random(sample_seed)
        light = bpy.data.lights.get(light_name)
        if light is None:
            raise ValueError(f"Light '{light_name}' not found in the scene.")
        
        kelvin_temp = None
        if blackbody_color == BlackbodyLightColor.COOL:
            kelvin_temp = self._sample_gaussian_in_range((6800, 18000), rng)
        elif blackbody_color == BlackbodyLightColor.NEUTRAL:
            kelvin_temp = self._sample_gaussian_in_range((5700, 6500), rng)
        elif blackbody_color == BlackbodyLightColor.WARM:
            kelvin_temp = self._sample_gaussian_in_range((2300, 5000), rng)
        else:
            raise ValueError(f"Unknown BlackbodyLightColor value: {blackbody_color}")
        light.use_temperature = True
        light.color = (1, 1, 1)  # Reset tint to white before applying temperature
        light.temperature = kelvin_temp
        log(f"Set light '{light_name}' color temperature to {kelvin_temp}K")

    def _sample_light_location(
        self,
        cam: bpy.types.Object,
        obj: bpy.types.Object,
        light_name: str,
        light_direction: LightDirection,
        distance_from_object: float = 2,
        camera_left_right_amount: float = 0.8,
        sample_cone_degrees: float = 15
    ) -> None:
        light_direction_name = light_direction.name

        camera_to_object = obj.location - cam.location
        z_axis = mathutils.Vector((0, 0, 1))
        camera_to_object.normalize()
        camera_left = z_axis.cross(camera_to_object).normalized()
        camera_right = -camera_left

        object_to_light_vector = None
        if 'BACK' in light_direction_name:
            object_to_light_vector = camera_to_object.reflect(z_axis)
        elif 'FRONT' in light_direction_name:
            object_to_light_vector = -camera_to_object

        if 'RIGHT' in light_direction_name:
            object_to_light_vector += camera_right * camera_left_right_amount
        elif 'LEFT' in light_direction_name:
            object_to_light_vector += camera_left * camera_left_right_amount

        object_to_light_vector.normalize()
        object_to_light_vector += z_axis * 0.5

        light_location = (
            obj.location +
            ImageTextSceneManager._sample_cone(object_to_light_vector, sample_cone_degrees) * distance_from_object
        )

        # Create a new light data block
        light_object = bpy.data.objects.get(light_name)
        light_object.location = light_location

        # Point the light at the object using a track to constraint
        constraint = light_object.constraints.new(type='TRACK_TO')
        constraint.target = obj
    
    def setup_scene(self, signature_vector: ImageTextInstructSignatureVector, **kwargs) -> None:
        """
        Set up lights based on the signature vector.
        
        :param signature_vector: Signature vector defining the lighting setup
        """
        log(f"Setting up scene for signature vector: {signature_vector}")
        # TODO: Implement light setup logic based on signature_vector
        # This would call _sample_light_location, _sample_light_intensity, _sample_light_color_blackbody, etc.
        pass

if __name__ == "__main__":
    try:
        dashdash_index = sys.argv.index('--')
        args_after_dashdash = sys.argv[dashdash_index + 1:]
    except ValueError:
        args_after_dashdash = sys.argv[1:]  # No '--' present

    parser = argparse.ArgumentParser(
        description="Render an image with specified parameters (expects arguments after '--')."
    )
    parser.add_argument('--output_path', type=str, required=True, help='Path to save the rendered image.')
    parser.add_argument('--mode', type=str, choices=['image-image', 'image-text-instruct'], default='image-text-instruct', help='Rendering mode')
    
    # Parse mode first to determine which additional args to expect
    mode_args, remaining = parser.parse_known_args(args_after_dashdash)
    
    render_manager = RenderManager()
    render_manager.set_render_settings(resolution=(256, 256), samples=64)

    if mode_args.mode == 'image-image':
        parser.add_argument('--camera_seed', type=int, required=True, help='Seed for the camera randomness.')
        parser.add_argument('--hdri_path', type=str, required=True, help='Path to the HDRI file.')
        parser.add_argument('--hdri_z_rotation_offset', type=float, required=True, help='Z rotation offset for the HDRI in degrees.')

        args = parser.parse_args(args_after_dashdash)

        scene_manager = ImageImageSceneManager()
        scene_manager.setup_scene(
            camera_seed=args.camera_seed,
            hdri_path=args.hdri_path,
            hdri_z_rotation_offset=args.hdri_z_rotation_offset
        )
        result_path = render_manager.render(output_path=args.output_path)
        
    elif mode_args.mode == 'image-text-instruct':
        parser.add_argument('--serialized_signature_vector', type=str, required=True, help='Serialized signature vector in pickle format.')
        args = parser.parse_args(args_after_dashdash)

        signature_vector_str = args.serialized_signature_vector
        signature_vector_bytes = base64.b64decode(signature_vector_str.encode('ascii'))
        signature_vector = pickle.loads(signature_vector_bytes)
        
        scene_manager = ImageTextSceneManager()
        scene_manager.setup_scene(signature_vector=signature_vector)
        result_path = render_manager.render(output_path=args.output_path)