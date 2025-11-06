import base64
import pickle
from typing import List

from data.signature_vector.data_getters import HDRIData
from .scene_managers import ImageImageSceneManager, ImageTextSceneManager


class RenderModeStrategy:
    def add_args(self, parser) -> None:
        raise NotImplementedError
    def run(self, args, render_manager) -> None:
        raise NotImplementedError


class ImageImageStrategy(RenderModeStrategy):
    def add_args(self, parser) -> None:
        parser.add_argument('--serialized_signature_vector', type=str, required=True, help='Base64-encoded pickle of ImageImageSignatureVector')
        parser.add_argument('--output_path', type=str, required=True, help='Path to save the rendered image.')

    def run(self, args, render_manager) -> None:
        sig_bytes = base64.b64decode(args.serialized_signature_vector.encode('ascii'))
        sv = pickle.loads(sig_bytes)

        hdri_name = sv.variant_attributes[0].name
        hdri_rot = sv.variant_attributes[0].z_rotation_offset_from_camera
        camera_seed = sv.invariant_attributes[1].seed
        hdri_path = HDRIData.get_hdri_path_by_name(hdri_name, resolution='2k', extension='.exr')

        scene_manager = ImageImageSceneManager()
        scene_manager.setup_scene(
            camera_seed=camera_seed,
            hdri_path=hdri_path,
            hdri_z_rotation_offset=hdri_rot
        )
        render_manager.render(output_path=args.output_path)


class ImageImageBatchStrategy(RenderModeStrategy):
    def add_args(self, parser) -> None:
        parser.add_argument('--serialized_signature_vectors', type=str, required=True, help='Base64-encoded pickle of list[ImageImageSignatureVector]')
        parser.add_argument('--serialized_output_paths', type=str, required=True, help='Base64-encoded pickle of list[str] for output paths')

    def run(self, args, render_manager) -> None:
        sv_list = pickle.loads(base64.b64decode(args.serialized_signature_vectors.encode('ascii')))
        output_paths: List[str] = pickle.loads(base64.b64decode(args.serialized_output_paths.encode('ascii')))

        if len(sv_list) != len(output_paths):
            raise ValueError('serialized_signature_vectors and serialized_output_paths must be same length')

        scene_manager = ImageImageSceneManager()
        for sv, outp in zip(sv_list, output_paths):
            hdri_name = sv.variant_attributes[0].name
            hdri_rot = sv.variant_attributes[0].z_rotation_offset_from_camera
            camera_seed = sv.invariant_attributes[1].seed
            hdri_path = HDRIData.get_hdri_path_by_name(hdri_name, resolution='2k', extension='.exr')

            scene_manager.setup_scene(
                camera_seed=camera_seed,
                hdri_path=hdri_path,
                hdri_z_rotation_offset=hdri_rot
            )
            render_manager.render(output_path=outp)


class ImageTextInstructStrategy(RenderModeStrategy):
    def add_args(self, parser) -> None:
        parser.add_argument('--serialized_signature_vector', type=str, required=True, help='Serialized signature vector in pickle format.')
        parser.add_argument('--output_path', type=str, required=True, help='Path to save the rendered image.')

    def run(self, args, render_manager) -> None:
        signature_vector_str = args.serialized_signature_vector
        signature_vector_bytes = base64.b64decode(signature_vector_str.encode('ascii'))
        signature_vector = pickle.loads(signature_vector_bytes)
        
        scene_manager = ImageTextSceneManager()
        scene_manager.setup_scene(signature_vector=signature_vector)
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
