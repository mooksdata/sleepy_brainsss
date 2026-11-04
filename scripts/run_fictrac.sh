#!/bin/bash
#SBATCH -J fictrac
#SBATCH -p trc,normal
#SBATCH -t 4:00:00
#SBATCH -c 4
#SBATCH --mem=8G
#SBATCH --constraint=CPU_MNF:INTEL
#SBATCH -o ./logs/fictrac_%j.out

# Run FicTrac offline on one Jackfish recording folder (adapted from Yandan's run_fictrac.sh).
# Usage (from scripts/):
#   sbatch run_fictrac.sh <recording_folder> <output_folder> [camera]
# e.g.
#   sbatch run_fictrac.sh /oak/stanford/groups/trc/data/Mook/jackfish_videos/20260617/fly1/1 \
#                         /oak/stanford/groups/trc/data/Mook/fictrac_output/20260617/fly1/1
# The recording folder must hold cam_<camera>.mp4, cam_<camera>.txt and a FicTrac config
# (config_CL.txt, or any config*.txt). camera defaults to 18384364, the ball camera.
# Intel-only: Sherlock's opencv/4.12.0 module dies with Illegal Instruction on AMD nodes.

set -e
if [ "$#" -lt 2 ]; then
    echo "Usage: sbatch run_fictrac.sh <recording_folder> <output_folder> [camera]" >&2
    exit 1
fi
REC_DIR=$1
OUT_DIR=$2
CAMERA=${3:-18384364}

MP4=$REC_DIR/cam_$CAMERA.mp4
if [ ! -f "$MP4" ]; then
    echo "No $MP4" >&2
    exit 1
fi
CONFIG=$REC_DIR/config_CL.txt
if [ ! -f "$CONFIG" ]; then
    shopt -s nullglob
    CONFIGS=("$REC_DIR"/config*.txt)
    shopt -u nullglob
    if [ "${#CONFIGS[@]}" -ne 1 ]; then
        echo "Need exactly one FicTrac config (config_CL.txt or config*.txt) in $REC_DIR, found ${#CONFIGS[@]}" >&2
        exit 1
    fi
    CONFIG=${CONFIGS[0]}
fi

mkdir -p "$OUT_DIR"
if ls "$OUT_DIR"/*.dat >/dev/null 2>&1; then
    echo "$OUT_DIR already has a .dat; delete or move it to rerun." >&2
    exit 1
fi
echo "video:  $MP4"
echo "config: $CONFIG"
echo "output: $OUT_DIR"
date

cp "$CONFIG" "$OUT_DIR/config_used.txt"
cp "$REC_DIR/cam_$CAMERA.txt" "$OUT_DIR/jackfish_timestamps.txt"
cd "$OUT_DIR"

# FicTrac writes its outputs next to the source video, so point it at a local symlink
ln -sf "$MP4" "./cam_$CAMERA.mp4"
trap 'rm -f "$OUT_DIR/cam_$CAMERA.mp4"' EXIT

# Offline run: read the video, no display window, no network socket
sed -i -E \
    -e "s|^([[:space:]]*src_fn[[:space:]]*:).*|\1 ./cam_$CAMERA.mp4|" \
    -e "s|^([[:space:]]*do_display[[:space:]]*:).*|\1 n|" \
    -e "/^[[:space:]]*sock_(host|port)[[:space:]]*:/d" \
    config_used.txt

# sbatch runs a spooled copy of this script, so look for fictrac_env.sh in the submit dir
ENV_SH="$SLURM_SUBMIT_DIR/fictrac_env.sh"
[ -f "$ENV_SH" ] || ENV_SH="$(dirname "$0")/fictrac_env.sh"
source "$ENV_SH"

# -v must come before the config; after it, it is ignored and the log grows huge
fictrac -v WRN config_used.txt

chgrp -R oak_trc "$OUT_DIR" 2>/dev/null || true
date
ls -lh "$OUT_DIR"
