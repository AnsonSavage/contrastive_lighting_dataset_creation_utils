""" A derivative of https://github.dev/allenai/objaverse-rendering/download_objaverse.py"""


import argparse
import json
import random
import os
import urllib.request
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Set

import objaverse
from tqdm import tqdm

class LocalStateManager:
    def __init__(self, output_dir: str, cache_file_path: str = "objaverse_file_sizes.jsonl"):
        self.output_dir = output_dir
        self.cache_file_path = cache_file_path
        self.file_size_cache = {}
        self.file_size_lock = threading.Lock()
        self.completed_uids = set()
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        self._load_file_size_cache()
        self._scan_completed_uids()

    def _load_file_size_cache(self):
        """Loads existing file sizes from the JSONL file into memory."""
        if not os.path.exists(self.cache_file_path):
            return

        print(f"Loading file size cache from {self.cache_file_path}...")
        count = 0
        with open(self.cache_file_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    self.file_size_cache[entry["uid"]] = entry["size_mb"]
                    count += 1
                except json.JSONDecodeError:
                    continue
        print(f"Loaded {count} entries from cache.")

    def _scan_completed_uids(self):
        """
        Scans the local directory to find UIDs that are already downloaded.
        Assumes files are saved as {uid}.glb
        """
        # List all files ending in .glb and strip the extension to get the UID
        existing_files = [
            f.split(".glb")[0] 
            for f in os.listdir(self.output_dir) 
            if f.endswith(".glb")
        ]
        self.completed_uids = set(existing_files)

    def save_file_size_entry(self, uid, size_mb):
        """Thread-safe append to the JSONL file and update memory."""
        with self.file_size_lock:
            self.file_size_cache[uid] = size_mb
            with open(self.cache_file_path, "a") as f:
                f.write(json.dumps({"uid": uid, "size_mb": size_mb}) + "\n")
    
    def get_cached_size(self, uid):
        return self.file_size_cache.get(uid)
    
    def get_file_path(self, uid):
        return os.path.join(self.output_dir, f"{uid}.glb")


def download_worker(data):
    """
    Worker function to download a single file.
    data is a tuple: (uid, url, state_manager, max_file_size_mb)
    """
    uid, url, state_manager, max_file_size_mb = data
    destination = state_manager.get_file_path(uid)

    try:
        # Double check existence inside worker to prevent race conditions or redundant work
        if os.path.exists(destination):
            return True
            
        # Check local memory cache first
        cached_size = state_manager.get_cached_size(uid)
        
        if cached_size is not None:
            # We know the size from a previous run
            if cached_size > max_file_size_mb:
                # print(f"Skipping {uid} (cached): {cached_size:.2f} MB > {max_file_size_mb} MB")
                return False
        else:
            # Not in cache, query the server
            req = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(req) as response:
                content_length = response.getheader('Content-Length')
                assert content_length is not None, "Content-Length header is missing"
                file_size_mb = int(content_length) / (1024 * 1024)
                
                # Save to cache immediately
                state_manager.save_file_size_entry(uid, file_size_mb)

                if file_size_mb > max_file_size_mb:
                    print(f"Skipping {uid}: file size {file_size_mb:.2f} MB exceeds limit of {max_file_size_mb} MB")
                    return False

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
        default=160, 
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
    parser.add_argument(
        "--max_file_size_mb",
        type=int,
        default=50,
        help="Maximum file size to download in megabytes"
    )
    
    args = parser.parse_args()
    
    # Initialize state manager
    state_manager = LocalStateManager(args.output_dir)

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
    
    # Calculate remaining work
    uids_to_download = [uid for uid in uids if uid not in state_manager.completed_uids]
    
    print(f"Found {len(state_manager.completed_uids)} existing files.")
    print(f"Remaining to download: {len(uids_to_download)}")

    # 2. Prepare URLs
    print("Resolving URLs...")
    object_paths = objaverse._load_object_paths()
    
    # Prepare list of tuples for the worker: (uid, url, state_manager, max_file_size_mb)
    download_queue = []
    for uid in uids_to_download:
        if uid in object_paths:
            url = f"https://huggingface.co/datasets/allenai/objaverse/resolve/main/{object_paths[uid]}"
            download_queue.append((uid, url, state_manager, args.max_file_size_mb))

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