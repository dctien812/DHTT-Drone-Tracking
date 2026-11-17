#!/bin/bash
source ~/venv-vision/bin/activate
cd ~
V=/mnt/d/Personal/Drone-Tracking/vision/verify_b1
python -I $V/compare_a.py
python -I $V/crosscheck_b.py
