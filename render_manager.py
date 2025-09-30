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

class ImageImageRenderManager:
    '''
    Is capable of rendering to disk, given the following:
        - A render output path
        - A camera seed
        - An HDRI name and rotation offset
    
    '''

    def render(self,
               output_path: str,
               scene_path: str,
               camera_seed: int,
               hdri_path: str,
               hdri_z_rotation_offset: float,
            ) -> str:
        camera_spawner = CameraSpawner( # TODO: right now, this assumes we're always using the procedural camera setup
            look_from_volume_name=LOOK_FROM_VOLUME_OBJ,
            look_at_volume_name=LOOK_AT_VOLUME_OBJ,
            camera_name=PROCEDURAL_CAMERA_OBJ
        )
        bpy.ops.wm.open_mainfile(filepath=scene_path)
        camera_spawner.update(update_seed=camera_seed)

        # Get Camera's Z rotation
        camera = bpy.data.objects.get(PROCEDURAL_CAMERA_OBJ)
        assert camera is not None, f"Camera '{PROCEDURAL_CAMERA_OBJ}' not found in the scene."
        assert camera.rotation_mode == 'XYZ', "Camera rotation mode must be 'XYZ' to extract Z rotation."
        camera_z_rotation = math.degrees(camera.rotation_euler.z)
        hdri_rotation = (camera_z_rotation + hdri_z_rotation_offset) % 360

        # Now that the camera is in place, we need to set the HDRI
        bpy.context.scene.world.node_tree.nodes['Environment Texture'].image = bpy.data.images.load(hdri_path)
        bpy.context.scene.world.node_tree.nodes['Mapping'].inputs['Rotation'].default_value[2] = math.radians(hdri_rotation) # TODO: check but I'm pretty sure this should be radians.

        # Finally, we need to set the output path and render the image
        bpy.context.scene.render.filepath = output_path
        bpy.ops.render.render(write_still=True)

        return output_path

# Read in command line arguments including --output_path, --scene_path, --camera_seed, --hdri_path, --hdri_z_rotation_offset

if __name__ == "__main__":
    # Full argv as received inside Blender's python or normal python execution
    print("Raw sys.argv:", sys.argv)

    # Strategy: Blender (and other wrappers) pass their own flags before the '--'.
    # We locate '--' and only parse what follows. If '--' not present, fall back to standard parsing.
    try:
        dashdash_index = sys.argv.index('--')
        args_after_dashdash = sys.argv[dashdash_index + 1:]
    except ValueError:
        args_after_dashdash = sys.argv[1:]  # No '--' present

    print("Args considered for argparse:", args_after_dashdash)

    parser = argparse.ArgumentParser(
        description="Render an image with specified parameters (expects arguments after '--')."
    )
    parser.add_argument('--output_path', type=str, required=True, help='Path to save the rendered image.')
    parser.add_argument('--scene_path', type=str, required=True, help='Path to the Blender scene file (.blend).')
    parser.add_argument('--camera_seed', type=int, required=True, help='Seed for the camera randomness.')
    parser.add_argument('--hdri_path', type=str, required=True, help='Path to the HDRI file.')
    parser.add_argument('--hdri_z_rotation_offset', type=float, required=True, help='Z rotation offset for the HDRI in degrees.')

    # Parse only the relevant slice
    args = parser.parse_args(args_after_dashdash)

    render_manager = ImageImageRenderManager()
    result_path = render_manager.render(
        output_path=args.output_path,
        scene_path=args.scene_path,
        camera_seed=args.camera_seed,
        hdri_path=args.hdri_path,
        hdri_z_rotation_offset=args.hdri_z_rotation_offset
    )
    print(f"Render complete: {result_path}")