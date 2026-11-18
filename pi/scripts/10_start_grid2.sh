#!/bin/bash
K=$HOME/.ssh/id_pi_lab; PI=dctien812@192.168.1.91; D=/mnt/d/Personal/Drone-Tracking/pi
mkdir -p $D/results/from_pi_run1
scp -q -i $K -o IdentitiesOnly=yes $PI:dtrack/results/{grid.log,bench.csv,frame_ncnn_640.png,frame_onnx_640.png} $D/results/from_pi_run1/
scp -q -i $K -o IdentitiesOnly=yes $D/scripts/10_grid2.sh $D/scripts/soak.py $PI:dtrack/
ssh -i $K -o IdentitiesOnly=yes $PI "cd ~/dtrack; setsid nohup bash 10_grid2.sh > results/grid2.out 2>&1 < /dev/null & echo started"