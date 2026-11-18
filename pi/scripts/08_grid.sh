#!/bin/bash
# luoi do: 4 dinh dang x 3 co anh, 5 video x 150 khung dau. Chay nen, log o ~/dtrack/results/grid.log
cd ~/dtrack; export TMPDIR=~/dtrack/tmp OMP_NUM_THREADS=4
rm -f results/bench.csv results/smoke.*
for sz in 640 480 320; do
 for f in ncnn onnx openvino pt; do
  case $f in
   ncnn) M=models/ft_v8n_${sz}_ncnn_model;; onnx) M=models/ft_v8n_${sz}.onnx;;
   openvino) M=models/ft_v8n_${sz}_openvino_model;; pt) M=models/ft_v8n_best.pt;;
  esac
  SV=""; [ $sz = 640 ] && SV="--save results/frame_${f}_640.png"
  sleep 20  # nghi giua cac cau hinh
  ~/dtrack/venv/bin/python bench.py --model $M --fmt $f --imgsz $sz --maxf 150 $SV 2>&1 | grep -E '^\{|Error|error' | tee -a results/grid.log
 done
done
echo GRID_DONE >> results/grid.log