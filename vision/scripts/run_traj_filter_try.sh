#!/bin/bash
# thu nghiem loc theo quy dao (ngoai tuyen, 1 luong): bash run_traj_filter_try.sh [--conf 0.25] [--no-cam]
source ~/venv-vision/bin/activate
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd /mnt/d/Personal/Drone-Tracking/vision/scripts
python -I traj_filter_try.py "$@"
