#!/bin/bash
. "$(dirname "$0")/../pi.env" 2>/dev/null || { echo "Loi: thieu pi/pi.env (sao chep tu pi/pi.env.example roi dien PI_USER, PI_HOST)" >&2; exit 1; }
K=$HOME/.ssh/id_pi_lab; PI="$PI_USER@$PI_HOST"; D=/mnt/d/Personal/Drone-Tracking/pi
scp -q -i $K -o IdentitiesOnly=yes $D/scripts/bench.py $D/scripts/11_light.sh $PI:dtrack/
ssh -i $K -o IdentitiesOnly=yes $PI "cd ~/dtrack; vcgencmd get_throttled; pgrep -f bench.py; rm -f results/light.log; setsid nohup bash 11_light.sh > results/light.out 2>&1 < /dev/null & echo started"