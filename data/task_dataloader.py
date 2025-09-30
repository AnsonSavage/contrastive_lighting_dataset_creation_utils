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

import torch
from .signature_vector.signature_vector import SignatureVector
from .signature_vector.light_attribute import HDRIName
from .signature_vector.invariant_attributes import SceneID, CameraSeed
from .signature_vector.data_getters import get_available_scene_ids, get_available_hdris_names, get_scene_path_by_id

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
    def __init__(self, blender_path: str | None = None):
        # Use provided path or fall back to env BLENDER_PATH
        self.path_to_blender = blender_path or BLENDER_PATH
    
    def do_render(self, signature_vector: SignatureVector, output_path: str, headless: bool = True) -> str:
        subprocess.run([
            self.path_to_blender,
            '--background' if headless else '',
            get_scene_path_by_id(signature_vector.invariant_attributes[0].scene_id), # TODO: I don't really like how we're indexing into the signature vector like this, maybe getters would be better.
            '--python', 'render_script.py',
            '--', f'--output_path={output_path}'] + self.signature_vector_to_args(signature_vector)) # TODO: I guess we'll need to be able to serialize the signature vectors

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
            raise ValueError(f"Path {path} does not exist") # TODO: request the render and then ensure it gets saved to that path. Eventually we'll want to do some kind of lazy thing here because we don't want to have to reaload the scene a bunch of times, but we'll get to that later.
        return path

def get_image_path_by_signature_vector(signature_vector: ImageImageSignatureVector) -> torch.Tensor:
    # This function will need to look up the appropriate render based on the signature vector
    # If it's on disk, it'll just load that, otherwise it will request a render of it
    pass

class ImageImageDataLoader:
    def get_batch(self, invariant_free_mask, batch_size:int = None) -> ImageImageSignatureVector: # normally would also include a variant free mask, but this is true trivially in this case.
        batch_size = 32 # If none, should it get the biggest batch size it can?
        # So, basically what we need to do now is:
        """
        - If the SceneID is not free, we need to select a single random scene
        - Similarly, if the CameraSeed is not free, we need to select a single random camera seed

        # Otherwise, we sample those with replacement


        - The HDRI name will always be free, so we can just sample that without replacement
        """

        # TODO: you should probably also do some digging into whether you can support multiple positive pairs in your batch.
        # For now, we're just going to have one positive pair per batch.

        selected_scene_left = None
        selected_scene_right = None
        for i in range(len(self.invariant_attributes)):
            is_free = invariant_free_mask[i]
            attribute = self.invariant_attributes[i]
            if not is_free:
                if isinstance(attribute, SceneID): # TODO: should this be handled via polymorphism?
                    # Select a single random scene ID
                    available_scenes = get_available_scene_ids()
                    selected_scene_left = image_image_rng.choice(available_scenes)
                    selected_scene_right = image_image_rng.choice(available_scenes)
                elif isinstance(attribute, CameraSeed):
                    selected_seed = image_image_rng.randint(0, 1e6)
                    attribute.seed = selected_seed
                else:
                    raise ValueError(f"Unknown invariant attribute type: {type(attribute)}")
            else:
                raise NotImplementedError("Currently only supports non-free invariant attributes")

         # Okay, left side doesn't yet know what the camera HDRI offset will be yet. The right side will be informed from the left side. 
         # Waiiittt... I like this better: what if we randomly select the HDRI offset for both sides, have the camera seed chooose the camera rotation, and then constrain the Hdri offset to be that rotation + some random offset!
         # Okay, I really like that and I'm so glad that this clicked, haha. So much simpler.
         # So now the question is: do we still need to pre-generate the data using the sampling from the dataloader, or do we just systematically make a bunch of it?
        """Let's compare and contrast the two approaches:
        - Pre-generating the data:
          - Pros: We only generate the data we will actually train on, according to whatever sampling strategies we come up with for the dataloaders
            - Cons: More complex to implement, need to manage storage of pre-generated data, less flexible for changing sampling strategies
            - Cons: It doesn't allow us to sample from existing data, so knowing the "size" of the dataset is more complex.
        - Systematically generating the data:
            - Pros: Simpler to implement, more flexible for changing sampling strategies, can easily sample from existing data
            - Cons: May use a ton of storage space and render power
            - Cons: It's not really clear, out of all the possible data we could make, what is the most helpful data?
        """

        """ 
        Here's what I'm thinking:
        - if we systematically generate it, we can flag data somehow to be able to be grouped as a task, that way future runs can be more flexible and grab one task at a time. Tasks can have references to the paths of the images, that way images could be used across tasks, if necessary
        So, we can have a 'read' mode where the number of tasks is simply fixed to the generated tasks. Could be good, I like it. The 'read' mode I think could be implemented using a dataloader
        # So, we'll have a giant pool of rendered images, and each task could be a JSON file or otherwise that references images in that pool
        """

        # TODO:
        # We need a method that, given an ImageImageSignatureVector, returns the path to the render, or requests a render if it doesn't exist yet and then returns the path
