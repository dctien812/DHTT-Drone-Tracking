#!/bin/bash
# huan luyen chinh V2 (nen). bash run_train_v2.sh [--epochs 30] [--limit N] ...   log: runs/train_v2.log
source ~/venv-vision/bin/activate
cd /mnt/d/Personal/Drone-Tracking/vision/scripts
nice -n 5 python -I train_v2.py "$@" > ../runs/train_v2.log 2>&1
