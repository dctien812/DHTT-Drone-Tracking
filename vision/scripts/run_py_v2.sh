#!/bin/bash
# chay mot script python _v2 trong venv: bash run_py_v2.sh <script.py> [args...]  (log ra stdout)
source ~/venv-vision/bin/activate
cd /mnt/d/Personal/Drone-Tracking/vision/scripts
S=$1; shift
python -I $S "$@"
