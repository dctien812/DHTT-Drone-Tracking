#!/bin/bash
# usage: 10_gz_only.sh <gpu|cpu> <world> <secs>
export RENDER=$1; source /mnt/d/Personal/Drone-Tracking/gazebo/scripts/env.sh
W=$2; T=${3:-40}
sudo apt-get install -y gstreamer1.0-tools >/dev/null 2>&1
LOG=$HOME/gazebo_logs/gz_${RENDER}_$W.log
uptime
gz sim -s -r --headless-rendering -v3 $W > $LOG 2>&1 &
GP=$!; echo GZPID=$GP
sleep 25
for i in 1 2 3; do timeout 5 gz topic -e -t /stats -n 1 2>&1 | grep -E "real_time|sim_time|paused|iterations" | tr '\n' ' '; echo; sleep 3; done
ps -o pid,pcpu,rss,etime,cmd -p $GP | cut -c1-120
kill $GP; sleep 3
tail -15 $LOG