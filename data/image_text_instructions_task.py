import os
import random
from environment import BLENDER_PATH, DATA_PATH
from .signature_vector.signature_vector import SignatureVector
from .signature_vector.light_attribute import HDRIName, VirtualLight
from .signature_vector.invariant_attributes import SceneID, CameraSeed, ContentSeed
from .signature_vector.data_getters import get_available_outdoor_scene_ids, get_available_hdris_names, get_scene_path_by_id, get_hdri_path_by_name
import subprocess

image_text_instruct_rng = random.Random(2)

class ImageTextInstructRenderGenerator:
    def __init__(self):
        self.path_to_blender = BLENDER_PATH

    def do_render(self, signature_vector: SignatureVector, output_path: str, headless: bool = True) -> str:
        scene_path = get_scene_path_by_id(signature_vector.invariant_attributes[0].scene_id)
        result = subprocess.run([
            self.path_to_blender,
            scene_path,
            '--background' if headless else '',
            '--python', 'render_manager.py',
            
            '--', # Begin command line args for the script
            f'--output_path={output_path}',
            # f'--scene_path={scene_path}',
            f'--camera_seed={signature_vector.invariant_attributes[1].seed}',
            f'--hdri_path={get_hdri_path_by_name(signature_vector.variant_attributes[0].name, resolution="2k", extension=".exr")}',
            f'--hdri_z_rotation_offset={signature_vector.variant_attributes[0].z_rotation_offset_from_camera}'
        ],
                                capture_output=True)

        for line in result.stdout.splitlines():
            if '[render_manager]' in line.decode('utf-8'):
                print(line.decode('utf-8'))
        if result.stderr:
            print("Blender script errors: ", result.stderr)
        return output_path

class ImageTextInstructSignatureVector(SignatureVector):
    def __init__(self, variant_attributes: tuple[tuple[VirtualLight]], invariant_attributes: tuple[SceneID, CameraSeed, ContentSeed]):
        super().__init__(variant_attributes, invariant_attributes)
    def to_path(self):
        # Build path relative to DATA_PATH/renders (future substructure could be added)
        base_data_path = os.path.join(DATA_PATH, 'renders')
        path = os.path.join(
            base_data_path,
            self.invariant_attributes[0].scene_id,
            self.variant_attributes[0].name,
            f"camera_{self.invariant_attributes[1].seed}_hdri_offset_{self.variant_attributes[0].z_rotation_offset_from_camera}.png"
        )
        if not os.path.exists(path):
            ImageTextInstructRenderGenerator().do_render(self, path)
        return path

class ImageTextDataLoader:
    def get_batch_of_signature_vectors(self, invariant_free_mask, batch_size:int = None) -> list[tuple[ImageTextInstructSignatureVector]]: # normally would also include a variant free mask, but this is true trivially in this case.
        available_scenes = get_available_outdoor_scene_ids()
        available_hdris = get_available_hdris_names()
        print("Available scenes:", available_scenes)
        print("Available HDRIs:", available_hdris)
        selection_of_hdris = image_text_instruct_rng.sample(available_hdris, k=batch_size)
        rotations = [image_text_instruct_rng.randint(0, 360) for _ in range(batch_size)]
        selected_scene_left = image_text_instruct_rng.choice(available_scenes)
        selected_scene_right = image_text_instruct_rng.choice(available_scenes)
        camera_seed_left = image_text_instruct_rng.randint(0, 1e6)
        camera_seed_right = image_text_instruct_rng.randint(0, 1e6)

        batch = []
        for i in range(batch_size): # TODO: later you can support the free mask, right now we're assuming everything is not free :)
            selected_hdri = selection_of_hdris[i]
            selected_rotation = rotations[i]
            hdri_attribute = HDRIName(
                name=selected_hdri,
                z_rotation_offset_from_camera=selected_rotation
            )

            signature_vector_left = ImageImageSignatureVector(
                variant_attributes=(hdri_attribute,),
                invariant_attributes=(
                    SceneID(scene_id=selected_scene_left),
                    CameraSeed(seed=camera_seed_left)
                )
            )

            signature_vector_right = ImageImageSignatureVector(
                variant_attributes=(hdri_attribute,),
                invariant_attributes=(
                    SceneID(scene_id=selected_scene_right),
                    CameraSeed(seed=camera_seed_right)
                )
            )
            batch.append((signature_vector_left, signature_vector_right))
        return batch

        
    def get_batch_of_images_given_signature_vectors(self, signature_vectors: list[tuple[ImageImageSignatureVector, ...]]) -> list[tuple[str, str]]:
        image_paths = []
        for sv_left, sv_right in signature_vectors:
            left_image_path = sv_left.to_path()
            right_image_path = sv_right.to_path()
            image_paths.append((left_image_path, right_image_path))
        return image_paths
