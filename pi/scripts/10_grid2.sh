#!/bin/bash
# luoi do phan con thieu (bench.csv noi tiep); mon.log ghi 2 giay/lan co fsync de con dau vet neu Pi rot
cd ~/dtrack; export TMPDIR=~/dtrack/tmp OMP_NUM_THREADS=4
( while true; do echo "$(date +%T) $(vcgencmd measure_temp) $(vcgencmd get_throttled) $(vcgencmd pmic_read_adc | grep -o 'EXT5V_V volt([0-9]*)=[0-9.]*') f=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq) $(cut -d' ' -f1 /proc/loadavg)" >> results/mon.log; sync; sleep 2; done ) &
MON=$!
run() { # fmt size model
  sleep 20
  SV=""; [ $2 = 640 ] && SV="--save results/frame_$1_640.png"
  ~/dtrack/venv/bin/python bench.py --model $3 --fmt $1 --imgsz $2 --maxf 150 $SV 2>&1 | grep -E '^\{|Error|error' | tee -a results/grid.log
}
for sz in 480 320; do run ncnn $sz models/ft_v8n_${sz}_ncnn_model; done
for sz in 640 480 320; do run openvino $sz models/ft_v8n_${sz}_openvino_model; done
for sz in 480 320; do run onnx $sz models/ft_v8n_${sz}.onnx; done
run pt 640 models/ft_v8n_best.pt
echo GRID2_DONE >> results/grid.log
kill $MON