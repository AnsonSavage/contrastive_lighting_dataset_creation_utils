import pathlib
from pathlib import Path
from typing import List, Sequence, Tuple
import argparse
import sys

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render default collection cameras across outdoor scenes")
    parser.add_argument("--output-root", type=str, default=None, help="Override output root directory (default: DATA_PATH/renders_from_default_cameras)")
    parser.add_argument("--run-inside-blender", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--hdri-paths", nargs='+', default=[], help=argparse.SUPPRESS)
    return parser

# Parse arguments after '--' if present, otherwise parse all args
try:
    dashdash_index = sys.argv.index('--')
    args_after_dashdash = sys.argv[dashdash_index + 1:]
except ValueError:
    args_after_dashdash = sys.argv[1:]  # No '--' present

parser = build_parser()
args = parser.parse_args(args_after_dashdash)
in_blender = args.run_inside_blender


if in_blender:
    # Ensure this file's directory is on sys.path so we can import local packages when run by Blender
    current_dir = pathlib.Path(__file__).resolve().parent
    if str(current_dir) not in sys.path:
        sys.path.append(str(current_dir))
    import bpy
    from rendering.render_manager import RenderManager 
    from rendering.hdri_manager import HDRIManager
    from configure_camera_collections import (  # type: ignore
        CAMERAS_FOR_DATASET_COLL,
        DEFAULT_COLL,
    )

    def get_default_cameras() -> List["bpy.types.Object"]:
        assert bpy is not None, "get_default_cameras must run inside Blender"
        root_coll = bpy.data.collections.get(CAMERAS_FOR_DATASET_COLL)
        if root_coll is None:
            raise RuntimeError(
                f"Collection '{CAMERAS_FOR_DATASET_COLL}' not found. Did you run configure_camera_collections?"
            )
        default_coll = root_coll.children.get(DEFAULT_COLL)
        if default_coll is None:
            raise RuntimeError(
                f"Sub-collection '{DEFAULT_COLL}' not found under '{CAMERAS_FOR_DATASET_COLL}'."
            )
        cameras = [obj for obj in default_coll.objects if obj.type == "CAMERA"]
        if not cameras:
            raise RuntimeError(
                f"No cameras located in collection '{DEFAULT_COLL}'. Add at least one camera before rendering."
            )
        return cameras

    def render_with_camera_and_hdri(
        render_manager: RenderManager,
        camera: "bpy.types.Object",
        hdri_path: str,
        output_path: str,
    ) -> None:
        hdri_manager = HDRIManager()
        render_manager.set_camera(camera)
        hdri_manager.set_hdri(hdri_path, strength=1.0, rotation_degrees=0.0)

        render_manager.render(output_path=str(output_path))

    cameras = get_default_cameras()
    hdri_paths = args.hdri_paths
    render_manager = RenderManager()
    render_manager.set_render_settings(
        resolution=(512, 512),
        samples=32,
        bypass_compositing_nodes=True,
    )
    assert hdri_paths, "No HDRI paths provided for rendering."
    # Compose the file name by the name of the camera plus the the current blender file (without the .blend extension) + the base name of the hdri without the extension
    for camera in cameras:
        for hdri_path in hdri_paths:
            hdri_name = Path(hdri_path).stem
            blend_file_stem = Path(bpy.data.filepath).stem
            file_output_name = f"{blend_file_stem}_{hdri_name}_{camera.name}.png"
            output_dir = Path(args.output_root) 
            assert output_dir is not None, "Output root directory must be specified when running inside Blender."
            output_path = output_dir / file_output_name
            # Skip render if the path already exists
            if output_path.exists():
                print(f"Skipping existing render: {output_path}")
                continue
            render_with_camera_and_hdri(
                render_manager=render_manager,
                camera=camera,
                hdri_path=hdri_path,
                output_path=str(output_path),
            )

else:
    # Here we have access to the HDRIs that are available, etc.
    import subprocess
    from data.signature_vector.data_getters import OutdoorSceneData, HDRIData  # type: ignore
    from environment import BLENDER_PATH, DATA_PATH 

    scene_data = OutdoorSceneData()
    scenes = scene_data.get_available_scene_ids()
    scene_paths = [scene_data.get_scene_path_by_id(sid) for sid in scenes]

    hdri_data = HDRIData()
    hdri_names = hdri_data.get_available_hdris_names()
    hdri_paths = [hdri_data.get_hdri_path_by_name(name) for name in hdri_names]

    for scene_path in scene_paths:
        scene_id = Path(scene_path).stem
        output_root = Path(args.output_root) if args.output_root else Path(DATA_PATH) / "renders_from_default_cameras"
        output_dir = output_root / scene_id
        output_dir.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [BLENDER_PATH,
            scene_path,
            "--background",
            "--python", __file__, "--",
            "--run-inside-blender",
            "--output-root", str(output_dir),
            "--hdri-paths"] + hdri_paths)