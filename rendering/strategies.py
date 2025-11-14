import base64
import pickle
import os
from typing import List, Optional

from data.signature_vector.data_getters import HDRIData
from .scene_managers import ImageImageSceneManager, ImageTextSceneManager
from .render_manager import RenderManager


class RenderModeStrategy:
    def add_args(self, parser) -> None:
        raise NotImplementedError
    def run(self, args, render_manager) -> None:
        raise NotImplementedError

def get_aov_output_directory(image_output_path: str, scene_id: str, camera_seed: int) -> str:
    """
    Generate a unique AOV output directory based on the image output path, scene ID, and camera seed.
    
    :param image_output_path: The path where the main rendered image will be saved.
    :param scene_id: The identifier for the scene being rendered.
    :param camera_seed: The seed value used for camera placement.
    :return: A string representing the path to the AOV output directory.
    """
    base_dir = os.path.dirname(os.path.dirname(image_output_path))
    aov_dir = os.path.join(base_dir, "aovs")
    aov_dir_name = f"{scene_id}_camera_{camera_seed}_aovs"
    aov_output_dir = os.path.join(aov_dir, aov_dir_name)
    os.makedirs(aov_output_dir, exist_ok=True)
    return aov_output_dir

def _load_payload_bytes(inline_value: Optional[str], path_value: Optional[str], description: str) -> bytes:
    if path_value:
        with open(path_value, 'rb') as payload_file:
            return payload_file.read()
    if inline_value:
        return base64.b64decode(inline_value.encode('ascii'))
    raise ValueError(f"Missing {description}: provide either inline value or *_path argument.")


class ImageImageStrategy(RenderModeStrategy):
    def add_args(self, parser) -> None:
        parser.add_argument('--serialized_signature_vector', type=str, required=False, help='Base64-encoded pickle of ImageImageSignatureVector')
        parser.add_argument('--serialized_signature_vector_path', type=str, required=False, help='Path to pickle data for ImageImageSignatureVector')
        parser.add_argument('--output_path', type=str, required=True, help='Path to save the rendered image.')

    def run(self, args, render_manager: RenderManager) -> None:
        sig_bytes = _load_payload_bytes(
            inline_value=args.serialized_signature_vector,
            path_value=args.serialized_signature_vector_path,
            description='serialized_signature_vector'
        )
        sv = pickle.loads(sig_bytes)
        # Use helper methods on the signature vector to avoid tuple indexing
        hdri_name = sv.get_hdri_name()
        hdri_rot = sv.get_hdri_rotation()
        camera_seed = sv.get_camera_seed()
        hdri_path = HDRIData.get_hdri_path_by_name(hdri_name, resolution='2k', extension='.exr')

        scene_manager = ImageImageSceneManager()
        scene_manager.setup_scene(
            camera_seed=camera_seed,
            hdri_path=hdri_path,
            hdri_z_rotation_offset=hdri_rot
        )
        # Configure AOVs into a directory unique to this content (hdri) and camera seed
        scene_id = sv.get_scene_id()
        aov_output_dir = get_aov_output_directory(args.output_path, scene_id, camera_seed)
        render_manager.set_aovs(args.aovs, aov_output_dir)
        render_manager.render(output_path=args.output_path)


class ImageImageBatchStrategy(RenderModeStrategy):
    def add_args(self, parser) -> None:
        parser.add_argument('--serialized_signature_vectors', type=str, required=False, help='Base64-encoded pickle of list[ImageImageSignatureVector]')
        parser.add_argument('--serialized_signature_vectors_path', type=str, required=False, help='Path to pickle data for list[ImageImageSignatureVector]')
        parser.add_argument('--serialized_output_paths', type=str, required=False, help='Base64-encoded pickle of list[str] for output paths')
        parser.add_argument('--serialized_output_paths_path', type=str, required=False, help='Path to pickle data for list[str] of output paths')

    def run(self, args, render_manager: RenderManager) -> None:
        sv_bytes = _load_payload_bytes(
            inline_value=args.serialized_signature_vectors,
            path_value=args.serialized_signature_vectors_path,
            description='serialized_signature_vectors'
        )
        output_bytes = _load_payload_bytes(
            inline_value=args.serialized_output_paths,
            path_value=args.serialized_output_paths_path,
            description='serialized_output_paths'
        )
        sv_list = pickle.loads(sv_bytes)
        output_paths: List[str] = pickle.loads(output_bytes)

        if len(sv_list) != len(output_paths):
            raise ValueError('serialized_signature_vectors and serialized_output_paths must be same length')

        scene_manager = ImageImageSceneManager()
        for sv, outp in zip(sv_list, output_paths):
            # Use helper methods on the signature vector to avoid tuple indexing
            hdri_name = sv.get_hdri_name()
            hdri_rot = sv.get_hdri_rotation()
            camera_seed = sv.get_camera_seed()
            hdri_path = HDRIData.get_hdri_path_by_name(hdri_name, resolution='2k', extension='.exr')

            scene_manager.setup_scene(
                camera_seed=camera_seed,
                hdri_path=hdri_path,
                hdri_z_rotation_offset=hdri_rot
            )
            # Unique AOV directory per content and camera seed
            scene_id = sv.get_scene_id()
            aov_output_dir = get_aov_output_directory(outp, scene_id, camera_seed)
            render_manager.set_aovs(args.aovs, aov_output_dir)
            render_manager.render(output_path=outp)


class ImageTextInstructStrategy(RenderModeStrategy):
    def add_args(self, parser) -> None:
        parser.add_argument('--serialized_signature_vector', type=str, required=False, help='Serialized signature vector (Base64-encoded pickle).')
        parser.add_argument('--serialized_signature_vector_path', type=str, required=False, help='Path to pickle data for the signature vector.')
        parser.add_argument('--output_path', type=str, required=True, help='Path to save the rendered image.')

    def run(self, args, render_manager: RenderManager) -> None:
        signature_vector_bytes = _load_payload_bytes(
            inline_value=args.serialized_signature_vector,
            path_value=args.serialized_signature_vector_path,
            description='serialized_signature_vector'
        )
        signature_vector = pickle.loads(signature_vector_bytes)
        
        scene_manager = ImageTextSceneManager()
        scene_manager.setup_scene(signature_vector=signature_vector)
        # TODO: does not yet support aovs
        render_manager.render(output_path=args.output_path)


def get_strategy(mode: str) -> RenderModeStrategy:
    mapping = {
        'image-image': ImageImageStrategy(),
        'image-image-batch': ImageImageBatchStrategy(),
        'image-text-instruct': ImageTextInstructStrategy(),
    }
    if mode not in mapping:
        raise ValueError(f"Unknown mode: {mode}")
    return mapping[mode]
