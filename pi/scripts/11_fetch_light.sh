#!/bin/bash
. "$(dirname "$0")/../pi.env" 2>/dev/null || { echo "Loi: thieu pi/pi.env (sao chep tu pi/pi.env.example roi dien PI_USER, PI_HOST)" >&2; exit 1; }
K=$HOME/.ssh/id_pi_lab; PI="$PI_USER@$PI_HOST"; D=/mnt/d/Personal/Drone-Tracking/pi/results
for f in light.csv light.log mon_light.log; do scp -q -i $K -o IdentitiesOnly=yes "$PI:dtrack/results/$f" $D/; done
ssh -i $K -o IdentitiesOnly=yes $PI "tail -3 ~/dtrack/results/light.log | cut -c1-200; pgrep -fa 'bench.py|11_light' | grep -v pgrep; vcgencmd measure_temp; vcgencmd get_throttled; sort -t= -k3 ~/dtrack/results/mon_light.log | awk '{print \$2}' | sort | tail -1; df -h / | tail -1"