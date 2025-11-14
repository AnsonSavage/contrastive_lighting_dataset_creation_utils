import pickle
import os
import random
from environment import DATA_PATH
from .signature_vector.signature_vector import SignatureVector
from .signature_vector.light_attribute import KeyLight, FillLight, RimLight, VirtualLight
from .signature_vector.invariant_attributes import SceneID, CameraSeed, ContentSeed
from .signature_vector.signature_vector import SignatureVectorFactory
import uuid
from .temp_payload import temporary_payload_file

image_text_instruct_rng = random.Random(2)

class ImageTextInstructRenderGenerator:
    def __init__(self):
        pass

    def do_render(self, signature_vector: 'ImageTextInstructSignatureVector', output_path: str):
        # Call Blender via BlenderManager and stream output
        from blender_manager import BlenderManager

        payload = pickle.dumps(signature_vector)
        with temporary_payload_file(payload) as payload_path:
            blender_manager = BlenderManager()
            blender_manager.open_blender_file_with_args(
                file_path='',  # no .blend file here; script is expected to manage it
                python_script_path='render_manager.py',
                args_for_python_script=[
                    '--output_path', output_path,
                    f'--serialized_signature_vector_path={payload_path}',
                    '--aovs', 'metallic', 'albedo', 'roughness',
                ],
                background=True,
            )
        return output_path

class ImageTextInstructSignatureVector(SignatureVector):
    def __init__(self, variant_attributes: tuple[tuple[VirtualLight, ...]], invariant_attributes: tuple[SceneID, CameraSeed, ContentSeed]):
        # TODO: does the tuple of virtual lights need to be of fixed length?
        super().__init__(variant_attributes, invariant_attributes)
    def to_path(self):
        # Build path relative to DATA_PATH/renders (future substructure could be added)
        base_data_path = os.path.join(DATA_PATH, 'renders')
        path = os.path.join(
            base_data_path,
            self.invariant_attributes[0].scene_id,
            str(uuid.uuid4().hex) + '.png'  # Unique filename # TODO: should this be a hash of the signature vector instead?
        )
        if not os.path.exists(path):
            ImageTextInstructRenderGenerator().do_render(self, path)
        return path

class ImageTextDataLoader:
    def get_batch_of_signature_vectors(self, batch_size:int = None) -> list[tuple[ImageTextInstructSignatureVector, str]]:
        #  think we'll move the masks to another factory classs that's in charge of sampling them, importance sampling, and rejection sampling, etc.
        image_text_signature_vector_factory = SignatureVectorFactory(
            variant_attributes_and_freedom=(
                (KeyLight, True), # Key light
                (FillLight, True), # Fill light
                (RimLight, True)  # Rim light
            ),
            invariant_attributes_and_freedom=(
                (SceneID, False),
                (CameraSeed, False),
                (ContentSeed, False)
            ),
            rng=image_text_instruct_rng
        )

        batch = []
        for i in range(batch_size): 
            batch.append(
                (
                    image_text_signature_vector_factory.sample_signature_vector(ImageTextInstructSignatureVector),
                    "A photo of a scene with dramatic lighting." #TODO: Placeholder text instruction for now
                )
            )
        return batch

    def get_batch_of_images_given_signature_vectors(self, signature_vectors: list[tuple[ImageTextInstructSignatureVector, ...]]) -> list[tuple[str, str]]:
        image_paths = []
        # TODO
        return image_paths


if __name__ == "__main__":
    # Quick test
    dataloader = ImageTextDataLoader()
    batch = dataloader.get_batch_of_signature_vectors(batch_size=2)
    for sv, instruction in batch:
        print(sv.to_path(), instruction)