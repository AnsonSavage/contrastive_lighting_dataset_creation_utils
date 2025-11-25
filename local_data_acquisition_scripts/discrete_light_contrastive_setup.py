import bpy
import random
import math
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


if __name__ == "__main__":
    # Parse Blender CLI args (everything after '--') using argparse
    raw_argv = sys.argv
    if '--' in raw_argv:
        raw_argv = raw_argv[raw_argv.index('--') + 1:]
    else:
        raw_argv = []

    parser = argparse.ArgumentParser(description="Discrete light contrastive setup")
    parser.add_argument('folder', nargs='?', default=None, help='Path to folder containing focus object files')
    parser.add_argument('-n', '--num-objects', type=int, default=3, help='Number of objects to import and scatter (default: 3)')
    parser.add_argument('--min-distance', type=float, default=1.5, help='Minimum distance between scattered objects (default: 1.5)')
    args = parser.parse_args(raw_argv)

    # folder_arg = args.folder
    folder_arg = r'C:\Users\yaboy\Downloads\test_set_of_glb_files' # TODO: replace this with args.folder for actual usage

    active_cam = bpy.context.scene.camera

    object_loader = ObjectLoader()

    focus_object = None
    all_imported_objects = []  # All imported objects for scattering

    # If a folder is provided, import n random models
    if folder_arg:
        if os.path.isdir(folder_arg):
            clear_collection_objects('Focus_Objects')
            
            object_selector = ObjectSelector(folder_arg)
            print(f"Found {len(object_selector.all_files)} compatible files in folder: {folder_arg}", flush=True)
            
            if not object_selector.all_files:
                print(f"No compatible files found. Supported: {object_selector.supported_extensions}")
            else:
                num_to_import = args.num_objects
                focus_objects_collection = ensure_collection('Focus_Objects')
                
                print(f"Attempting to import {num_to_import} valid objects...")
                
                selected_filenames = set()
                
                while len(all_imported_objects) < num_to_import:
                    # Try to pick a file that hasn't been selected yet, unless we have to
                    valid_files = object_selector.get_valid_files()
                    available_files = list(set(valid_files) - selected_filenames)
                    
                    if not available_files:
                        # If we ran out of unique files, allow reuse if we have any valid files
                        if not valid_files:
                            print("No valid files left.")
                            break
                        chosen = random.choice(valid_files)
                    else:
                        chosen = random.choice(available_files)
                        
                    chosen_path = os.path.join(folder_arg, chosen)
                    print(f"Importing object {len(all_imported_objects)+1}/{num_to_import}: {chosen_path}")
                    
                    imported_obj = object_loader.import_object(chosen_path)
                    imported_objects = list(bpy.context.selected_objects)
                    
                    # Preprocess (merge, scale, set origin)
                    processed_obj = object_loader.preprocess_object(imported_objects)
                    
                    if processed_obj:
                        # Check for emissive materials
                        if object_selector.is_emissive(processed_obj):
                            print(f"Object {chosen} has emissive materials. Marking invalid and removing.")
                            object_selector.mark_invalid(chosen)
                            bpy.data.objects.remove(processed_obj, do_unlink=True)
                            continue
                        
                        # Move imported objects into the Focus_Objects collection
                        try:
                            if processed_obj.name not in focus_objects_collection.objects:
                                focus_objects_collection.objects.link(processed_obj)
                        except Exception:
                            pass
                            
                        all_imported_objects.append(processed_obj)
                        selected_filenames.add(chosen)
                    else:
                        print(f"Failed to process object {chosen}.")
                        # If preprocessing failed (e.g. no mesh), mark as invalid so we don't try again
                        object_selector.mark_invalid(chosen)
                
                # Select one object to be the focus object
                if all_imported_objects:
                    focus_object = random.choice(all_imported_objects)
                    print(f"Selected focus object: {focus_object.name}")
        else:
            print(f"Provided folder path does not exist: {folder_arg}")

    if not focus_object:
        print("Error: No focus object found or imported. Exiting.")
    else:
        # Scatter all objects (including focus) with minimum distance between them
        scatterer = ObjectScatterer("scatter_plane", seed=random.randint(0, 10000), min_distance=args.min_distance)
        scatterer.scatter_multiple(all_imported_objects)
        object_loader.set_object_origin(focus_object, use_bbox_z='MAX', origin_offset = (0, 0, -0.2))

        camera_spawner = CameraSpawner("look_from_volume", focus_object.name, active_cam.name, use_look_at_volume_exact_location=True)
        camera_spawner.update(random.randint(0, 10000), restore_hidden_state=True)

        # Ensure the camera's depth-of-field is focused on the selected focus object
        try:
            if active_cam and active_cam.type == 'CAMERA':
                active_cam.data.dof.use_dof = True
                active_cam.data.dof.focus_object = focus_object
                # set a reasonably large aperture (small f-stop) for visible DOF if supported
                if hasattr(active_cam.data.dof, 'aperture_fstop'):
                    active_cam.data.dof.aperture_fstop = 0.5
                print(f"Set camera '{active_cam.name}' focus to object '{focus_object.name}'")
        except Exception as e:
            print(f"Warning: failed to set camera focus: {e}")
        
        generator = DiscreteLightGenerator()
        generator.set_seed(6429) # random.randint(0, 10000))
        generator.generate_lights(focus_object, active_cam)