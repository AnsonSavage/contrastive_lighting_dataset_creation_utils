import argparse
import random
from data.signature_vector.data_getters import HDRIData, OutdoorSceneData

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate image-image contrastive data.")
    parser.add_argument('--num_iterations', type=int, default=10, help='Number of pairs to generate')
    args = parser.parse_args()
    num_iterations = args.num_iterations

    print(f"Generating {num_iterations} image-image contrastive pairs...")

    
    for i in range(num_iterations):
        print(f"Generating pair {i+1}/{num_iterations}...")

        # Randomly select an HDRI:
        selected_hdri = random.choice(HDRIData.get_available_hdris_names())
        hdri_path = HDRIData.get_hdri_path_by_name(selected_hdri)
        print(f"Selected HDRI: {selected_hdri} at path {hdri_path}")

        