# Assumes that Blender is loaded up with the relevant scene... Although loading the scene here wouldn't be bad.

import math
import bpy
# Add this file's directory to the Python path for imports
import sys
import pathlib
current_dir = pathlib.Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from camera_spawner import CameraSpawner
from configure_camera_collections import PROCEDURAL_CAMERA_OBJ, LOOK_FROM_VOLUME_OBJ, LOOK_AT_VOLUME_OBJ
import argparse

should_log = True

def log(msg: str) -> None:
    if should_log:
        print(f"[render_manager] {msg}")

class ImageImageRenderManager:
    '''
    Is capable of rendering to disk, given the following:
        - A render output path
        - A camera seed
        - An HDRI name and rotation offset
    
    '''

    def _set_hdri(self, hdri_path: str, strength: float = 1.0, rotation_degrees: float = 0.0) -> None:
        """
        Set an HDRI environment texture in Blender's World settings.
        
        :param hdri_path: Full path to the HDRI image file
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
        
        # Optional: Set strength of the HDRI (default is 1.0)
        background.inputs["Strength"].default_value = strength
    
    def render(self,
                output_path: str,
            #    scene_path: str,
                camera_seed: int,
                hdri_path: str,
                hdri_z_rotation_offset: float,
                resolution = (384, 384),
                use_denoising = True,
                use_denoising_gpu = True,
                samples = 128
            ) -> str:
        camera_spawner = CameraSpawner( # TODO: right now, this assumes we're always using the procedural camera setup
            look_from_volume_name=LOOK_FROM_VOLUME_OBJ,
            look_at_volume_name=LOOK_AT_VOLUME_OBJ,
            camera_name=PROCEDURAL_CAMERA_OBJ
        )
        # bpy.ops.wm.open_mainfile(filepath=scene_path) # TODO: IDK why, but this didn't seem to load the scene in time. Okay, yeah, you basically need to set up a callback with @persistent and bpy.app.handlers.load_post
        camera = bpy.data.objects.get(PROCEDURAL_CAMERA_OBJ)
        camera_z_rotation = math.degrees(camera.rotation_euler.z)
        log(f"Camera Z rotation before updating seed: {camera_z_rotation} degrees")
        camera_spawner.update(update_seed=camera_seed)

        # Get Camera's Z rotation
        camera = bpy.data.objects.get(PROCEDURAL_CAMERA_OBJ)
        assert camera is not None, f"Camera '{PROCEDURAL_CAMERA_OBJ}' not found in the scene."
        assert camera.rotation_mode == 'XYZ', "Camera rotation mode must be 'XYZ' to extract Z rotation."
        camera_z_rotation = math.degrees(camera.rotation_euler.z)
        log(f"Camera Z rotation: {camera_z_rotation} degrees")
        hdri_rotation = (camera_z_rotation + hdri_z_rotation_offset) % 360
        log(f"HDRI rotation set to: {hdri_rotation} degrees (Camera Z rotation: {camera_z_rotation}, Offset: {hdri_z_rotation_offset})")

        # Set the scene active camera
        bpy.context.scene.camera = camera

        # Now that the camera is in place, we need to set the HDRI
        self._set_hdri(hdri_path, strength=1.0, rotation_degrees=hdri_rotation)

        # Finally, we need to set the output path and render the image
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

        bpy.ops.render.render(write_still=True)

        return output_path

# Read in command line arguments including --output_path, --scene_path, --camera_seed, --hdri_path, --hdri_z_rotation_offset

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
    # parser.add_argument('--scene_path', type=str, required=True, help='Path to the Blender scene file (.blend).')
    parser.add_argument('--camera_seed', type=int, required=True, help='Seed for the camera randomness.')
    parser.add_argument('--hdri_path', type=str, required=True, help='Path to the HDRI file.')
    parser.add_argument('--hdri_z_rotation_offset', type=float, required=True, help='Z rotation offset for the HDRI in degrees.')

    # Parse only the relevant slice
    args = parser.parse_args(args_after_dashdash)

    render_manager = ImageImageRenderManager()
    result_path = render_manager.render(
        output_path=args.output_path,
        # scene_path=args.scene_path,
        camera_seed=args.camera_seed,
        hdri_path=args.hdri_path,
        hdri_z_rotation_offset=args.hdri_z_rotation_offset
    )
    log(f"Render complete: {result_path}")