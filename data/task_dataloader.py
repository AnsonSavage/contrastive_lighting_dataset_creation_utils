'''
Here's how this is going to work! :)

Bascially, we are going to loop through different training tasks. Depending on the training task, we will load from a different data set, I think.

So, here are some of the different tasks we'll have:
1. image-image matching (image pairs with the same HDRI)
2. image-text image based lighting (descriptions simply based on the HDRI metadata)
3. image-text instruction based lighting (procedurally generated renders with LLM generated instructions (or rule-based English instructions that are run through an LLM to make them more natural and create more diverse examples))
4. image-text generated images (mostly focused on mood and style)
5. image-text real images focused on learning aesthetic
6. image-text real images focused on learning realistic lighting, learning from professional photographers, and learning more lighting vocabulary
7. (Hmm, actually though, would text-text be helpful?. Hmm, maybe something to explore with extra time.)

For each task, we'll also have a varying level of constraint. Each task has a different signature vector related to the type of data in that class. The signature vectors help us to avoid
false negative pairs in the same batch.


So, anyway, we'll select a task, and then select a "level of difficulty" for that task. The level of difficulty is related to how 
specific the signature vector is constrained.

In order to help us to begin generating data, I think it would be good to have a separate RNG for each task. That way, for the tasks we're not yet ready to support, we can skip them
but continue with the RNG sequence for the other tasks.

'''

import os
from environment import BLENDER_PATH, DATA_PATH
import random
import subprocess

# import torch
from .signature_vector.signature_vector import SignatureVector
from .signature_vector.light_attribute import HDRIName
from .signature_vector.invariant_attributes import SceneID, CameraSeed
from .signature_vector.data_getters import get_available_scene_ids, get_available_hdris_names, get_scene_path_by_id, get_hdri_path_by_name

# Make a separate random number generator for each task
image_image_rng = random.Random(0)
image_text_image_based_rng = random.Random(1)
image_text_instruction_based_rng = random.Random(2)
image_text_generated_image_rng = random.Random(3)
image_text_real_image_aesthetic_rng = random.Random(4)
image_text_real_image_lighting_rng = random.Random(5)

task_selector_rng = random.Random(6) # I think this will be preferred to simply looping through each task, we could set up importance sampling

task = 0 # let's just fix the task to 0 for now for simplicity.

# Alright, I'm just kinda free coding because I'm not exactly sure what this will look like yet., we'll figure it out as we go :)

image_image_is_free_invariant = (False, False)
image_image_is_free_variant = (True)

class RenderGenerator:
    def __init__(self):
        # Use provided path or fall back to env BLENDER_PATH
        self.path_to_blender = BLENDER_PATH

    def do_render(self, signature_vector: SignatureVector, output_path: str, headless: bool = True) -> str:
        scene_path = get_scene_path_by_id(signature_vector.invariant_attributes[0].scene_id)
        subprocess.run([
            self.path_to_blender,
            '--background' if headless else '',
            '--python', 'render_manager.py',
            
            '--', # Begin command line args for the script
            f'--output_path={output_path}',
            f'--scene_path={scene_path}',
            f'--camera_seed={signature_vector.invariant_attributes[1].seed}',
            f'--hdri_path={get_hdri_path_by_name(signature_vector.variant_attributes[0].name, resolution="2k", extension=".exr")}',
            f'--hdri_z_rotation_offset={signature_vector.variant_attributes[0].z_rotation_offset_from_camera}'
        ])
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
            RenderGenerator().do_render(self, path)
        return path

class ImageImageDataLoader:
    def get_batch_of_signature_vectors(self, invariant_free_mask, batch_size:int = None) -> list[ImageImageSignatureVector]: # normally would also include a variant free mask, but this is true trivially in this case.
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
        # The number of results will be 2 * batch size

        available_scenes = get_available_scene_ids()
        available_hdris = get_available_hdris_names()
        print("Available scenes:", available_scenes)
        print("Available HDRIs:", available_hdris)
        selection_of_hdris = image_image_rng.sample(available_hdris, k=batch_size)
        rotations = [image_image_rng.randint(0, 360) for _ in range(batch_size)]
        selected_scene_left = image_image_rng.choice(available_scenes)
        selected_scene_right = image_image_rng.choice(available_scenes)
        camera_seed_left = image_image_rng.randint(0, 1e6)
        camera_seed_right = image_image_rng.randint(0, 1e6)

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

# Let's test this now ;)

if __name__ == "__main__":
    dataloader = ImageImageDataLoader()
    sv_batch = dataloader.get_batch_of_signature_vectors(invariant_free_mask=image_image_is_free_invariant, batch_size=4)
    print("Signature Vectors:")
    for sv_left, sv_right in sv_batch:
        print("Left:", sv_left.variant_attributes[0].name, sv_left.variant_attributes[0].z_rotation_offset_from_camera, sv_left.invariant_attributes[0].scene_id, sv_left.invariant_attributes[1].seed)
        print("Right:", sv_right.variant_attributes[0].name, sv_right.variant_attributes[0].z_rotation_offset_from_camera, sv_right.invariant_attributes[0].scene_id, sv_right.invariant_attributes[1].seed)
    image_paths = dataloader.get_batch_of_images_given_signature_vectors(sv_batch)
    print("Image Paths:")
    for left_path, right_path in image_paths:
        print("Left Image Path:", left_path)
        print("Right Image Path:", right_path)