import sys
import os
import argparse
import glob
import bpy
import mathutils

# Add project root to path
sys.path.append(os.getcwd())

from camera_spawner import CameraSpawner
from discrete_light_utils import DiscreteLightGenerator, ObjectLoader, ObjectScatterer, ObjectSelector
from discrete_light_utils.collection_utils import ensure_collection, clear_collection_objects
from rendering.render_manager import RenderManager
from scene_preparation_scripts.configure_discrete_light_scene import (
    SCATTER_SURFACE_NAME,
    CAMERA_NAME,
    LOOK_FROM_VOLUME_NAME,
    FOCUS_OBJECT_NAME,
    FOCUS_OBJECTS_COLLECTION_NAME,
    BACKGROUND_OBJECTS_COLLECTION_NAME
)

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
    max_object_placement_attempts: int = 1000
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
            discrete_light_generator.align_lighting_configuration(camera, focus_object, inverse=True) # Undo the transformation done to the lights
            print("Regenerating camera position to ensure lights are visible to focus object...", flush=True)
            camera_seed += 1  # Change seed to get a new camera position
            camera_placement_attempts += 1
    
        if camera_placement_attempts >= max_camera_placement_attempts:
            print(f"Failed to place camera with visible lights after {max_camera_placement_attempts} attempts. Retrying with new focus object placement...", flush=True)
            continue # Retry placing the focus object and camera
            
    return camera_seed

def main():
    # Parse args
    raw_argv = sys.argv
    if '--' in raw_argv:
        raw_argv = raw_argv[raw_argv.index('--') + 1:]
    else:
        raw_argv = []

    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--start-seed', type=int, default=0)
    parser.add_argument('--end-seed', type=int, default=1023)
    parser.add_argument('--objects-folder', required=True, help='Path to folder containing objects')
    parser.add_argument('--num-background-objects', type=int, default=2)
    
    args = parser.parse_args(raw_argv)

    # Check for scene metadata to override settings
    import json
    scene_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    project_root = os.getcwd()
    metadata_path = os.path.join(project_root, "scene_metadata.json")
    
    num_background_objects = args.num_background_objects
    
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
    else:
        print(f"No scene_metadata.json found at {metadata_path}", flush=True)

    # Setup RenderManager
    render_manager = RenderManager()
    render_manager.set_render_settings(
        resolution=(512, 512), 
        samples=128, 
        use_gpu_rendering=True
    )

    # Ensure output dir
    os.makedirs(args.output_dir, exist_ok=True)

    # Setup ObjectScatterer
    # We need a scatter surface
    assert SCATTER_SURFACE_NAME in bpy.data.objects, f"Scatter surface '{SCATTER_SURFACE_NAME}' not found in the scene."
    object_scatterer = ObjectScatterer(scatter_plane_name=SCATTER_SURFACE_NAME, seed=0, min_distance=1.5)

    # ObjectLoader is needed for set_object_origin in find_valid_camera_and_object_placement
    object_loader = ObjectLoader()

    # Loop seeds
    for lighting_seed in range(args.start_seed, args.end_seed + 1):
        # Place Focus Object & Camera
        # We use the lighting seed as the base for other seeds to ensure determinism per lighting seed
        camera_seed = lighting_seed + 21
        scatter_seed = lighting_seed + 42
        object_selector_seed = lighting_seed + 63
        
        # Check if this render already exists before doing any work
        # We need to predict the output filename - use camera_seed as placeholder since final_camera_seed isn't known yet
        # Actually, since final_camera_seed can change, we use a pattern match instead
        blend_file_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
        # Check for any file matching this lighting seed pattern
        expected_pattern = f"{blend_file_name}_cam_*_light_{lighting_seed}_scatter_{scatter_seed}_objsel_{object_selector_seed}.png"
        existing_files = glob.glob(os.path.join(args.output_dir, expected_pattern))
        if existing_files:
            print(f"Skipping seed {lighting_seed}: render already exists at {existing_files[0]}", flush=True)
            continue
        
        print(f"Processing seed {lighting_seed}...", flush=True)
        
        # 1. Lighting Config
        discrete_light_generator = DiscreteLightGenerator(seed=lighting_seed)
        discrete_light_generator.generate_light_configuration()

        # 2. Build Scene
        # Clear previous objects
        clear_collection_objects(FOCUS_OBJECTS_COLLECTION_NAME)
        clear_collection_objects(BACKGROUND_OBJECTS_COLLECTION_NAME)
        object_scatterer.reset_positions()

        # Load Focus Object
        object_selector = ObjectSelector(args.objects_folder, object_loader, seed=object_selector_seed) # TODO: you can adjust max file size when you run this
        focus_object = object_selector.load_object()
            
        focus_object.name = FOCUS_OBJECT_NAME
        focus_objects_collection = ensure_collection(FOCUS_OBJECTS_COLLECTION_NAME)
        focus_objects_collection.objects.link(focus_object)
        
        # Update scatterer seed
        object_scatterer.set_seed(scatter_seed)
        
        try:
            final_camera_seed = find_valid_camera_and_object_placement(
                object_loader,
                object_scatterer,
                focus_object,
                discrete_light_generator,
                max_camera_placement_attempts=1000,
                max_camera_distance=9.0,
                camera_seed=camera_seed,
                camera_name=CAMERA_NAME,
                look_from_volume_name=LOOK_FROM_VOLUME_NAME,
                focus_object_name=focus_object.name
            )
        except RuntimeError as e:
            print(f"Skipping seed {lighting_seed}: {e}")
            continue
            
        # Register placed focus object so background objects don't overlap
        object_scatterer.register_placed_object(focus_object)
        
        # Place Background Objects
        background_objects_collection = ensure_collection(BACKGROUND_OBJECTS_COLLECTION_NAME)
        placed_background_count = 0
        max_background_placement_attempts = 50
        
        for i in range(num_background_objects):
            # Load a new background object
            try:
                bg_object = object_selector.load_object()
                if bg_object is None:
                    print(f"Warning: Failed to load background object {i+1}, skipping.", flush=True)
                    continue
            except Exception as e:
                print(f"Warning: Exception loading background object {i+1}: {e}", flush=True)
                continue
            
            bg_object.name = f"background_object_{i}"
            background_objects_collection.objects.link(bg_object)
            
            object_loader.set_object_origin(bg_object)
            
            # Try to place the object without bbox intersection and without obstructing lighting
            bg_obj_placement_attempts = 0
            placement_success = False
            
            while bg_obj_placement_attempts < max_background_placement_attempts:
                bg_obj_placement_attempts += 1
                
                # Attempt to place with bbox collision checking
                scatter_success = object_scatterer.scatter_and_rotate(bg_object)
                
                if not scatter_success:
                    print(f"Could not place background object {i+1} without bbox intersection after {bg_obj_placement_attempts} attempts.", flush=True)
                    continue
                
                # Verify this object doesn't obstruct any light to the focus object
                if discrete_light_generator.check_object_obstructs_lighting(bg_object, focus_object):
                    print(f"Background object {i+1} obstructs lighting, re-scattering (attempt {bg_obj_placement_attempts})...", flush=True)
                    # Remove from scatterer tracking so we can try again
                    object_scatterer.unregister_placed_object(bg_object)
                    continue
                
                # Successfully placed
                placement_success = True
                break
            
            if not placement_success:
                print(f"Could not place background object {i+1} after {max_background_placement_attempts} attempts, removing.", flush=True)
                object_scatterer.unregister_placed_object(bg_object)
                bpy.data.objects.remove(bg_object, do_unlink=True)
                continue
            
            placed_background_count += 1
            print(f"Successfully placed background object {i+1}.", flush=True)

        # 3. Render
        output_filename = create_file_output_name(
            camera_seed=final_camera_seed,
            ligting_seed=lighting_seed,
            scatter_seed=scatter_seed,
            object_selector_seed=object_selector_seed
        )
        output_path = os.path.join(args.output_dir, output_filename)
        
        # Set camera
        camera = bpy.data.objects.get(CAMERA_NAME)
        
        # Set DOF
        if camera:
            camera.data.dof.use_dof = True
            camera.data.dof.focus_object = focus_object
            camera.data.dof.aperture_fstop = 0.5

        render_manager.set_camera(camera)
        render_manager.render(output_path=output_path)

if __name__ == "__main__":
    main()
