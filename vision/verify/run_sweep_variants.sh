#!/bin/bash
source ~/venv-vision/bin/activate
V=/mnt/d/Personal/Drone-Tracking/vision
cd ~
for sz in 1280 640; do for tw in 20 40; do
nice python -I $V/verify/sweep_variants.py --tw $tw --imgsz $sz --n 300 --out $V/results/verify/sweep_tw${tw}_${sz}.csv
done; done