#!/bin/bash
#
#SBATCH --job-name=jn
#SBATCH --time=48:00:00
#SBATCH --gres gpu:1
#SBATCH --exclude="weaver1, weaver2, weaver3, weaver4, weaver5, vine5, vine11, lion6, lion7"
#SBATCH --constraint="gpu_12gb&pascal"
#SBATCH --qos=batch
#SBATCH --nodes=1
#SBATCH --mem=40000

eval "$(conda shell.bash hook)"
conda activate PPUU

cd ../
srun jupyter notebook --no-browser --port 10001 --notebook-dir=$(pwd)
