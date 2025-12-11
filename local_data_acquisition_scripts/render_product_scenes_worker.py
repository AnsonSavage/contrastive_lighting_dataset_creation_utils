import os
import sys
import argparse
import glob
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from environment import PRODUCT_SCENES_DIR, DATA_PATH
from blender_manager import BlenderManager


def compute_shard_work(scene_files: list[str], shard_index: int, shard_count: int, seeds_per_scene: int = 1024) -> list[tuple[str, int, int]]:
    # TODO: it has no sense of which items have already been completed.
    """
    Compute which (scene, start_seed, end_seed) tuples this shard should process.
    
    Distributes work evenly across shards. If there are more shards than scenes,
    the seed ranges get split across multiple shards for the same scene.
    
    Returns:
        List of (scene_path, start_seed, end_seed) tuples for this shard.
    """
    num_scenes = len(scene_files)
    if num_scenes == 0:
        return []
    
    # Total work units (each seed for each scene is one unit)
    total_work = num_scenes * seeds_per_scene
    
    # Divide work evenly
    work_per_shard = total_work // shard_count
    remainder = total_work % shard_count
    
    # Calculate this shard's start and end work indices
    # Shards with index < remainder get one extra work unit
    if shard_index < remainder:
        my_start = shard_index * (work_per_shard + 1)
        my_end = my_start + work_per_shard + 1
    else:
        my_start = remainder * (work_per_shard + 1) + (shard_index - remainder) * work_per_shard
        my_end = my_start + work_per_shard
    
    # Convert work indices to (scene, seed) pairs
    result = []
    for work_idx in range(my_start, my_end):
        scene_idx = work_idx // seeds_per_scene
        seed_idx = work_idx % seeds_per_scene
        
        # Check if we're starting a new scene or continuing
        if not result or result[-1][0] != scene_files[scene_idx]:
            # New scene entry
            result.append((scene_files[scene_idx], seed_idx, seed_idx))
        else:
            # Extend the seed range for the current scene
            scene_path, start_seed, _ = result[-1]
            result[-1] = (scene_path, start_seed, seed_idx)
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Render product scenes worker")
    parser.add_argument('--shard-index', type=int, default=0, help='Index of the current shard (0-based).')
    parser.add_argument('--shard-count', type=int, default=1, help='Total number of shards.')
    parser.add_argument('--seeds-per-scene', type=int, default=1024, help='Number of lighting seeds per scene.')
    parser.add_argument('--output-dir-name', type=str, default='product', help='Name of the output directory within DATA_PATH/renders.')
    parser.add_argument('--num-content-locks', type=int, default=15, help='Number of content configurations (different object placements) per scene.')
    parser.add_argument('--render-aovs', action='store_true', help='If set, render AOVs (one set per content key, not per lighting key).')
    parser.add_argument('--aovs', nargs='+', default=['metallic', 'albedo', 'roughness', 'normal'],
                        help='List of AOVs to render (default: metallic albedo roughness normal)')
    parser.add_argument('--material-library', type=str, default=None, help='Path to the material library .blend file')
    parser.add_argument('--min-passing-lighting-percentage', type=float, default=0.85, help='Minimum percentage of lighting seeds that must pass validation (0.0-1.0, default: 0.85). Set to 1.0 for all seeds to pass.')
    args = parser.parse_args()

    # List all .blend files in PRODUCT_SCENES_DIR
    assert os.path.exists(PRODUCT_SCENES_DIR), f"PRODUCT_SCENES_DIR does not exist: {PRODUCT_SCENES_DIR}"

    scene_files = sorted(glob.glob(os.path.join(PRODUCT_SCENES_DIR, "*.blend")))
    assert scene_files, f"No .blend files found in PRODUCT_SCENES_DIR: {PRODUCT_SCENES_DIR}"

    # Compute work for this shard
    my_work = compute_shard_work(scene_files, args.shard_index, args.shard_count, args.seeds_per_scene)
    
    total_seeds = sum(end - start + 1 for _, start, end in my_work)
    print(f"Shard {args.shard_index}/{args.shard_count} processing {len(my_work)} scene segment(s), {total_seeds} total seeds.")
    for scene_path, start_seed, end_seed in my_work:
        print(f"  - {Path(scene_path).stem}: seeds {start_seed}-{end_seed}")

    blender_manager = BlenderManager()
    script_path = os.path.join("local_data_acquisition_scripts", "render_product_scene_blender_maintain_content.py")
    objects_folder = os.path.join(DATA_PATH, "obj", "objaverse")

    for scene_path, start_seed, end_seed in my_work:
        print(f"Processing scene: {scene_path} (seeds {start_seed}-{end_seed})")
        
        scene_name = Path(scene_path).stem
        output_dir = os.path.join(DATA_PATH, "renders", args.output_dir_name, scene_name)

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Call Blender with the worker script
        blender_args = [
            f'--output-dir={output_dir}',
            f'--num-content-locks={args.num_content_locks}',
            f'--start-seed={start_seed}',
            f'--end-seed={end_seed}',
            f'--min-passing-lighting-percentage={args.min_passing_lighting_percentage}',
            f'--objects-folder={objects_folder}'
        ]
        
        # Add material library argument if provided
        if args.material_library:
            blender_args.append(f'--material-library={args.material_library}')
        
        # Add AOV arguments if requested
        if args.render_aovs:
            blender_args.append('--render-aovs')
            blender_args.extend(['--aovs'] + args.aovs)
        
        blender_manager.open_blender_file_with_args(
            file_path=scene_path,
            python_script_path=script_path,
            args_for_python_script=blender_args,
            background=True
        )

if __name__ == "__main__":
    main()
