import bpy
import random
import sys
import os
import argparse

# Add project root to path for imports
local_path = r'C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\contrastive_lighting_dataset_creation_utils'
if local_path in sys.path:
    sys.path.remove(local_path)
sys.path.append(local_path)

from camera_spawner import CameraSpawner
from discrete_light_utils import DiscreteLightGenerator, ObjectLoader, ObjectScatterer, ObjectSelector
from discrete_light_utils.collection_utils import clear_collection_objects, ensure_collection

import importlib
importlib.reload(sys.modules['discrete_light_utils'])
importlib.reload(sys.modules['camera_spawner'])
importlib.reload(sys.modules['discrete_light_utils.collection_utils'])

SCATTER_SURFACE_NAME = "scatter_surface"
CAMERA_NAME = "procedural_camera"
LOOK_FROM_VOLUME_NAME = "look_from_volume"
FOCUS_OBJECT_NAME = "focus_object"


if __name__ == "__main__":
    # Parse Blender CLI args (everything after '--') using argparse
    raw_argv = sys.argv
    if '--' in raw_argv:
        raw_argv = raw_argv[raw_argv.index('--') + 1:]
    else:
        raw_argv = []

    parser = argparse.ArgumentParser(description="Discrete light contrastive setup")
    parser.add_argument('folder', nargs='?', default=r'C:\Users\yaboy\Downloads\test_set_of_glb_files', help='Path to folder containing focus object files') # TODO: change default to None so that this arg is required
    parser.add_argument('-n', '--num-objects', type=int, default=3, help='Number of objects to import and scatter (default: 3)')
    parser.add_argument('--num-background-objects', type=int, default=3, help='Target number of background objects to place (default: 3)')
    parser.add_argument('--max-background-placement-attempts', type=int, default=50, help='Maximum attempts per background object placement (default: 50)')
    parser.add_argument('--min-distance', type=float, default=1.5, help='Minimum distance between scattered objects (default: 1.5)')
    parser.add_argument('--max-object-dimension', type=float, default=2, help='The size of the maximum dimension of imported objects after scaling (default: 2)')
    parser.add_argument('--lighting-seed', type=int, default=None, help='Random seed for discrete lighting generation (default: random)')
    parser.add_argument('--max-camera-attempts', type=int, default=20, help='Maximum attempts to place camera with visible lights (default: 100)')
    parser.add_argument('--max-camera-distance', type=float, default=10.0, help='Maximum distance of the camera from the focus object (default: 10.0)')
    args = parser.parse_args(raw_argv)
    folder_arg = args.folder
    num_background_objects = args.num_background_objects
    max_background_placement_attempts = args.max_background_placement_attempts
    lighting_seed = args.lighting_seed if args.lighting_seed is not None else random.randint(0, 10000)
    max_camera_placement_attempts = args.max_camera_attempts
    max_camera_distance = args.max_camera_distance
    camera_seed = random.randint(0, 10000)
    scatter_seed = random.randint(0, 10000)
    print(f"Using lighting seed: {lighting_seed}", flush=True)

    # Generate a lighting configuration based on the seed
    discrete_light_generator = DiscreteLightGenerator(seed=lighting_seed)
    discrete_light_generator.generate_light_configuration_from_seed()

    # Place a focus object
    clear_collection_objects('Focus_Objects') # TODO: this could probably move the unused objects into an unused collection, unless the likelihood of selecting the same object again is too low... 
    object_loader = ObjectLoader()
    object_selector = ObjectSelector(folder_arg, object_loader, max_file_size_mb=20)
    focus_object = object_selector.load_object()
    focus_object.name = FOCUS_OBJECT_NAME
    focus_objects_collection = ensure_collection('Focus_Objects')
    focus_objects_collection.objects.link(focus_object)
    object_scatterer = ObjectScatterer(scatter_plane_name=SCATTER_SURFACE_NAME, seed=scatter_seed, min_distance=args.min_distance)
    

    camera_and_object_placement_good = False
    object_placement_attempts = 0
    max_object_placement_attempts = 20

    while not camera_and_object_placement_good:
        object_placement_attempts += 1
        if object_placement_attempts > max_object_placement_attempts:
            raise RuntimeError(f"Failed to find a valid camera and object placement after {max_object_placement_attempts} attempts.")

        object_loader.set_object_origin(focus_object)
        object_scatterer.scatter_and_rotate(focus_object, check_bbox_intersection=False)
        object_loader.set_object_origin(focus_object, use_bbox_z='MAX', origin_offset = (0, 0, -0.2))

        # Place the camera in a valid location
        camera = bpy.data.objects.get(CAMERA_NAME)
        camera_spawner = CameraSpawner(LOOK_FROM_VOLUME_NAME, FOCUS_OBJECT_NAME, camera.name, use_look_at_volume_exact_location=True)
        camera_placement_attempts = 0
        while camera_placement_attempts < max_camera_placement_attempts:
            def pass_criteria(look_from, look_at):
                # Ensure the camera is at least 1 unit away from the focus object
                distance = (look_from - look_at).length
                return distance >= 1.0 and distance <= max_camera_distance
            # camera_spawner.update(update_seed=camera_seed, pass_criteria=pass_criteria, restore_hidden_state=True) # Place the camera where it can see the focus object
            camera_spawner.update(update_seed=camera_seed, pass_criteria=pass_criteria, required_visible_target_name=FOCUS_OBJECT_NAME, restore_hidden_state=True) # Place the camera where it can see the focus object
            discrete_light_generator.align_lighting_configuration_to_camera(camera)
            discrete_light_generator.align_lighting_configuration_to_target_object(focus_object)
            if discrete_light_generator.verify_lighting_visible_to_target(focus_object):
                camera_and_object_placement_good = True
                break
            print("Regenerating camera position to ensure lights are visible to focus object...", flush=True)
            camera_seed += 1  # Change seed to get a new camera position
            camera_placement_attempts += 1
    
        if camera_placement_attempts >= max_camera_placement_attempts:
            print(f"Failed to place camera with visible lights after {max_camera_placement_attempts} attempts. Retrying with new focus object placement...", flush=True)
            continue # Retry placing the focus object and camera
    
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
    
    background_objects_collection = ensure_collection('Background_Objects')
    clear_collection_objects('Background_Objects')
    
    placed_background_count = 0
    background_object_selector = ObjectSelector(folder_arg, object_loader, max_file_size_mb=20)
    
    print(f"Attempting to place {num_background_objects} background objects...", flush=True)
    
    for i in range(num_background_objects):
        print(f"Attempting to place background object {i+1}/{num_background_objects}...", flush=True)
        
        # Load a new background object
        try:
            bg_object = background_object_selector.load_object()
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
        
        # Set origin again after placement (similar to focus object pattern)
        object_loader.set_object_origin(bg_object, use_bbox_z='MAX', origin_offset=(0, 0, -0.2))
        
        # Verify this object doesn't obstruct any light to the focus object
        if discrete_light_generator.check_object_obstructs_lighting(bg_object, focus_object):
            print(f"Background object {i+1} obstructs lighting to focus object, removing.", flush=True)
            # Remove from scatterer tracking
            if bg_object in object_scatterer.placed_objects:
                object_scatterer.placed_objects.remove(bg_object)
            if object_scatterer.placed_positions:
                object_scatterer.placed_positions.pop()  # Remove last added position
            bpy.data.objects.remove(bg_object, do_unlink=True)
            continue
        
        placed_background_count += 1
        print(f"Successfully placed background object {i+1}.", flush=True)
    
    print(f"Successfully placed {placed_background_count}/{num_background_objects} background objects.", flush=True)