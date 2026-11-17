#!/bin/bash
# Doi cham xong (run_eval_all.sh) roi huan luyen, de khong tranh CPU.
source ~/venv-vision/bin/activate
cd ~
while pgrep -f run_eval_all.sh > /dev/null; do sleep 15; done
nice -n 10 python -I /mnt/d/Personal/Drone-Tracking/vision/scripts/train_ft.py
