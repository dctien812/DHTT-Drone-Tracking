#!/bin/bash
. "$(dirname "$0")/../pi.env" 2>/dev/null || { echo "Loi: thieu pi/pi.env (sao chep tu pi/pi.env.example roi dien PI_USER, PI_HOST)" >&2; exit 1; }
K=$HOME/.ssh/id_pi_lab; PI="$PI_USER@$PI_HOST"; D=/mnt/d/Personal/Drone-Tracking/pi
mkdir -p $D/results/from_pi_run2
for f in mon.log grid.log grid2.out bench.csv; do scp -q -i $K -o IdentitiesOnly=yes "$PI:dtrack/results/$f" $D/results/from_pi_run2/; done
ls -la $D/results/from_pi_run2
cat $D/results/from_pi_run2/bench.csv | cut -c1-330