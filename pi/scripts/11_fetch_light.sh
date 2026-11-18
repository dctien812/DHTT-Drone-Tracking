#!/bin/bash
K=$HOME/.ssh/id_pi_lab; PI=dctien812@192.168.1.91; D=/mnt/d/Personal/Drone-Tracking/pi/results
for f in light.csv light.log mon_light.log; do scp -q -i $K -o IdentitiesOnly=yes "$PI:dtrack/results/$f" $D/; done
ssh -i $K -o IdentitiesOnly=yes $PI "tail -3 ~/dtrack/results/light.log | cut -c1-200; pgrep -fa 'bench.py|11_light' | grep -v pgrep; vcgencmd measure_temp; vcgencmd get_throttled; sort -t= -k3 ~/dtrack/results/mon_light.log | awk '{print \$2}' | sort | tail -1; df -h / | tail -1"