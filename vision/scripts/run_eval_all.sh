#!/bin/bash
# Cham cac model tren tap test. Dung: bash run_eval_all.sh <tag> <weights> <cls>
source ~/venv-vision/bin/activate
cd ~
S=/mnt/d/Personal/Drone-Tracking/vision/scripts
for cfg in "full 640" "full 1280" "crop 640"; do
  set -- $cfg
  nice -n 10 python -I $S/eval_detector.py --tag "$TAG" --weights "$W" --cls "$CLS" --mode $1 --imgsz $2
done
