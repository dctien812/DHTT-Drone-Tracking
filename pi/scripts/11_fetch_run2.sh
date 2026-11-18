#!/bin/bash
K=$HOME/.ssh/id_pi_lab; PI=dctien812@192.168.1.91; D=/mnt/d/Personal/Drone-Tracking/pi
mkdir -p $D/results/from_pi_run2
for f in mon.log grid.log grid2.out bench.csv; do scp -q -i $K -o IdentitiesOnly=yes "$PI:dtrack/results/$f" $D/results/from_pi_run2/; done
ls -la $D/results/from_pi_run2
cat $D/results/from_pi_run2/bench.csv | cut -c1-330