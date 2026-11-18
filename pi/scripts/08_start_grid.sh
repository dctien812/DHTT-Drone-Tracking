#!/bin/bash
scp -q -i $HOME/.ssh/id_pi_lab -o IdentitiesOnly=yes /mnt/d/Personal/Drone-Tracking/pi/scripts/bench.py dctien812@192.168.1.91:dtrack/bench.py
scp -q -i $HOME/.ssh/id_pi_lab -o IdentitiesOnly=yes /mnt/d/Personal/Drone-Tracking/pi/scripts/08_grid.sh dctien812@192.168.1.91:dtrack/08_grid.sh
ssh -i $HOME/.ssh/id_pi_lab -o IdentitiesOnly=yes dctien812@192.168.1.91 "rm -f ~/dtrack/results/grid.log; nohup bash ~/dtrack/08_grid.sh > ~/dtrack/results/grid.out 2>&1 < /dev/null & echo started"