#!/bin/bash
source ~/venv-vision/bin/activate
V=/mnt/d/Personal/Drone-Tracking/vision
cd ~
# (b) mau ngau nhien 400 anh: ban sao eval_detector (cua V1) vs ma ghep cap rieng, cung mau
nice python -I $V/verify/eval_detector_copy.py --tag ft_v8n_b --weights $V/weights/ft_v8n_best.pt --cls 0 --mode crop --imgsz 640 --limit 400
nice python -I $V/verify/my_eval.py --out $V/results/verify/my_crop640_lim400 --limit 400
# toan test
nice python -I $V/verify/my_eval.py --out $V/results/verify/my_crop640