#!/bin/bash
# usage: 20_full.sh <gpu|cpu> <world>
export RENDER=$1; W=${2:-iris_runway.sdf}
source /mnt/d/Personal/Drone-Tracking/gazebo/scripts/env.sh
S=/mnt/d/Personal/Drone-Tracking/gazebo/scripts
R=/mnt/d/Personal/Drone-Tracking/gazebo/results
L=$HOME/gazebo_logs; mkdir -p $L $HOME/gazebo_logs/sitl_wd; cd $HOME/gazebo_logs/sitl_wd
PY=$HOME/venv-gazebo/bin/python
rtf() { for i in 1 2 3 4 5 6; do timeout 5 gz topic -e -t /stats -n 1 2>/dev/null | grep real_time_factor | awk '{print $2}'; done | awk -v t="$1" '{s+=$1;n++; if(min==""||$1<min)min=$1} END{printf "RTF %s: mean=%.3f min=%.3f n=%d\n", t, s/n, min, n}'; }
echo "=== RUN $RENDER $W $(date -Is)"; uptime
gz sim -s -r --headless-rendering -v3 $W > $L/run_gz_$RENDER.log 2>&1 & GZ=$!
sleep 20
~/ardupilot/build/sitl/bin/arducopter --model JSON --speedup 1 --slave 0 --sim-address=127.0.0.1 -I0 \
  --defaults $HOME/ardupilot/Tools/autotest/default_params/copter.parm,$HOME/ardupilot/Tools/autotest/default_params/gazebo-iris.parm \
  > $L/run_sitl_$RENDER.log 2>&1 & SI=$!
echo PIDS gz=$GZ sitl=$SI
sleep 10
rtf "idle(gz+sitl+camera sensor 10Hz, no stream)"
$PY $S/fly.py 10 25 > $L/run_fly_$RENDER.log 2>&1 &
FL=$!
for i in $(seq 1 100); do grep -q "takeoff ack" $L/run_fly_$RENDER.log && break; sleep 3; done; sleep 6; rtf "flying(takeoff)"
wait $FL; cat $L/run_fly_$RENDER.log
ET=$(gz topic -l | grep enable_streaming | head -1); echo "enable topic: $ET"
$PY $S/cam_recv.py 25 $R $RENDER > $L/run_cam_$RENDER.log 2>&1 & CM=$!
sleep 2
gz topic -t "$ET" -m gz.msgs.Boolean -p "data: 1"
sleep 8; rtf "camera streaming+hover"
echo "--- resources"; uptime
ps -o pid,pcpu,rss,etime,args -p $GZ,$SI | cut -c1-110
top -b -n1 | head -4 | tail -3
wait $CM; cat $L/run_cam_$RENDER.log
kill $SI $GZ; sleep 4; kill -9 $SI $GZ 2>/dev/null
echo "leftover:"; pgrep -a -f "gz sim|arducopter|ruby" | cut -c1-80