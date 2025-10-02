import pickle
import os
import random
import base64
from environment import BLENDER_PATH, DATA_PATH
from .signature_vector.signature_vector import SignatureVector
from .signature_vector.light_attribute import HDRIName, KeyLight, FillLight, RimLight, VirtualLight
from .signature_vector.invariant_attributes import SceneID, CameraSeed, ContentSeed
from .signature_vector.data_getters import OutdoorSceneData
from .signature_vector.signature_vector import SignatureVectorFactory
import subprocess
import uuid

image_text_instruct_rng = random.Random(2)

class ImageTextInstructRenderGenerator:
    def __init__(self):
        self.path_to_blender = BLENDER_PATH

    def do_render(self, signature_vector: 'ImageTextInstructSignatureVector', output_path: str):
        # Call Blender in background mode with the current script and pass the necessary arguments
        serialized_sv = base64.b64encode(pickle.dumps(signature_vector)).decode('ascii')
        cmd = [
            self.path_to_blender,
            '--background',  # Run in background mode
            '--python', 'render_manager.py',  # Path to this script
            '--',  # Arguments after this are passed to the script
            '--output_path', output_path,
            '--serialized_signature_vector', serialized_sv
        ]
        # print("Running command:", ' '.join(cmd))  # For debugging purposes
        result = subprocess.run(cmd, capture_output=True, check=True)
        for line in result.stdout.splitlines():
            print(line.decode('utf-8'))
        for line in result.stderr.splitlines():
            print("Blender script error:", line.decode('utf-8'))
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