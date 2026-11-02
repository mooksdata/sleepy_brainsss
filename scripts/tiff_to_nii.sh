#!/bin/bash
#SBATCH --job-name=tiff2nii
#SBATCH --partition=trc
#SBATCH --time=4:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=128G
#SBATCH --output=./logs/tiff2nii_%j.out
#SBATCH --open-mode=append
# Convert one Bruker TSeries folder of .ome.tif files to .nii (one per channel).
# Run from scripts/:   sbatch tiff_to_nii.sh /path/to/TSeries-XXXX/TSeries-XXXX.xml

ml python/3.6
date
python3 -u tiff_to_nii.py "$1"
date
