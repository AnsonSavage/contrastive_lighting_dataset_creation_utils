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
import random
from .image_image_task import ImageImageDataLoader

# Make a separate random number generator for each task
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