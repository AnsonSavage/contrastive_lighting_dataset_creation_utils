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
from data.image_image_task import ImageImageDataLoader
import argparse
from concurrent_tasks_helper import choose_shard

# Make a separate random number generator for each task
image_text_image_based_rng = random.Random(1)
image_text_generated_image_rng = random.Random(3)
image_text_real_image_aesthetic_rng = random.Random(4)
image_text_real_image_lighting_rng = random.Random(5)

task_selector_rng = random.Random(6) # I think this will be preferred to simply looping through each task, we could set up importance sampling

task = 0 # let's just fix the task to 0 for now for simplicity.

# Alright, I'm just kinda free coding because I'm not exactly sure what this will look like yet., we'll figure it out as we go :)

image_image_is_free_invariant = (False, False) # TODO: this is horrible design, you should have a better way of specifying which attributes are free vs constrained
image_image_is_free_variant = (True)


# Let's test this now ;)
if __name__ == "__main__":

    # Read in shard-index and shard-count from the command line    
    parser = argparse.ArgumentParser(description="DataLoader test script with sharding.")
    parser.add_argument('--shard-index', type=int, default=0, help='Index of the current shard (0-based).')
    parser.add_argument('--shard-count', type=int, default=1, help='Total number of shards.')
    parser.add_argument('--num-iter', type=int, default=256, help='Total number of iterations.')
    parser.add_argument('--batch-size', type=int, default=8, help='Number of images to render with the same content but different lighting.')
    args = parser.parse_args()
    shard_index, shard_count = choose_shard(args)

    n_iter = args.num_iter
    image_image_rng = random.Random(2)
    dataloader = ImageImageDataLoader(image_image_rng)
    signature_vectors = []
    for i in range(n_iter):
        # sv_batch = dataloader.get_batch_of_signature_vectors(invariant_free_mask=image_image_is_free_invariant, batch_size=1)
        signature_vectors.extend(dataloader.get_batch_of_signature_vectors(invariant_free_mask=image_image_is_free_invariant, batch_size=args.batch_size)) # This is a little counterintuitive: The batch size here controls the number of images with the same view and the same scene but with different ligting will show up on the left side and right side of tuples that are returned by this method.
    # for batch in signature_vectors:
    #     for sv in batch:
    #         print(sv)
    #         print("Left:", sv.variant_attributes[0].name, sv.variant_attributes[0].z_rotation_offset_from_camera, sv.invariant_attributes[0].scene_id, sv.invariant_attributes[1].seed)
    #         print("Right:", sv.variant_attributes[0].name, sv.variant_attributes[0].z_rotation_offset_from_camera, sv.invariant_attributes[0].scene_id, sv.invariant_attributes[1].seed)
    image_paths = dataloader.get_batch_of_images_given_signature_vectors(signature_vectors, shard_index=shard_index, shard_count=shard_count, task_method='individual')