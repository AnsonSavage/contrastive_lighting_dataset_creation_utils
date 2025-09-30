# Contrastive Lighting Dataset Creation Utils

Utilities for generating and managing a contrastive lighting dataset using Blender and HDRI environments.

## Environment Configuration (.env)

This project relies on absolute paths to external resources (your Blender executable and a root data directory). To avoid hard‑coding machine‑specific paths in the codebase, we load them from a local `.env` file using [`python-dotenv`](https://github.com/theskumar/python-dotenv).

### 1. Create Your `.env`

Copy the provided example file and edit the values:

```
cp .env.example .env
```

Then open `.env` and set:

| Variable | Description | Example |
|----------|-------------|---------|
| `BLENDER_PATH` | Absolute path to the Blender binary used for headless/background rendering. | `/groups/procedural_research/blender-4.5.3-linux-x64/blender` |
| `DATA_PATH` | Root directory that contains (or will contain) subfolders like `scenes/`, `hdri/`, `renders/`, etc. | `/groups/procedural_research/data/procedural_dataset_generation_data` |

The `.env` file is **gitignored** so you can safely keep machine specific paths there.

### 2. Expected Subdirectories Under `DATA_PATH`

You can structure `DATA_PATH` like this (names may evolve):

```
DATA_PATH/
  scenes/                  # .blend scene files
  hdri/                    # Each HDRI in its own folder with resolutions + metadata JSON
  renders/                 # Generated image outputs
  metadata/                # (Optional) Central JSON indices / task definitions
  temp/                    # (Optional) Scratch / intermediate outputs
```

HDRI folders are expected to look like:
```
hdri/<hdri_name>/
  <hdri_name>_2k.exr
  <hdri_name>_4k.exr
  <hdri_name>_asset_metadata.json
  ...
```

Scene files retain their `.blend` extension (used as the scene id).

### 3. Validation
When the project imports its environment module, it will:
- Load `.env`
- Ensure `BLENDER_PATH` exists and is executable
- Ensure `DATA_PATH` exists
- (Later) Optionally create missing subfolders

### 4. Why Use `.env`?
- Keeps code portable across Linux / Windows / cluster machines
- Prevents accidental commits of local absolute paths
- Allows different Blender versions per developer
- Simplifies deployment on render nodes

## Installing Dependencies

Create / activate your virtual environment, then install requirements:

```
pip install -r requirements.txt
```

`python-dotenv` is used to load the `.env`. Other dependencies:
- `requests` (Poly Haven API downloader)
- `torch` (optional now, planned for dataset pipelines)

## Using the Environment Variables in Code

A small helper module (`environment.py`) centralizes access. Example:

```python
from environment import BLENDER_PATH, DATA_PATH

print(BLENDER_PATH)
print(DATA_PATH)
```

Downstream modules should import from `environment` instead of calling `dotenv` directly.

## Blender Usage Notes
- Some scripts are meant to be run *inside* Blender (have `import bpy`). Those can still rely on `python-dotenv` as long as the working directory includes the `.env` file (or you add its path to `sys.path`).
- Headless renders are launched via subprocess using `BLENDER_PATH`.

## Poly Haven HDRIs
Use `polyhaven_hdri_downloader.py` to populate `DATA_PATH/hdri`. Example:

```
python polyhaven_hdri_downloader.py \
  /path/to/DATA_PATH/hdri \
  kiara_1_dawn venice_sunrise abandon_building \
  --resolution 4k --format exr
```

## Future Improvements (Ideas)
- Auto-create missing subdirectories on startup
- Add CLI for validating dataset integrity
- Extend env config for cache, logs, checkpoint paths

## Troubleshooting
| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `FileNotFoundError` for Blender | Wrong `BLENDER_PATH` | Update `.env` path |
| Empty HDRI list | Incorrect `DATA_PATH/hdri` path | Verify directory & names |
| Script works locally but not on cluster | Missing `.env` on node | Copy `.env` or set shell env vars |

You can also override by exporting shell variables (they take precedence):
```
export BLENDER_PATH=/custom/blender
export DATA_PATH=/custom/data_root
```

---
Happy rendering!
