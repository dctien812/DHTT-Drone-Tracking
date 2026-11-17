#!/bin/bash
# Quet kich thuoc muc tieu tong hop: dung env TAG, W (trong so), CLS (chi so lop drone)
source ~/venv-vision/bin/activate
cd ~
S=/mnt/d/Personal/Drone-Tracking/vision/scripts
for sz in 640 1280; do
  for tw in 6 8 10 12 15 20 30 40; do
    nice -n 10 python -I $S/eval_detector.py --tag "$TAG" --weights "$W" --cls "$CLS" --mode sweep --tw $tw --imgsz $sz --limit 900 | head -1
  done
done
