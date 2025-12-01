import bpy
import random
import sys
import os
import argparse
from typing import Callable
import mathutils

# Add project root to path for imports
local_path = r'C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\contrastive_lighting_dataset_creation_utils'
if local_path in sys.path:
    sys.path.remove(local_path)
sys.path.append(local_path)

from camera_spawner import CameraSpawner
from discrete_light_utils import DiscreteLightGenerator, ObjectLoader, ObjectScatterer, ObjectSelector
from discrete_light_utils.collection_utils import clear_collection_objects, ensure_collection
from rendering.render_manager import RenderManager
from scene_preparation_scripts.configure_discrete_light_scene import (
    SCATTER_SURFACE_NAME,
    CAMERA_NAME,
    LOOK_FROM_VOLUME_NAME,
    FOCUS_OBJECT_NAME,
    FOCUS_OBJECTS_COLLECTION_NAME,
    BACKGROUND_OBJECTS_COLLECTION_NAME,
    EXCLUDED_OBJECTS_COLLECTION_NAME
)

import importlib
importlib.reload(sys.modules['discrete_light_utils'])
importlib.reload(sys.modules['camera_spawner'])
importlib.reload(sys.modules['discrete_light_utils.collection_utils'])
importlib.reload(sys.modules['rendering.render_manager'])
importlib.reload(sys.modules['scene_preparation_scripts.configure_discrete_light_scene'])


def create_file_output_name(camera_seed: int, ligting_seed: int, scatter_seed: int, object_selector_seed: int) -> str:
    blend_file_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    return f"{blend_file_name}_cam_{camera_seed}_light_{ligting_seed}_scatter_{scatter_seed}_objsel_{object_selector_seed}.png"

def find_valid_camera_and_object_placement(
    object_loader: ObjectLoader,
    object_scatterer: ObjectScatterer,
    focus_object: bpy.types.Object,
    discrete_light_generator: DiscreteLightGenerator,
    max_camera_placement_attempts: int,
    max_camera_distance: float,
    camera_seed: int,
    camera_name: str,
    look_from_volume_name: str,
    focus_object_name: str,
    max_object_placement_attempts: int = 20
) -> int:
    camera_and_object_placement_good = False
    object_placement_attempts = 0

    while not camera_and_object_placement_good:
        object_placement_attempts += 1
        if object_placement_attempts > max_object_placement_attempts:
            raise RuntimeError(f"Failed to find a valid camera and object placement after {max_object_placement_attempts} attempts.")

        object_loader.set_object_origin(focus_object)
        object_scatterer.scatter_and_rotate(focus_object, check_bbox_intersection=False)
        object_loader.set_object_origin(focus_object, use_bbox_z='MAX', origin_offset = (0, 0, -0.2)) # Slightly lower origin than the top to help the camera and lights look more at the face of a person as opposed to the top of their head (if the object is a person, for example)

        # Place the camera in a valid location
        camera = bpy.data.objects.get(camera_name)
        camera_spawner = CameraSpawner(look_from_volume_name, focus_object_name, camera.name, use_look_at_volume_exact_location=True)
        camera_placement_attempts = 0
        while camera_placement_attempts < max_camera_placement_attempts:
            def pass_criteria(look_from, look_at):
                # Ensure the camera is at least 1 unit away from the focus object
                direction = (look_at - look_from).normalized()
                distance = (look_from - look_at).length
                looking_straight_down = mathutils.Vector((0, 0, -1)).dot(direction) > 0.6
                return distance >= 1.0 and distance <= max_camera_distance and not looking_straight_down
            
            camera_spawner.update(update_seed=camera_seed, pass_criteria=pass_criteria, required_visible_target_name=focus_object_name, restore_hidden_state=True, required_percentage_of_surface_visible=0.6) # Place the camera where it can see the focus object
            discrete_light_generator.align_lighting_configuration(camera, focus_object)
            if discrete_light_generator.verify_lighting_visible_to_target(focus_object):
                camera_and_object_placement_good = True
                break
            discrete_light_generator.align_lighting_configuration(camera, focus_object, inverse=True)
            print("Regenerating camera position to ensure lights are visible to focus object...", flush=True)
            camera_seed += 1  # Change seed to get a new camera position
            camera_placement_attempts += 1
    
        if camera_placement_attempts >= max_camera_placement_attempts:
            print(f"Failed to place camera with visible lights after {max_camera_placement_attempts} attempts. Retrying with new focus object placement...", flush=True)
            continue # Retry placing the focus object and camera
            
    return camera_seed

def sweep_lighting_seeds_and_render(
    discrete_light_generator: DiscreteLightGenerator,
    focus_object: bpy.types.Object,
    camera: bpy.types.Object,
    start_lighting_seed: int,
    total_lighting_seeds_attempt_to_render: int,
    output_dir: str,
    output_path_generator: Callable[[int], str],
    only_count=False
) -> int:
    """
    Sweeps through a range of lighting seeds, rendering images for valid configurations.

    Args:
        discrete_light_generator (DiscreteLightGenerator): The discrete light generator instance.
        focus_object (bpy.types.Object): The focus object in the scene.
        camera (bpy.types.Object): The camera used for rendering.
        start_lighting_seed (int): The starting lighting seed.
        total_lighting_seeds_attempt_to_render (int): Total number of lighting seeds to attempt rendering.
        output_dir (str): Directory to save rendered images.
        output_path_generator (callable): A callback function that generates output file names based on lighting seed.

    Returns:
        int: The number of valid renders completed.
    """
    render_manager = RenderManager()
    # Configure basic render settings
    render_manager.set_render_settings(
        resolution=(512, 512), 
        samples=128, 
        use_gpu_rendering=True
    )
    render_manager.set_camera(camera)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    valid_renders_count = 0
    
    for i in range(total_lighting_seeds_attempt_to_render):
        current_lighting_seed = start_lighting_seed + i
        print(f"Testing lighting seed: {current_lighting_seed}...", flush=True)
        
        # Update lighting
        discrete_light_generator.generate_light_configuration(seed=current_lighting_seed)
        
        discrete_light_generator.align_lighting_configuration(camera, focus_object)
        
        if discrete_light_generator.verify_lighting_visible_to_target(focus_object):
            print(f"Lighting seed {current_lighting_seed} is valid. Rendering...", flush=True)
            
            if not only_count:
                # Generate output path using the callback
                filename = output_path_generator(current_lighting_seed)
                output_path = os.path.join(output_dir, filename)
                
                render_manager.render(output_path=output_path)
            valid_renders_count += 1
        else:
            print(f"Lighting seed {current_lighting_seed} is invalid (obstructed). Skipping.", flush=True)

    print(f"Finished sweeping. Rendered {valid_renders_count} valid images.", flush=True)
    return valid_renders_count


if __name__ == "__main__":
    # Parse Blender CLI args (everything after '--') using argparse
    raw_argv = sys.argv
    if '--' in raw_argv:
        raw_argv = raw_argv[raw_argv.index('--') + 1:]
    else:
        raw_argv = []

    parser = argparse.ArgumentParser(description="Discrete light contrastive setup")
    parser.add_argument('folder', nargs='?', default=r'C:\Users\yaboy\Downloads\test_set_of_glb_files', help='Path to folder containing focus object files') # TODO: change default to None so that this arg is required
    parser.add_argument('--num-background-objects', type=int, default=2, help='Target number of background objects to place (default: 2)')
    parser.add_argument('--max-background-placement-attempts', type=int, default=50, help='Maximum attempts per background object placement (default: 50)')
    parser.add_argument('--min-distance', type=float, default=1.5, help='Minimum distance between scattered objects (default: 1.5)')
    parser.add_argument('--max-object-dimension', type=float, default=2, help='The size of the maximum dimension of imported objects after scaling (default: 2)')
    parser.add_argument('--lighting-seed', type=int, default=None, help='Random seed for discrete lighting generation (default: random)')
    parser.add_argument('--max-camera-attempts', type=int, default=20, help='Maximum attempts to place camera with visible lights (default: 100)')
    parser.add_argument('--max-camera-distance', type=float, default=10.0, help='Maximum distance of the camera from the focus object (default: 10.0)')
    parser.add_argument('--sweep-lighting', action='store_true', help='Enable sweeping through a range of lighting seeds')
    parser.add_argument('--num-lighting-samples', type=int, default=1000, help='Number of lighting seeds to sweep if --sweep-lighting is enabled (default: 1000)')
    parser.add_argument('--output-dir', type=str, default='output_renders', help='Directory to save renders (default: output_renders)')
    
    args = parser.parse_args(raw_argv)

    import json

    # Ensure output_dir is absolute
    if not os.path.isabs(args.output_dir):
        args.output_dir = os.path.join(local_path, args.output_dir)

    folder_arg = args.folder
    num_background_objects = args.num_background_objects

    # Check for scene metadata
    scene_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    metadata_path = os.path.join(local_path, "scene_metadata.json")
    
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            if scene_name in metadata:
                scene_data = metadata[scene_name]
                if "num_background_objects" in scene_data:
                    print(f"Overriding num_background_objects from metadata for scene '{scene_name}': {scene_data['num_background_objects']}", flush=True)
                    num_background_objects = scene_data["num_background_objects"]
        except Exception as e:
            print(f"Error reading scene metadata: {e}", flush=True)

    max_background_placement_attempts = args.max_background_placement_attempts
    lighting_seed = args.lighting_seed if args.lighting_seed is not None else random.randint(0, 10000)
    max_camera_placement_attempts = args.max_camera_attempts
    max_camera_distance = args.max_camera_distance
    camera_seed = random.randint(0, 10000)
    scatter_seed = random.randint(0, 10000)
    print(f"Using lighting seed: {lighting_seed}", flush=True)

    # Generate a lighting configuration based on the seed
    discrete_light_generator = DiscreteLightGenerator(seed=lighting_seed, excluded_collection_name=EXCLUDED_OBJECTS_COLLECTION_NAME)
    discrete_light_generator.generate_light_configuration()

    # Place a focus object
    clear_collection_objects(FOCUS_OBJECTS_COLLECTION_NAME) # TODO: this could probably move the unused objects into an unused collection, unless the likelihood of selecting the same object again is too low... 
    object_loader = ObjectLoader()
    object_selector_seed = random.randint(0, 10000)  # Separate seed for focus object selection
    object_selector = ObjectSelector(folder_arg, object_loader, max_file_size_mb=20, seed=object_selector_seed)
    focus_object = object_selector.load_object()
    focus_object.name = FOCUS_OBJECT_NAME
    focus_objects_collection = ensure_collection(FOCUS_OBJECTS_COLLECTION_NAME)
    focus_objects_collection.objects.link(focus_object)
    object_scatterer = ObjectScatterer(scatter_plane_name=SCATTER_SURFACE_NAME, seed=scatter_seed, min_distance=args.min_distance)
    

    camera_seed = find_valid_camera_and_object_placement(
        object_loader,
        object_scatterer,
        focus_object,
        discrete_light_generator,
        max_camera_placement_attempts,
        max_camera_distance,
        camera_seed,
        CAMERA_NAME,
        LOOK_FROM_VOLUME_NAME,
        FOCUS_OBJECT_NAME
    )
    
    camera = bpy.data.objects.get(CAMERA_NAME)
    
    # Successfully placed camera and focus object with visible lights

    # Set camera's focus distance to the focus object
    camera.data.dof.use_dof = True
    camera.data.dof.focus_object = focus_object
    camera.data.dof.aperture_fstop = 0.5  # Example f
    
    # Register the focus object with the scatterer for bbox collision checks
    object_scatterer.register_placed_object(focus_object)
    
    # Place background objects
    assert folder_arg is not None, "Error: No folder path provided for object import."
    assert os.path.exists(folder_arg), f"Error: Provided folder path does not exist: {folder_arg}"
    
    background_objects_collection = ensure_collection(BACKGROUND_OBJECTS_COLLECTION_NAME)
    clear_collection_objects(BACKGROUND_OBJECTS_COLLECTION_NAME)
    
    placed_background_count = 0
    
    print(f"Attempting to place {num_background_objects} background objects...", flush=True)
    
    for i in range(num_background_objects):
        print(f"Attempting to place background object {i+1}/{num_background_objects}...", flush=True)
        
        # Load a new background object
        try:
            bg_object = object_selector.load_object()
            if bg_object is None:
                print(f"Warning: Failed to load background object {i+1}, skipping.", flush=True)
                continue
        except Exception as e:
            print(f"Warning: Exception loading background object {i+1}: {e}, skipping.", flush=True)
            continue
        
        bg_object.name = f"background_object_{i}"
        
        # Link to background objects collection
        background_objects_collection.objects.link(bg_object)
        
        # Set origin before scattering
        object_loader.set_object_origin(bg_object)
        
        # Attempt to place with bbox collision checking
        placement_success = object_scatterer.scatter_and_rotate(
            bg_object, 
            check_bbox_intersection=True,
            max_attempts=max_background_placement_attempts
        )
        
        if not placement_success:
            print(f"Could not place background object {i+1} without bbox intersection, removing.", flush=True)
            bpy.data.objects.remove(bg_object, do_unlink=True)
            continue
        
        # Verify this object doesn't obstruct any light to the focus object
        if discrete_light_generator.check_object_obstructs_lighting(bg_object, focus_object):
            print(f"Background object {i+1} obstructs lighting to focus object, removing.", flush=True)
            # Remove from scatterer tracking
            object_scatterer.unregister_placed_object(bg_object)
            bpy.data.objects.remove(bg_object, do_unlink=True)
            continue
        
        placed_background_count += 1
        print(f"Successfully placed background object {i+1}.", flush=True)
    
    print(f"Successfully placed {placed_background_count}/{num_background_objects} background objects.", flush=True)

    args.sweep_lighting = True # TODO: remove this line after testing
    if args.sweep_lighting:
        print("Starting lighting sweep...", flush=True)
        
        # Create a callback that generates output filenames based on lighting seed
        def output_path_generator(lighting_seed):
            return create_file_output_name(
                camera_seed=camera_seed,
                ligting_seed=lighting_seed,
                scatter_seed=scatter_seed,
                object_selector_seed=object_selector_seed
            )
        
        sweep_lighting_seeds_and_render(
            discrete_light_generator,
            focus_object,
            camera,
            start_lighting_seed=lighting_seed,
            total_lighting_seeds_attempt_to_render=args.num_lighting_samples,
            output_dir=args.output_dir,
            output_path_generator=output_path_generator,
            only_count=True
        )
    else:
        print("Lighting sweep disabled. Setup complete.", flush=True)