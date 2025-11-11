import os
import json
import re
# try:
    # When running from project root
from environment import HDRI_DIR, OUTDOOR_SCENES_DIR, INDOOR_SCENES_DIR  # type: ignore
# except ModuleNotFoundError:  # pragma: no cover
#     # If executed as a package from a different CWD, attempt relative import via sys.path tweak
#     import sys, pathlib
#     project_root = pathlib.Path(__file__).resolve().parents[3]
#     if str(project_root) not in sys.path:
#         sys.path.append(str(project_root))
#     from environment import HDRI_DIR, OUTDOOR_SCENES_DIR  # type: ignore

class HDRIData:
    cached_hdri_names = []
    @staticmethod
    def get_available_hdris_names():
        """Return list of available HDRI folder names (one per HDRI)."""
        if HDRIData.cached_hdri_names:
            return HDRIData.cached_hdri_names
        if not os.path.isdir(HDRI_DIR):
            raise FileNotFoundError(f"HDRI directory not found: {HDRI_DIR}")

        # Only include directories (each HDRI is a folder)
        HDRIData.cached_hdri_names.extend([d for d in os.listdir(HDRI_DIR) if os.path.isdir(os.path.join(HDRI_DIR, d))])
        return HDRIData.cached_hdri_names

    @staticmethod
    def get_hdri_path_by_name(name: str, resolution:str = '2k', extension:str = '.exr') -> str:
        """Return the path to an HDRI file by its name and resolution.

        Expected filename pattern: <name>_<resolution><extension>
        """
        hdri_folder = os.path.join(HDRI_DIR, name)
        if not os.path.exists(hdri_folder):
            raise ValueError(f"HDRI folder {hdri_folder} does not exist (HDRI_DIR={HDRI_DIR})")
        hdri_files = [f for f in os.listdir(hdri_folder) if f.endswith(extension)]
        if resolution is not None:
            target_file = f"{name}_{resolution}{extension}"
            if target_file in hdri_files:
                return os.path.join(hdri_folder, target_file)
            else:
                raise ValueError(f"HDRI file with resolution {resolution} not found in {hdri_folder}. Available: {hdri_files}")
        raise NotImplementedError("Getting the highest resolution HDRI not yet implemented")

class SceneData:
    def __init__(self, path_prefix):
        self.path_prefix = path_prefix
        self.cached_scene_ids:list = None

    def get_available_scene_ids(self):
        if self.cached_scene_ids:
            return self.cached_scene_ids
        if not os.path.isdir(self.path_prefix):
            raise FileNotFoundError(f"Scenes directory not found: {self.path_prefix}")
        self.cached_scene_ids = [f for f in os.listdir(self.path_prefix) if f.endswith('.blend')]
        return self.cached_scene_ids


    def get_scene_path_by_id(self, scene_id: str):
        scene_path = os.path.join(self.path_prefix, scene_id)
        if not scene_id.endswith('.blend'):
            scene_path += '.blend'
        if not os.path.exists(scene_path):
            raise ValueError(f"Scene path {scene_path} does not exist (SCENES_DIR={self.path_prefix})")
        return scene_path

class OutdoorSceneData(SceneData):
    def __init__(self):
        super().__init__(OUTDOOR_SCENES_DIR)

class IndoorSceneData(SceneData):
    def __init__(self):
        super().__init__(INDOOR_SCENES_DIR)