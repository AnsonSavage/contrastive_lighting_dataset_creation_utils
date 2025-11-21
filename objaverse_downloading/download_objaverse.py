""" A derivative of https://github.dev/allenai/objaverse-rendering/download_objaverse.py"""


import argparse
import json
import random
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Set

import objaverse
from tqdm import tqdm

def get_completed_uids(directory: str) -> Set[str]:
    """
    Scans the local directory to find UIDs that are already downloaded.
    Assumes files are saved as {uid}.glb
    """
    if not os.path.exists(directory):
        os.makedirs(directory)
        return set()

    # List all files ending in .glb and strip the extension to get the UID
    existing_files = [
        f.split(".glb")[0] 
        for f in os.listdir(directory) 
        if f.endswith(".glb")
    ]
    return set(existing_files)


def download_worker(data):
    """
    Worker function to download a single file.
    data is a tuple: (uid, url, output_dir)
    """
    uid, url, output_dir = data
    destination = os.path.join(output_dir, f"{uid}.glb")

    try:
        # Double check existence inside worker to prevent race conditions or redundant work
        if os.path.exists(destination):
            return True
            
        urllib.request.urlretrieve(url, destination)
        return True
    except Exception as e:
        # You might want to log this to a file if you are downloading millions of objects
        # print(f"Failed to download {uid}: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Objaverse models locally.")
    
    parser.add_argument(
        "--output_dir", 
        type=str, 
        default="./downloaded_models", 
        help="Directory to save the models"
    )
    parser.add_argument(
        "--num_threads", 
        type=int, 
        default=16, 
        help="Number of concurrent download threads"
    )
    parser.add_argument(
        "--start_i", 
        type=int, 
        default=0, 
        help="Index to start at (useful for splitting across machines)"
    )
    parser.add_argument(
        "--end_i", 
        type=int, 
        default=-1, 
        help="Index to end at (-1 for all)"
    )
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    print("Loading Objaverse UIDs...")
    uids = objaverse.load_uids()

    # Deterministic shuffle so start_i/end_i are consistent across runs
    random.seed(42)
    random.shuffle(uids)

    # Handle slicing
    end_index = args.end_i if args.end_i != -1 else len(uids)
    uids = uids[args.start_i : end_index]
    
    print(f"Processing range: {args.start_i} to {end_index} ({len(uids)} items)")

    # 1. Filter out already downloaded files
    print("Checking for existing files...")
    completed_uids = get_completed_uids(args.output_dir)
    
    # Calculate remaining work
    uids_to_download = [uid for uid in uids if uid not in completed_uids]
    
    print(f"Found {len(completed_uids)} existing files.")
    print(f"Remaining to download: {len(uids_to_download)}")

    # 2. Prepare URLs
    print("Resolving URLs...")
    object_paths = objaverse._load_object_paths()
    
    # Prepare list of tuples for the worker: (uid, url, output_dir)
    download_queue = []
    for uid in uids_to_download:
        if uid in object_paths:
            url = f"https://huggingface.co/datasets/allenai/objaverse/resolve/main/{object_paths[uid]}"
            download_queue.append((uid, url, args.output_dir))

    # 3. Update the JSON manifest 
    current_urls = [item[1] for item in download_queue]
    with open("input_models_path.json", "w") as f:
        json.dump(current_urls, f, indent=2)

    # 4. Start Downloading
    if not download_queue:
        print("Everything in this range is already downloaded!")
    else:
        print(f"Starting download with {args.num_threads} threads...")
        
        with ThreadPoolExecutor(max_workers=args.num_threads) as executor:
            results = list(tqdm(
                executor.map(download_worker, download_queue), 
                total=len(download_queue),
                unit="obj"
            ))

    print("Done!")