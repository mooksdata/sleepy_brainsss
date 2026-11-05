#!/bin/bash
#SBATCH --job-name=verifynii
#SBATCH --partition=trc
#SBATCH --time=0:30:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --output=./logs/verifynii_%j.out
# Read-only check of a Bruker .nii conversion against its original tifs.
# Run from scripts/:   sbatch verify_nii.sh /path/to/TSeries-XXXX/TSeries-XXXX.xml

ml python/3.6
python3 -u verify_nii.py "$1"
