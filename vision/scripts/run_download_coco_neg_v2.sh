#!/bin/bash
source ~/venv-vision/bin/activate
cd /mnt/d/Personal/Drone-Tracking/vision/scripts
python -I download_coco_neg_v2.py "$@" 2>&1 | tee ../data/coco-neg/download.log
