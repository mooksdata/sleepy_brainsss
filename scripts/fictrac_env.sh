# Sherlock environment for FicTrac (same modules as Yandan's build).
# FICTRAC_BIN: folder holding the fictrac executable. Default: your own build in ~/src/fictrac.
module load math devel system
module load ffmpeg/7.1 nlopt/2.6.2 opencv/4.12.0
module load gcc/14.2.0 cuda/12.6.1
export LD_LIBRARY_PATH=/share/software/user/open/gcc/14.2.0/lib64:/share/software/user/open/cuda/12.6.1/lib64:$LD_LIBRARY_PATH
export PATH=${FICTRAC_BIN:-$HOME/src/fictrac/bin}:$PATH
