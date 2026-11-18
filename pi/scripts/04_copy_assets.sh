#!/bin/bash
K=$HOME/.ssh/id_pi_lab; PI=dctien812@192.168.1.91
ssh -i $K -o IdentitiesOnly=yes $PI "mkdir -p ~/dtrack/videos ~/dtrack/models ~/dtrack/results"
W=/mnt/d/Personal/Drone-Tracking/vision/weights/ft_v8n_best.pt
V=/mnt/d/Personal/DHTT-TRACKING-TEST/AI-6/video
scp -q -i $K -o IdentitiesOnly=yes $W $PI:dtrack/models/ft_v8n_best.pt
for n in 001 021 045 075 100; do scp -q -i $K -o IdentitiesOnly=yes $V/V_DRONE_$n.mp4 $PI:dtrack/videos/; done
scp -q -i $K -o IdentitiesOnly=yes /mnt/d/Personal/Drone-Tracking/pi/scripts/bench.py $PI:dtrack/bench.py
ssh -i $K -o IdentitiesOnly=yes $PI "ls -la ~/dtrack/videos ~/dtrack/models"