#!/bin/bash
# Tai lap phep cham V1: dung ban sao eval_detector.py, chi doi dong RES de khong ghi de file ket qua cu cua V1.
source ~/venv-vision/bin/activate
V=/mnt/d/Personal/Drone-Tracking/vision
OUT=$V/results/verify/v1rerun
mkdir -p $OUT
sed "s#^RES = ROOT + '/results'#RES = '$OUT'#" $V/scripts/eval_detector.py > $V/verify/eval_detector_copy.py
diff $V/scripts/eval_detector.py $V/verify/eval_detector_copy.py
cd ~
for rep in 1 2 3; do
  for mode in crop full; do
    echo "== rep $rep mode $mode"
    nice -n 5 python -I $V/verify/eval_detector_copy.py --tag ft_v8n_rep$rep --weights $V/weights/ft_v8n_best.pt --cls 0 --mode $mode --imgsz 640
  done
done