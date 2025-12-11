#!/bin/bash

#SBATCH --time=15:00:00   # walltime
#SBATCH --ntasks=2   # number of processor cores (i.e. tasks)
#SBATCH --nodes=1   # number of nodes
#SBATCH --gpus=1
#SBATCH --mem-per-cpu=32768M   # memory per CPU core
#SBATCH --qos=standby
#SBATCH --mail-type=ALL
#SBATCH --mail-user=ansonsav@byu.edu

#SBATCH --array=0-7
#SBATCH --requeue

# Set the max number of threads to use for programs using OpenMP. Should be <= ppn. Does nothing if the program doesn't use OpenMP.
export OMP_NUM_THREADS=$SLURM_CPUS_ON_NODE

# LOAD MODULES, INSERT CODE, AND RUN YOUR PROGRAMS HERE

# Derive shard index/count from Slurm env; fall back to single shard if not set.
SHARD_INDEX=${SLURM_ARRAY_TASK_ID:-0}
SHARD_MIN=${SLURM_ARRAY_TASK_MIN:-0}
SHARD_MAX=${SLURM_ARRAY_TASK_MAX:-0}
SHARD_STEP=${SLURM_ARRAY_TASK_STEP:-1}

# Compute shard count = ((max - min) / step) + 1
if [[ -n "$SLURM_ARRAY_TASK_MAX" ]]; then
	SHARD_COUNT=$(( (SHARD_MAX - SHARD_MIN) / SHARD_STEP + 1 ))
	# Normalize zero-based index when min != 0 or step != 1
	NORM_INDEX=$(( (SHARD_INDEX - SHARD_MIN) / SHARD_STEP ))
else
	SHARD_COUNT=1
	NORM_INDEX=0
fi

echo "Running shard $(($NORM_INDEX+1)) of $SHARD_COUNT" >&2

cd ~/masters_thesis/contrastive_lighting_dataset_creation_utils
export BLENDER_PATH="/home/ansonsav/blender/blender-4.5.4-linux-x64/blender"
export DATA_PATH="/home/ansonsav/nobackup/autodelete/contrastive_lighting_dataset"

# Run the worker script
venv/bin/python3 local_data_acquisition_scripts/render_product_scenes_worker.py \
	--shard-index "$NORM_INDEX" \
	--shard-count "$SHARD_COUNT" \
	--output-dir-name "product_content_lock_test_varied_materials_04" \
	--seeds-per-scene 1024 \
	--render-aovs \
	--material-library "/home/ansonsav/masters_thesis/contrastive_lighting_dataset_creation_utils/contrastive_data/scenes/product/material_libraries/material_library_01.blend" \
	--min-passing-lighting-percentage 0.5 # We are pretty loose here. We want some resemblence of the lighting vocab we've pre-computed with Qwen, but wen're not going to be strict.