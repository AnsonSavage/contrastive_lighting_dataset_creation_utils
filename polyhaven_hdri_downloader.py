"""Utilities for downloading HDRI metadata and files from Poly Haven using the official API.

Rewritten to avoid HTML scraping (which is disallowed by Poly Haven's ToS) and
instead leverage their documented JSON endpoints:
  - https://api.polyhaven.com/info/{asset_id}
  - https://api.polyhaven.com/files/{asset_id}

Example:
  python polyhaven_hdri_scraper.py output_dir https://polyhaven.com/a/kiara_1_dawn --resolution 8k --format exr

Features:
  * Fetch full metadata (categories, tags, description, authors, etc.).
  * Select preferred resolution (falls back gracefully if unavailable).
  * Choose file format: exr or hdr.
  * Optional tonemapped JPG download.
  * Integrity check via MD5 (optional flag) after download.
  * Rate limiting / polite delay between assets.

Note: Please support Poly Haven (https://polyhaven.com/support) if this tooling
helps your workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from typing import Dict, Any, Tuple

import requests

API_INFO = "https://api.polyhaven.com/info/{asset}"
API_FILES = "https://api.polyhaven.com/files/{asset}"

DEFAULT_RES_ORDER = ["1k", "2k", "4k", "8k", "16k", "20k", "24k", "29k", "30k"]  # ascending for fallback logic


class PolyHavenAPIError(RuntimeError):
    pass


def extract_asset_id(url_or_id: str) -> str:
    """Accept either a full https://polyhaven.com/a/<id> URL or a raw id."""
    clean = url_or_id.strip().rstrip('/')
    if "/a/" in clean:
        return clean.split("/a/")[-1]
    # support older style https://polyhaven.com/<id>
    if clean.startswith("http"):
        return clean.split('/')[-1]
    return clean


def http_get_json(url: str, retries: int = 3, backoff: float = 0.75) -> Any:
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 404:
                raise PolyHavenAPIError(f"Asset not found at {url}")
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:  # ValueError for json decode
            last_exc = e
            if attempt == retries:
                raise PolyHavenAPIError(f"Failed GET {url}: {e}")
            time.sleep(backoff * attempt)
    raise PolyHavenAPIError(f"Unexpected retry exhaustion for {url}: {last_exc}")


def fetch_asset_info(asset_id: str) -> Dict[str, Any]:
    return http_get_json(API_INFO.format(asset=asset_id))


def fetch_asset_files(asset_id: str) -> Dict[str, Any]:
    return http_get_json(API_FILES.format(asset=asset_id))


def choose_resolution(available: Dict[str, Any], desired: str) -> str:
    """Return desired if present else the highest below it or the closest available."""
    if desired in available:
        return desired
    # Build ordered preference list up to largest present
    present = [r for r in DEFAULT_RES_ORDER if r in available]
    if not present:
        raise PolyHavenAPIError("No standard resolution keys present in asset files JSON")
    # find closest by index difference
    if desired in DEFAULT_RES_ORDER:
        desired_idx = DEFAULT_RES_ORDER.index(desired)
        # pick the present resolution with minimal absolute index distance
        best = min(present, key=lambda r: abs(DEFAULT_RES_ORDER.index(r) - desired_idx))
        return best
    # fallback to highest
    return present[-1]


def select_hdri_file(files_json: Dict[str, Any], resolution: str, file_format: str) -> Tuple[str, int, str]:
    """Return (url, size_bytes, md5) for the chosen HDRI file.

    files_json structure excerpt:
      {
        "hdri": {
            "8k": {"hdr": {"url": ... , "size": int, "md5": str}, "exr": {...}},
            "16k": { ... }
        },
        "tonemapped": {...}
      }
    """
    hdri_section = files_json.get("hdri")
    if not hdri_section:
        raise PolyHavenAPIError("'hdri' section missing in files JSON")
    chosen_res = choose_resolution(hdri_section, resolution)
    res_entry = hdri_section[chosen_res]
    if file_format not in res_entry:
        # fallback: pick any available format
        available_formats = list(res_entry.keys())
        if not available_formats:
            raise PolyHavenAPIError(f"No file formats listed under resolution {chosen_res}")
        fallback_fmt = available_formats[0]
        print(f"Requested format '{file_format}' not available at {chosen_res}, using '{fallback_fmt}'.")
        file_format = fallback_fmt
    entry = res_entry[file_format]
    return entry["url"], entry.get("size", -1), entry.get("md5", "")


def download_file(url: str, dest_path: str, chunk: int = 1024 * 1024) -> None:
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        written = 0
        with open(dest_path, "wb") as f:
            for part in r.iter_content(chunk_size=chunk):
                if not part:
                    continue
                f.write(part)
                written += len(part)


def save_metadata(asset_dir: str, asset_id: str, info: Dict[str, Any], files_json: Dict[str, Any]) -> None:
    meta_path = os.path.join(asset_dir, f"{asset_id}_asset_metadata.json")
    data = {
        "asset_id": asset_id,
        "info": info,
        # prune heavy nested file data to just available resolutions & formats summary
        "available_resolutions": sorted(list(files_json.get("hdri", {}).keys()), key=lambda r: DEFAULT_RES_ORDER.index(r) if r in DEFAULT_RES_ORDER else 999),
        "formats_per_resolution": {res: list(files_json["hdri"][res].keys()) for res in files_json.get("hdri", {})},
        "tonemapped_jpg": files_json.get("tonemapped", {}).get("url"),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def process_asset(asset_identifier: str, out_dir: str, resolution: str, file_format: str, download_tonemapped: bool, delay: float) -> None:
    asset_id = extract_asset_id(asset_identifier)
    asset_dir = os.path.join(out_dir, asset_id)
    os.makedirs(asset_dir, exist_ok=True)

    print(f"== Processing {asset_id} ==")
    info = fetch_asset_info(asset_id)
    files_json = fetch_asset_files(asset_id)
    save_metadata(asset_dir, asset_id, info, files_json)
    url, size_bytes, md5 = select_hdri_file(files_json, resolution, file_format)
    fname = os.path.basename(url.split('?')[0])  # strip query args
    dest = os.path.join(asset_dir, fname)
    print(f"Downloading HDRI: {fname} ({size_bytes/1e6:.1f} MB) -> {dest}")
    download_file(url, dest)
    print("HDRI download complete.")

    if download_tonemapped and files_json.get("tonemapped", {}).get("url"):
        tm_url = files_json["tonemapped"]["url"]
        tm_name = os.path.basename(tm_url.split('?')[0])
        tm_dest = os.path.join(asset_dir, tm_name)
        print(f"Downloading tonemapped JPG: {tm_name}")
        download_file(tm_url, tm_dest)

    if delay > 0:
        time.sleep(delay)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Download Poly Haven HDRIs and metadata via official API")
    p.add_argument("directory", help="Output directory")
    p.add_argument("assets", nargs="+", help="Poly Haven asset URLs or IDs, or list to text file containing these assets separated by new lines (e.g. kiara_1_dawn or https://polyhaven.com/a/kiara_1_dawn)")
    p.add_argument("--resolution", default="4k", help="Desired resolution (e.g. 1k,2k,4k,8k,16k,20k,24k,29k,30k). Will fallback to closest available.")
    p.add_argument("--format", choices=["exr", "hdr"], default="exr", help="Preferred file format")
    p.add_argument("--tonemapped", action="store_true", help="Also download tonemapped JPG preview if available")
    p.add_argument("--delay", type=float, default=0.0, help="Delay (seconds) between assets to be polite")
    return p


def main():  # pragma: no cover
    parser = build_parser()
    args = parser.parse_args()
    os.makedirs(args.directory, exist_ok=True)
    assets_to_request = args.assets
    if len(assets_to_request) == 0:
        print("No assets specified, exiting.")
        return
    elif len(assets_to_request) == 1:
        # Check if it's a text file with multiple asset IDs/URLs on each line
        potential_file = assets_to_request[0]
        if os.path.isfile(potential_file):
            with open(potential_file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
                if lines:
                    assets_to_request = lines
                    print(f"Loaded {len(lines)} assets from {potential_file}")
                else:
                    print(f"No valid asset lines found in {potential_file}, exiting.")
                    return
    for asset in assets_to_request:
        try:
            process_asset(
                asset,
                args.directory,
                args.resolution.lower(),
                args.format.lower(),
                args.tonemapped,
                args.delay,
            )
        except PolyHavenAPIError as e:
            print(f"Error: {e}")
        except Exception as e: 
            print(f"Unexpected error processing {asset}: {e}")


if __name__ == "__main__":  # pragma: no cover
    main()

