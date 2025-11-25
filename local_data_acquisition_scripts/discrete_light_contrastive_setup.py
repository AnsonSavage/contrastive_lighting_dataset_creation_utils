import bpy
import random
import math
import sys
import os
import argparse

# Add project root to path for imports
sys.path.append(r'C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\contrastive_lighting_dataset_creation_utils')

from camera_spawner import CameraSpawner
from discrete_light_utils import DiscreteLightGenerator, ObjectLoader, ObjectScatterer
from discrete_light_utils.collection_utils import clear_collection_objects, ensure_collection


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
    all_scene_objects = []  # All imported objects for scattering

    # If a folder is provided, import n random models
    if folder_arg:
        if os.path.isdir(folder_arg):
            clear_collection_objects('Focus_Objects')
            supported = ('.glb', '.gltf', '.fbx')
            files = [f for f in os.listdir(folder_arg) if f.lower().endswith(supported)]
            print(f"Found {len(files)} compatible files in folder: {folder_arg}", flush=True)
            
            if not files:
                print(f"No compatible files found. Supported: {supported}")
            else:
                # Select n random files (with replacement if needed)
                num_to_import = args.num_objects
                if len(files) >= num_to_import:
                    chosen_files = random.sample(files, num_to_import)
                else:
                    # If fewer files than requested, use replacement
                    chosen_files = [random.choice(files) for _ in range(num_to_import)]
                
                print(f"Importing {len(chosen_files)} objects...")
                
                coll = ensure_collection('Focus_Objects')
                
                for i, chosen in enumerate(chosen_files):
                    chosen_path = os.path.join(folder_arg, chosen)
                    print(f"Importing object {i+1}/{len(chosen_files)}: {chosen_path}")
                    
                    imported_obj = object_loader.import_object(chosen_path)
                    imported_objects = list(bpy.context.selected_objects)
                    
                    # Move imported objects into the Focus_Objects collection
                    for obj in imported_objects:
                        try:
                            if obj.name not in coll.objects:
                                coll.objects.link(obj)
                        except Exception:
                            pass
                    
                    # Preprocess (merge, scale, set origin)
                    processed_obj = object_loader.preprocess_object(imported_objects)
                    
                    if processed_obj:
                        all_scene_objects.append(processed_obj)
                
                # Select one object to be the focus object
                if all_scene_objects:
                    focus_object = random.choice(all_scene_objects)
                    print(f"Selected focus object: {focus_object.name}")
        else:
            print(f"Provided folder path does not exist: {folder_arg}")

    if not focus_object:
        print("Error: No focus object found or imported. Exiting.")
    else:
        # Scatter all objects (including focus) with minimum distance between them
        scatterer = ObjectScatterer("scatter_plane", seed=random.randint(0, 10000), min_distance=args.min_distance)
        scatterer.scatter_multiple(all_scene_objects)

        camera_spawner = CameraSpawner("look_from_volume", focus_object.name, active_cam.name, use_look_at_volume_exact_location=True)
        camera_spawner.update(random.randint(0, 10000), restore_hidden_state=True)
        
        generator = DiscreteLightGenerator()
        generator.set_seed(random.randint(0, 10000))
        generator.generate_lights(focus_object, active_cam)