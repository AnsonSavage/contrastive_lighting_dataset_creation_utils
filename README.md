# Contrastive Lighting Dataset Creation Utils

Utilities for generating and managing a contrastive lighting dataset using Blender and HDRI environments. This codebase is designed to procedurally generate synthetic images with varying lighting, camera angles, and object placements for machine learning tasks.

## Environment Configuration (.env)

This project relies on absolute paths to external resources (your Blender executable and a root data directory). To avoid hard‑coding machine‑specific paths in the codebase, we load them from a local `.env` file using [`python-dotenv`](https://github.com/theskumar/python-dotenv).

### 1. Create Your `.env`

Copy the provided example file and edit the values:

```bash
cp .env.example .env
```

Then open `.env` and set:

| Variable | Description | Example |
|----------|-------------|---------|
| `BLENDER_PATH` | Absolute path to the Blender binary used for headless/background rendering. | `/groups/procedural_research/blender-4.5.3-linux-x64/blender` |
| `DATA_PATH` | Root directory that contains (or will contain) subfolders like `scenes/`, `hdri/`, `renders/`, etc. | `/groups/procedural_research/data/procedural_dataset_generation_data` |
| `PRODUCT_SCENES_DIR` | Directory containing the base `.blend` files for product scenes. | `/home/user/my_product_scenes` |

The `.env` file is **gitignored** so you can safely keep machine specific paths there.

Note however that this .env can't be properly loaded from within some Blender scripts due to how Blender manages its Python environment. In those cases, these environment paths are set in the SLURM submission script (e.g., `render_product_scenes.sh`, `render_using_multiple_nodes.sh`, etc.).

### 2. Expected Subdirectories Under `DATA_PATH`

You can structure `DATA_PATH` like this (names may evolve):

```
DATA_PATH/
  scenes/outdoor/          # .blend scene files
  scenes/product/          # .blend scene files
  hdri/                    # Each HDRI in its own folder with resolutions + metadata JSON
  renders/                 # Generated image outputs
  obj/                     # 3D Object assets (e.g. Objaverse)
```

## Main Functionalities

### Product Scene Rendering Pipeline

One functionality of this repository is the "Product Scene" rendering pipeline, which generates thousands of variations of base scenes by randomizing lighting, camera positions, and background objects.

#### Workflow

1.  **Submission**: The process starts with `local_data_acquisition_scripts/render_product_scenes.sh`. This is a SLURM submission script that launches an array job.
2.  **Orchestration**: The shell script runs `local_data_acquisition_scripts/render_product_scenes_worker.py`. This worker:
    *   Scans `PRODUCT_SCENES_DIR` for `.blend` files.
    *   Calculates a "shard" of work based on the SLURM array index.
    *   **Load Balancing**: Work is split not just by scene, but by *seeds*. If you have 10 scenes and 1000 seeds each, the worker ensures all SLURM nodes get an equal chunk of the total (10,000) render tasks.
    *   Launches Blender in a subprocess for each chunk.
3.  **Rendering**: Inside Blender, `local_data_acquisition_scripts/render_product_scene_blender.py` executes:
    *   **Configuration**: Reads `scene_metadata.json` (if present in the project root) to override settings like `num_background_objects`.
    *   **Scene Setup**: Loads a random "focus object" and "background objects" using `ObjectLoader` and `ObjectScatterer`.
    *   **Placement**: Randomly places objects on a defined scatter surface, ensuring no collisions.
    *   **Camera**: Spawns a camera looking at the focus object using `CameraSpawner`.
    *   **Lighting**: Generates discrete lights (point/area) within a cone directed at the object using `DiscreteLightGenerator`.
    *   **Output**: Renders the frame and saves it to `DATA_PATH/renders/product/<scene_name>/`.

#### Usage

To submit a job to the cluster:

```bash
sbatch local_data_acquisition_scripts/render_product_scenes.sh
```

Ensure you have configured your `.env` file and that `render_product_scenes.sh` has the correct SLURM parameters (partition, time, etc.) for your environment.

#### Key Modules

##### `local_data_acquisition_scripts/`
Contains the entry points for the rendering pipeline.
- `render_product_scenes.sh`: SLURM job script.
- `render_product_scenes_worker.py`: Python orchestrator for load balancing.
- `render_product_scene_blender.py`: The script that runs *inside* Blender.

##### `discrete_light_utils/`
Utilities for procedural generation.
- `discrete_light_generator.py`: Generates randomized lighting configurations.
- `object_scatterer.py`: Handles collision-free placement of objects on surfaces.
- `object_loader.py`: Loads 3D models from the dataset.

##### `rendering/`
Core rendering abstraction.
- `render_manager.py`: Configures the render engine (Cycles, GPU/OptiX) and executes the render.
- `camera_spawner.py`: Helper for placing cameras with visibility constraints.

##### `scene_metadata.json`
An optional JSON file in the project root that allows per-scene configuration overrides.
Example:
```json
{
    "my_scene_name": {
        "num_background_objects": 5
    }
}
```
