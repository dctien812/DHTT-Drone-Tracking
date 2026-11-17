#!/bin/bash
export RENDER=gpu; source /mnt/d/Personal/Drone-Tracking/gazebo/scripts/env.sh
L=$HOME/gazebo_logs/gz_gui.log
gz sim -r -v3 iris_runway.sdf > $L 2>&1 & P=$!
sleep 45
echo "alive: $(ps -p $P -o pid=,pcpu=,rss= )"; pgrep -a -f "gz sim" | cut -c1-80
timeout 5 gz topic -e -t /stats -n 1 | grep real_time_factor
grep -a -i -E "error|fail|GLX|EGL|segm" $L | head -8
kill $P; sleep 4; pgrep -f "gz sim" || echo "no gz left"