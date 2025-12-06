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

def render_exists(output_dir, lighting_seed, scatter_seed, object_selector_seed):
    blend_file_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    expected_pattern = (
        f"{blend_file_name}_cam_*_light_{lighting_seed}_scatter_"
        f"{scatter_seed}_objsel_{object_selector_seed}.png"
    )
    existing = glob.glob(os.path.join(output_dir, expected_pattern))
    if existing:
        print(
            f"Skipping seed {lighting_seed}: render already exists at {existing[0]}",
            flush=True,
        )
        return True
    return False

def find_valid_camera_and_object_placement(
    object_loader: ObjectLoader,
    object_scatterer: ObjectScatterer,
    focus_object: bpy.types.Object,
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
        def pass_criteria(look_from, look_at):
            # Ensure the camera is at least 1 unit away from the focus object
            direction = (look_at - look_from).normalized()
            distance = (look_from - look_at).length
            looking_straight_down = mathutils.Vector((0, 0, -1)).dot(direction) > 0.6
            looking_straight_up = mathutils.Vector((0, 0, 1)).dot(direction) > 0.6
            return distance >= 1.0 and distance <= max_camera_distance and not looking_straight_down and not looking_straight_up
        
        try:
            camera_spawner.update(update_seed=camera_seed, pass_criteria=pass_criteria, required_visible_target_name=focus_object_name, restore_hidden_state=True, required_percentage_of_surface_visible=0.6, max_attempts=max_camera_placement_attempts) # Place the camera where it can see the focus object
        except RuntimeError as e:
            continue
        camera_and_object_placement_good = True
            
    return camera_seed

def get_metadata(path: str) -> dict:
    if os.path.exists(path):
        import json
        with open(path, 'r') as f:
            return json.load(f)
    return {}

def place_background_objects(
    object_selector: ObjectSelector,
    object_loader: ObjectLoader,
    object_scatterer: ObjectScatterer,
    num_background_objects: int,
    max_placement_attempts: int = 50
) -> list:
    """
    Place background objects in the scene while avoiding overlaps and lighting obstruction.
    
    Args:
        object_selector: Object selector for loading objects
        object_loader: Object loader for setting origins
        object_scatterer: Object scatterer for placing objects
        focus_object: The focus object in the scene
        discrete_light_generator: Discrete light generator for lighting checks
        num_background_objects: Target number of background objects to place
        max_placement_attempts: Maximum attempts per object placement
    
    Returns:
        list: List of successfully placed background objects
    """
    clear_collection_objects(BACKGROUND_OBJECTS_COLLECTION_NAME)
    background_objects_collection = ensure_collection(BACKGROUND_OBJECTS_COLLECTION_NAME)
    placed_background_objects = []
    
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
        
        while bg_obj_placement_attempts < max_placement_attempts:
            bg_obj_placement_attempts += 1
            
            # Attempt to place with bbox collision checking
            scatter_success = object_scatterer.scatter_and_rotate(bg_object)
            
            if not scatter_success:
                print(f"Could not place background object {i+1} without bbox intersection after {bg_obj_placement_attempts} attempts.", flush=True)
                continue
            
            # Successfully placed
            placement_success = True
            break
        
        if not placement_success:
            print(f"Could not place background object {i+1} after {max_placement_attempts} attempts, removing.", flush=True)
            object_scatterer.unregister_placed_object(bg_object)
            bpy.data.objects.remove(bg_object, do_unlink=True)
            # If we can't place an object, return what we have so far to avoid infinite loops or weird states
            return placed_background_objects
        
        placed_background_objects.append(bg_object)
        print(f"Successfully placed background object {i+1}.", flush=True)
    
    return placed_background_objects

def main():
    # Parse args
    raw_argv = sys.argv
    if '--' in raw_argv:
        raw_argv = raw_argv[raw_argv.index('--') + 1:]
    else:
        raw_argv = []

    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--num-content-locks', type=int, default=0)
    parser.add_argument('--start-seed', type=int, default=0)
    parser.add_argument('--end-seed', type=int, default=1023)
    parser.add_argument('--objects-folder', required=True, help='Path to folder containing objects')
    parser.add_argument('--num-background-objects', type=int, default=2)
    parser.add_argument('--min-object-height', type=float, default=0.5, help='Minimum height of the object bounding box (default: 0.5)')
    parser.add_argument('--min-object-width', type=float, default=0.1, help='Minimum width/depth of the object bounding box (default: 0.1)')
    parser.add_argument('--min-passing-lighting-percentage', type=float, default=0.85, help='Minimum percentage of lighting seeds that must pass validation (0.0-1.0, default: 0.85). Set to 1.0 for all seeds to pass.')
    
    args = parser.parse_args(raw_argv)

    # Check for scene metadata to override settings
    import json
    scene_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    project_root = os.getcwd()
    metadata_path = os.path.join(project_root, "scene_metadata.json")
    
    num_background_objects = args.num_background_objects
    
    metadata = get_metadata(metadata_path)
    if scene_name in metadata:
        scene_data = metadata[scene_name]
        if "num_background_objects" in scene_data:
            print(
                f"Overriding num_background_objects from metadata for scene '{scene_name}': "
                f"{scene_data['num_background_objects']}",
                flush=True,
            )
            num_background_objects = scene_data["num_background_objects"]

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
    assert SCATTER_SURFACE_NAME in bpy.data.objects, f"Scatter surface '{SCATTER_SURFACE_NAME}' not found in the scene."
    object_scatterer = ObjectScatterer(scatter_plane_name=SCATTER_SURFACE_NAME, seed=0, min_distance=1.5)

    # ObjectLoader is needed for set_object_origin in find_valid_camera_and_object_placement
    object_loader = ObjectLoader()

    # Loop seeds
    num_content_locks = args.num_content_locks
    camera_seed = 21
    scatter_seed = 42
    object_selector_seed = 63
    camera = bpy.data.objects.get(CAMERA_NAME)
    assert camera is not None, f"Camera '{CAMERA_NAME}' not found in the scene."

    for _ in range(num_content_locks):
        is_content_such_that_lighting_works = False
        content_generation_attempts = 0
        max_content_generation_attempts = 100  # Prevent infinite loops

        while not is_content_such_that_lighting_works:
            content_generation_attempts += 1
            if content_generation_attempts > max_content_generation_attempts:
                print(f"Failed to generate valid content after {max_content_generation_attempts} attempts. Skipping this content lock.", flush=True)
                break

            camera_seed += 1
            scatter_seed += 1
            object_selector_seed += 1

            clear_collection_objects(FOCUS_OBJECTS_COLLECTION_NAME)
            clear_collection_objects(BACKGROUND_OBJECTS_COLLECTION_NAME)
            object_scatterer.reset_positions()

            # Load Focus Object
            object_selector = ObjectSelector(args.objects_folder, object_loader, min_height=args.min_object_height, min_width=args.min_object_width, seed=object_selector_seed) # TODO: you can adjust max file size when you run this
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
                    max_camera_placement_attempts=100,
                    max_camera_distance=9.0,
                    camera_seed=camera_seed,
                    camera_name=CAMERA_NAME,
                    look_from_volume_name=LOOK_FROM_VOLUME_NAME,
                    focus_object_name=focus_object.name,
                    max_object_placement_attempts=100
                )
            except RuntimeError as e:
                print(f"Unable to find camera placement for current focus object: {e}", flush=True)
                continue

            # Place Background Objects
            placed_background_objects = place_background_objects(
                object_selector=object_selector,
                object_loader=object_loader,
                object_scatterer=object_scatterer,
                num_background_objects=num_background_objects,
                max_placement_attempts=50
            )

            # Check if we placed enough objects (optional strict check)
            if len(placed_background_objects) < num_background_objects:
                print(f"Only placed {len(placed_background_objects)}/{num_background_objects} background objects. Retrying content...", flush=True)
                continue

            # See if we can sweep all the lighting configurations and still have visible lighting
            passing_lighting_seeds = 0
            total_lighting_seeds = args.end_seed - args.start_seed + 1
            min_passing_seeds = int(total_lighting_seeds * args.min_passing_lighting_percentage)
            
            for lighting_seed in range(args.start_seed, args.end_seed + 1):
                discrete_light_generator = DiscreteLightGenerator(seed=lighting_seed)
                discrete_light_generator.generate_light_configuration()
                discrete_light_generator.align_lighting_configuration(camera, focus_object)
                
                # Check if lighting is visible to focus object
                if not discrete_light_generator.verify_lighting_visible_to_target(focus_object):
                    print(f"Lighting seed {lighting_seed} not visible to focus object with current content.", flush=True)
                    continue
                
                # Check if background objects obstruct lighting
                objects_obstruct = False
                for obj in placed_background_objects:
                    if discrete_light_generator.check_object_obstructs_lighting(obj, focus_object):
                        print(f"Background object '{obj.name}' obstructs lighting for seed {lighting_seed}.", flush=True)
                        objects_obstruct = True
                        break
                
                if not objects_obstruct:
                    passing_lighting_seeds += 1
            
            # Check if we meet the minimum passing percentage
            if passing_lighting_seeds >= min_passing_seeds:
                print(f"Content validated: {passing_lighting_seeds}/{total_lighting_seeds} lighting seeds pass ({100.0 * passing_lighting_seeds / total_lighting_seeds:.1f}%, required {100.0 * args.min_passing_lighting_percentage:.1f}%)", flush=True)
                is_content_such_that_lighting_works = True
            else:
                print(f"Content rejected: only {passing_lighting_seeds}/{total_lighting_seeds} lighting seeds pass ({100.0 * passing_lighting_seeds / total_lighting_seeds:.1f}%, required {100.0 * args.min_passing_lighting_percentage:.1f}%). Retrying content...", flush=True)
                is_content_such_that_lighting_works = False
        
        if not is_content_such_that_lighting_works:
            print(f"Could not find valid content for this lock after {max_content_generation_attempts} attempts, moving to next lock.", flush=True)
            continue # Could not find valid content for this lock, move to next

        # At this point, we know that the current content works for the required percentage of lighting seeds. So now we'll render for each seed
        for lighting_seed in range(args.start_seed, args.end_seed + 1):
            if render_exists(args.output_dir, lighting_seed, scatter_seed, object_selector_seed):
                continue

            print(f"Processing seed {lighting_seed}...", flush=True)
            
            # 1. Lighting Config
            discrete_light_generator = DiscreteLightGenerator(seed=lighting_seed)
            discrete_light_generator.generate_light_configuration()
            discrete_light_generator.align_lighting_configuration(camera, focus_object)

            # 3. Render
            output_filename = create_file_output_name(
                camera_seed=final_camera_seed,
                ligting_seed=lighting_seed,
                scatter_seed=scatter_seed,
                object_selector_seed=object_selector_seed
            )
            output_path = os.path.join(args.output_dir, output_filename)
            
            # Set DOF
            camera.data.dof.use_dof = True
            camera.data.dof.focus_object = focus_object
            camera.data.dof.aperture_fstop = 0.5

            render_manager.set_camera(camera)
            render_manager.render(output_path=output_path)

if __name__ == "__main__":
    main()
