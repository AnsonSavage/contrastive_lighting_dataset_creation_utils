import imageio.v3 as iio
import numpy as np
import glob
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
import os
from tqdm import tqdm # Optional: for a nice progress bar

# --- ⚙️ Configuration ---

# 1. Set this to your folder of .exr files
#    Use "folder_name/*.exr" to get all EXR files in that folder.
#    Use "folder_name/**/*.exr" for recursive search.
FILE_PATTERN = "/groups/procedural_research/data/procedural_dataset_generation_data/hdri/**/*.exr"

# 2. Set the number of clusters you want to find
K_CLUSTERS = 5

# 3. Histogram settings (advanced)
HIST_BINS = 128      # Number of bins for the histogram
LOG_LUM_RANGE = (0, 8) # Range for log-luminance (log(1+L)).
                       # (0, 8) covers brightness values from L=0 up to L=e^8-1 (~3000),
                       # which is a good default for HDR.
# ---

def process_exr_to_hist(filepath):
    """
    Loads an EXR file and calculates its normalized log-luminance histogram.
    """
    try:
        # Read image. Result is a float32 numpy array.
        img = iio.imread(filepath)

        # Handle multi-channel (e.g., RGBA). We only want RGB.
        if img.shape[-1] > 3:
            img = img[..., :3]
        
        # Standard luminance calculation
        luminance = 0.2126 * img[..., 0] + 0.7152 * img[..., 1] + 0.0722 * img[..., 2]
        
        # Clamp negative values (shouldn't happen, but safe)
        luminance = np.maximum(0, luminance)
        
        # Use log(1+x) to handle zero values and compress dynamic range
        log_luminance = np.log1p(luminance)
        
        # Create histogram with a fixed range
        hist, _ = np.histogram(
            log_luminance.ravel(), 
            bins=HIST_BINS, 
            range=LOG_LUM_RANGE
        )
        
        # Normalize histogram to be a probability distribution
        hist_sum = hist.sum()
        if hist_sum > 0:
            normalized_hist = hist.astype(np.float32) / hist_sum
        else:
            # Handle black images (all zeros)
            normalized_hist = np.zeros(HIST_BINS, dtype=np.float32)
            
        return normalized_hist
        
    except Exception as e:
        print(f"Warning: Could not process {filepath}. Error: {e}")
        return None

def main():
    print(f"🔍 Searching for files matching: {FILE_PATTERN}")
    # Use recursive=True if your pattern includes "**"
    recursive = "**" in FILE_PATTERN
    filepaths = glob.glob(FILE_PATTERN, recursive=recursive)
    
    if not filepaths:
        print("\n" + "❌" * 30)
        print(" Error: No .exr files found.")
        print(" Please edit the 'FILE_PATTERN' variable in the script")
        print(" to point to your folder of .exr images.")
        print("❌" * 30)
        return

    print(f"✅ Found {len(filepaths)} files. Processing histograms...")
    
    features = []
    valid_filepaths = []
    
    # Use tqdm for a progress bar (optional, remove if not installed)
    for fp in tqdm(filepaths, desc="Processing files"):
        hist = process_exr_to_hist(fp)
        if hist is not None:
            features.append(hist)
            valid_filepaths.append(os.path.basename(fp))
            
    if not features:
        print("❌ Error: No files could be successfully processed.")
        return
        
    features = np.array(features)
    
    # --- Clustering ---
    print(f"\nCluster: Running K-Means to find {K_CLUSTERS} clusters...")
    kmeans = KMeans(n_clusters=K_CLUSTERS, random_state=42, n_init=10)
    labels = kmeans.fit_predict(features)
    
    # --- Dimensionality Reduction ---
    
    # 1. PCA: Reduce to 50D (or fewer if we have few samples/bins)
    print("Reduce: Running PCA...")
    n_pca_components = min(50, features.shape[0], features.shape[1])
    
    if n_pca_components < 2:
        print(f"Warning: Not enough data ({features.shape[0]} samples) for dimensionality reduction. Skipping plot.")
        return
        
    pca = PCA(n_components=n_pca_components)
    pca_features = pca.fit_transform(features)
    
    # 2. t-SNE: Reduce from PCA's output to 2D
    print("Reduce: Running t-SNE... (this may take a moment)")
    
    # Perplexity must be less than the number of samples
    perplexity = min(30, features.shape[0] - 1)
    if perplexity <= 0:
        print("Warning: Not enough samples for t-SNE. Skipping plot.")
        return
        
    tsne = TSNE(
        n_components=2, 
        perplexity=perplexity, 
        random_state=42,
        n_iter=1000,
        init='pca', # Initialize with PCA, often gives better results
        learning_rate='auto'
    )
    projection = tsne.fit_transform(pca_features)
    
    # --- Plotting ---
    print("📊 Plotting results...")
    plt.figure(figsize=(12, 10))
    
    # Create a scatter plot, coloring by cluster label
    scatter = plt.scatter(
        projection[:, 0], 
        projection[:, 1], 
        c=labels, 
        cmap='viridis',  # 'viridis' is a good perceptually uniform colormap
        alpha=0.7,
        s=50 # marker size
    )
    
    # Add a colorbar
    plt.colorbar(scatter, ticks=range(K_CLUSTERS), label='Cluster ID')
    
    plt.title(f't-SNE Projection of EXR Histograms ({len(features)} images, {K_CLUSTERS} clusters)')
    plt.xlabel('t-SNE Component 1')
    plt.ylabel('t-SNE Component 2')
    plt.grid(True, linestyle='--', alpha=0.3)
    
    # Optional: To add labels to the plot, uncomment the following lines.
    # Warning: This will be very messy if you have many files.
    # print("Adding text labels to plot...")
    # for i, txt in enumerate(valid_filepaths):
    #     plt.annotate(txt, (projection[i, 0], projection[i, 1]), fontsize=8, alpha=0.6)

    print("Displaying plot. Close the plot window to exit.")
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()