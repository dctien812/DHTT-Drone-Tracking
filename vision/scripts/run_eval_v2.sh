#!/bin/bash
# cham 1 model: tap test sach + 120 khung nhan tay.  bash run_eval_v2.sh TAG WEIGHTS   (vd: ft .../weights/ft_v8n_best.pt)
source ~/venv-vision/bin/activate
cd /mnt/d/Personal/Drone-Tracking/vision/scripts
export OMP_NUM_THREADS=10
python -I score_labels_v2.py "$1" "$2"
python -I eval_clean_v2.py --tag "$1" --weights "$2"
