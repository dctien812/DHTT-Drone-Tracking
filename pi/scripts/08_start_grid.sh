#!/bin/bash
. "$(dirname "$0")/../pi.env" 2>/dev/null || { echo "Loi: thieu pi/pi.env (sao chep tu pi/pi.env.example roi dien PI_USER, PI_HOST)" >&2; exit 1; }; PI="$PI_USER@$PI_HOST"
scp -q -i $HOME/.ssh/id_pi_lab -o IdentitiesOnly=yes /mnt/d/Personal/Drone-Tracking/pi/scripts/bench.py $PI:dtrack/bench.py
scp -q -i $HOME/.ssh/id_pi_lab -o IdentitiesOnly=yes /mnt/d/Personal/Drone-Tracking/pi/scripts/08_grid.sh $PI:dtrack/08_grid.sh
ssh -i $HOME/.ssh/id_pi_lab -o IdentitiesOnly=yes $PI "rm -f ~/dtrack/results/grid.log; nohup bash ~/dtrack/08_grid.sh > ~/dtrack/results/grid.out 2>&1 < /dev/null & echo started"