#!/bin/bash
source ~/venv-vision/bin/activate
cd /mnt/d/Personal/Drone-Tracking/vision/scripts
python -I features_v2.py 2>&1 | tee ../results/v2/features_v2.log
