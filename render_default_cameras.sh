#!/bin/bash

#SBATCH --time=14:00:00   # walltime
#SBATCH --ntasks=1   # number of processor cores (i.e. tasks)
#SBATCH --nodes=1   # number of nodes
#SBATCH --gpus=1
#SBATCH --mem-per-cpu=32768M   # memory per CPU core
#SBATCH --qos=cs
#SBATCH --mail-type=ALL
#SBATCH --mail-user=ansonsav@byu.edu

# Set the max number of threads to use for programs using OpenMP. Should be <= ppn. Does nothing if the program doesn't use OpenMP.
export OMP_NUM_THREADS=$SLURM_CPUS_ON_NODE

# LOAD MODULES, INSERT CODE, AND RUN YOUR PROGRAMS HERE

cd ~/masters_thesis/contrastive_lighting_dataset_creation_utils
export BLENDER_PATH="/home/ansonsav/blender/blender-4.5.4-linux-x64/blender"
export DATA_PATH="/home/ansonsav/masters_thesis/contrastive_lighting_dataset_creation_utils/contrastive_data"
venv/bin/python3 render_default_collection_cameras.py
