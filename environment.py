"""Centralized environment variable loading & validation.

Loads .env (if present) and exposes validated absolute paths used across the
project. Import from here instead of calling dotenv.load_dotenv in multiple
modules.
"""
from __future__ import annotations
import os
import shutil
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "python-dotenv is required. Install with `pip install python-dotenv` or add it to requirements.txt"
    ) from e

# Load .env file once on import (shell env vars override .env values)
load_dotenv(override=False)

REQUIRED_VARS = ["BLENDER_PATH", "DATA_PATH"]
missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
if missing:
    raise EnvironmentError(f"Missing required environment variables: {missing}. Did you create your .env?")

BLENDER_PATH = os.getenv("BLENDER_PATH")  # type: ignore
DATA_PATH = os.getenv("DATA_PATH")  # type: ignore

# Expand ~ and resolve symlinks
BLENDER_PATH = str(Path(BLENDER_PATH).expanduser().resolve())
DATA_PATH = str(Path(DATA_PATH).expanduser().resolve())

# Validation
if not Path(BLENDER_PATH).exists():
    raise FileNotFoundError(f"BLENDER_PATH does not exist: {BLENDER_PATH}")
if not os.access(BLENDER_PATH, os.X_OK):
    # On some systems Blender may be launched via a wrapper script; we just warn if not executable.
    print(f"Warning: BLENDER_PATH is not marked executable: {BLENDER_PATH}")
if not Path(DATA_PATH).exists():
    raise FileNotFoundError(f"DATA_PATH does not exist: {DATA_PATH}")

# Helpful derived subpaths (lazy creation optional future)
SCENES_DIR = os.path.join(DATA_PATH, "scenes")
HDRI_DIR = os.path.join(DATA_PATH, "hdri")
RENDERS_DIR = os.path.join(DATA_PATH, "renders")

for d in [SCENES_DIR, HDRI_DIR, RENDERS_DIR]:
    if not Path(d).exists():  # don't auto-create yet; enforce explicit setup to catch misconfig
        # Could change to: Path(d).mkdir(parents=True, exist_ok=True)
        pass

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

__all__ = [
    "BLENDER_PATH",
    "DATA_PATH",
    "SCENES_DIR",
    "HDRI_DIR",
    "RENDERS_DIR",
    "ensure_dir",
]
