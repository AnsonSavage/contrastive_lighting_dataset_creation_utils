import os
import json
import re

cached_hdri_names = []

def get_available_hdris_names():
    if cached_hdri_names:
        return cached_hdri_names
    hdri_directory = r'C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\contrastive_lighting_dataset_creation_utils\dummy_data\hdri'
    cached_hdri_names.extend(os.listdir(hdri_directory))
    return cached_hdri_names

cached_scene_ids = []

def get_available_scene_ids():
    if cached_scene_ids:
        return cached_scene_ids
    scene_directory = r'C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\contrastive_lighting_dataset_creation_utils\dummy_data\scenes'
    # We could remove the .blend, but there's really no point because we just need a unique identifier and we'll have to add it back later.
    return [f for f in os.listdir(scene_directory) if f.endswith('.blend')]

def get_hdri_path_by_name(name: str, resolution:str = '2k', extension:str = '.exr'):
    # if resolution is specified, try to get that one, otherwise, get the one with the highest resolution
    hdri_directory = r'C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\contrastive_lighting_dataset_creation_utils\dummy_data\hdri'
    # Get all files ending with the specified extension in the folder
    hdri_folder = os.path.join(hdri_directory, name)
    if not os.path.exists(hdri_folder):
        raise ValueError(f"HDRI folder {hdri_folder} does not exist")
    hdri_files = [f for f in os.listdir(hdri_folder) if f.endswith(extension)]
    # Resolution is specified before the extension, e.g. name_4k.exr
    if resolution is not None:
        target_file = f"{name}_{resolution}{extension}"
        if target_file in hdri_files:
            return os.path.join(hdri_folder, target_file)
        else:
            raise ValueError(f"HDRI file with resolution {resolution} not found in {hdri_folder}")
    raise NotImplementedError("Getting the highest resolution HDRI not yet implemented")

def get_scene_path_by_id(scene_id: str):
    scene_directory = r'C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\contrastive_lighting_dataset_creation_utils\dummy_data\scenes'
    scene_path = os.path.join(scene_directory, scene_id)
    if not os.path.exists(scene_path):
        raise ValueError(f"Scene path {scene_path} does not exist")
    return scene_path