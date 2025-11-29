import os
import sys
import argparse
import glob
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from environment import PRODUCT_SCENES_DIR, DATA_PATH
from blender_manager import BlenderManager

def main():
    parser = argparse.ArgumentParser(description="Render product scenes worker")
    parser.add_argument('--shard-index', type=int, default=0, help='Index of the current shard (0-based).')
    parser.add_argument('--shard-count', type=int, default=1, help='Total number of shards.')
    args = parser.parse_args()

    # List all .blend files in PRODUCT_SCENES_DIR
    if not os.path.exists(PRODUCT_SCENES_DIR):
        print(f"Warning: PRODUCT_SCENES_DIR does not exist: {PRODUCT_SCENES_DIR}")
        return

    scene_files = sorted(glob.glob(os.path.join(PRODUCT_SCENES_DIR, "*.blend")))
    if not scene_files:
        print(f"No .blend files found in {PRODUCT_SCENES_DIR}")
        return

    # Distribute scenes across shards
    # We want to distribute the work evenly.
    # If we have fewer scenes than shards, some shards will be idle.
    # If we have many scenes, we split them.
    
    my_scenes = [s for i, s in enumerate(scene_files) if i % args.shard_count == args.shard_index]
    
    print(f"Shard {args.shard_index}/{args.shard_count} processing {len(my_scenes)} scenes out of {len(scene_files)} total.")

    blender_manager = BlenderManager()
    script_path = os.path.join("local_data_acquisition_scripts", "render_product_scene_blender.py")
    objects_folder = os.path.join(DATA_PATH, "obj", "objaverse")

    for scene_path in my_scenes:
        print(f"Processing scene: {scene_path}")
        
        scene_name = Path(scene_path).stem
        output_dir = os.path.join("contrastive_data", "renders", "product", scene_name)
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Call Blender with the worker script
        # We loop seeds 0-1023
        blender_manager.open_blender_file_with_args(
            file_path=scene_path,
            python_script_path=script_path,
            args_for_python_script=[
                f'--output-dir={output_dir}',
                '--start-seed=0',
                '--end-seed=1023',
                f'--objects-folder={objects_folder}'
            ],
            background=True
        )

if __name__ == "__main__":
    main()
