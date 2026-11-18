#!/bin/bash
K=$HOME/.ssh/id_pi_lab; PI=dctien812@192.168.1.91; D=/mnt/d/Personal/Drone-Tracking/pi
scp -q -i $K -o IdentitiesOnly=yes $D/scripts/bench.py $D/scripts/11_light.sh $PI:dtrack/
ssh -i $K -o IdentitiesOnly=yes $PI "cd ~/dtrack; vcgencmd get_throttled; pgrep -f bench.py; rm -f results/light.log; setsid nohup bash 11_light.sh > results/light.out 2>&1 < /dev/null & echo started"