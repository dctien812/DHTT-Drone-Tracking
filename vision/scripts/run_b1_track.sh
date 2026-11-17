#!/bin/bash
# B1: pha track (ByteTrack, BoT-SORT khong ReID/GMC) tren cac npz da co, conf 0.25 va 0.5 -> results/b1/trk_*.csv
source ~/venv-vision/bin/activate
cd ~
S=/mnt/d/Personal/Drone-Tracking/vision/scripts
O=/mnt/d/Personal/Drone-Tracking/vision/runs/b1_det
R=/mnt/d/Personal/Drone-Tracking/vision/results/b1
for n in ${@:-ft_full ai6_full ai5_full ft_crop}; do d=$O/$n
  [ -d $d ] || continue
  for tr in bytetrack botsort; do for c in 0.25 0.5; do
    python -I $S/track_videos.py track --det $d --tracker $tr --conf $c --out $R/trk_${n}_${tr}_c$c.csv > /dev/null
  done; done
done
for d in $O/bench8_*; do n=$(basename $d); python -I $S/track_videos.py track --det $d --tracker bytetrack --conf 0.25 --out $R/bench_${n}.csv > /dev/null; done
ls $R