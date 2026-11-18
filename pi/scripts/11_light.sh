#!/bin/bash
# che do nhe: NCNN, tang tai tu tu 1->2->3 nhan (taskset); dung neu EXT5V<4.75 hoac co co thieu ap hien tai (bit0)
cd ~/dtrack; export TMPDIR=~/dtrack/tmp OMP_NUM_THREADS=1
OUT=results/light.csv; rm -f $OUT
( while true; do echo "$(date +%T) $(vcgencmd measure_temp) $(vcgencmd get_throttled) $(vcgencmd pmic_read_adc | grep -o 'EXT5V_V volt([0-9]*)=[0-9.]*') f=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq) fan=$(cat /sys/devices/platform/cooling_fan/hwmon/*/fan1_input) st=$(cat /sys/class/thermal/cooling_device0/cur_state) load=$(cut -d' ' -f1 /proc/loadavg)" >> results/mon_light.log; sync; sleep 2; done ) &
MON=$!
STOP=0
for n in 1 2 3; do
  CORES=$(seq -s, 0 $((n-1)))
  for sz in 640 480 320; do
    sleep 25
    taskset -c $CORES ~/dtrack/venv/bin/python bench.py --model models/ft_v8n_${sz}_ncnn_model --fmt ncnn --imgsz $sz --maxf 60 --out $OUT 2>&1 | grep -E '^\{|Error' | sed "s/^/cores=$n /" | tee -a results/light.log
  done
  LAST=$(tail -3 $OUT | python3 -c "import sys,csv;r=list(csv.reader(sys.stdin));print(min(float(x[14]) for x in r))")
  echo "after cores=$n min_ext5v=$LAST" | tee -a results/light.log
  python3 -c "import sys;sys.exit(0 if $LAST>=4.75 else 1)" || { echo "STOP: EXT5V<4.75" | tee -a results/light.log; break; }
  tail -3 $OUT | awk -F, '{print $17}' | grep -q -E '0x[0-9a-f]*[13579bdf]$' && { echo "STOP: flag bit0" | tee -a results/light.log; break; }
done
echo LIGHT_DONE | tee -a results/light.log
kill $MON