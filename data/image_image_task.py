import os
import random
from environment import BLENDER_PATH, DATA_PATH
from .signature_vector.signature_vector import SignatureVector
from .signature_vector.light_attribute import HDRIName
from .signature_vector.invariant_attributes import SceneID, CameraSeed
from .signature_vector.data_getters import HDRIData, OutdoorSceneData
import subprocess

# TODO: We'll need to do some thinking for how to organize all of these classes better :)

image_image_rng = random.Random(0)

class ImageImageRenderGenerator:
    def __init__(self):
        self.path_to_blender = BLENDER_PATH

    def do_render(self, signature_vector: SignatureVector, output_path: str, headless: bool = True) -> str:
        scene_path = OutdoorSceneData().get_scene_path_by_id(signature_vector.invariant_attributes[0].scene_id)
        try:
            result = subprocess.run([
                self.path_to_blender,
                scene_path,
                '--background' if headless else '',
                '--python', 'render_manager.py',
                
                '--', # Begin command line args for the script
                '--mode=image-image',
                f'--output_path={output_path}',
                # f'--scene_path={scene_path}',
                f'--camera_seed={signature_vector.invariant_attributes[1].seed}',
                f'--hdri_path={HDRIData.get_hdri_path_by_name(signature_vector.variant_attributes[0].name, resolution="2k", extension=".exr")}',
                f'--hdri_z_rotation_offset={signature_vector.variant_attributes[0].z_rotation_offset_from_camera}'
            ],
            capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            print("Error during Blender rendering:")
            print(e.stdout.decode('utf-8'))
            print(e.stderr.decode('utf-8'))
            raise e


        for line in result.stdout.splitlines():
            if '[render_manager]' in line.decode('utf-8'):
                print(line.decode('utf-8'))
        if result.stderr:
            print("Blender script errors: ", result.stderr)
        return output_path

class ImageImageSignatureVector(SignatureVector):
    def __init__(self, variant_attributes: tuple[HDRIName], invariant_attributes: tuple[SceneID, CameraSeed]):
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
            ImageImageRenderGenerator().do_render(self, path)
        return path

class ImageImageDataLoader:
    def get_batch_of_signature_vectors(self, invariant_free_mask, batch_size:int = None) -> list[tuple[ImageImageSignatureVector, ImageImageSignatureVector]]: # normally would also include a variant free mask, but this is true trivially in this case.
        # If batch_size is none, should it get the biggest batch size it can?
        # So, basically what we need to do now is:
        """
        - If the SceneID is not free, we need to select a single random scene
        - Similarly, if the CameraSeed is not free, we need to select a single random camera seed

        # Otherwise, we sample those with replacement

        - The HDRI name will always be free, so we can just sample that without replacement
        """

        # TODO: you should probably also do some digging into whether you can support multiple positive pairs in your batch.
        # For now, we're just going to have one positive pair per batch.
        # TODO: Once you add support for rejection sampling, etc. you can do the same kind of sampling here that you do in the image_text_instructions_task.py file.

        available_scenes = OutdoorSceneData().get_available_scene_ids()
        available_hdris = HDRIData.get_available_hdris_names()
        print("Available scenes:", available_scenes)
        print("Available HDRIs:", available_hdris)
        selection_of_hdris = image_image_rng.sample(available_hdris, k=batch_size)
        rotations = [image_image_rng.randint(0, 360) for _ in range(batch_size)]
        selected_scene_left = image_image_rng.choice(available_scenes)
        selected_scene_right = image_image_rng.choice(available_scenes)
        camera_seed_left = image_image_rng.randint(0, 1e6)
        camera_seed_right = image_image_rng.randint(0, 1e6)

        batch = []
        for i in range(batch_size):
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


    def get_batch_of_images_given_signature_vectors(self, signature_vectors: list[tuple[ImageImageSignatureVector, ImageImageSignatureVector]]) -> list[tuple[str, str]]:
        image_paths = []
        for sv_left, sv_right in signature_vectors:
            left_image_path = sv_left.to_path()
            right_image_path = sv_right.to_path()
            image_paths.append((left_image_path, right_image_path))
        return image_paths
