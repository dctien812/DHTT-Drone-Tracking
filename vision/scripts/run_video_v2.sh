#!/bin/bash
# 119 video, ca khung, ByteTrack mac dinh (track_videos.py). bash run_video_v2.sh TAG WEIGHTS [detect]
#  - detect: chay model tren tung khung (luu runs/v2_det/<TAG>_full/*.npz). Bo qua neu TAG=ft: dung lai npz cu runs/b1_det/ft_full (cung model, cung lenh).
#  - track : ByteTrack conf 0.25/0.5 -> results/v2/trk_<TAG>_full_bytetrack_c*.csv
source ~/venv-vision/bin/activate
cd ~
S=/mnt/d/Personal/Drone-Tracking/vision/scripts; V=/mnt/d/Personal/Drone-Tracking/vision
TAG=$1; W=$2
if [ "$TAG" = ft ]; then D=$V/runs/b1_det/ft_full; else D=$V/runs/v2_det/${TAG}_full; fi
if [ "$3" = detect ]; then
  export OMP_NUM_THREADS=10 MKL_NUM_THREADS=10
  nice -n 5 python -I $S/track_videos.py detect --weights $W --cls 0 --mode full --threads 10 --out $D
fi
for c in 0.25 0.5; do
  python -I $S/track_videos.py track --det $D --tracker bytetrack --conf $c --out $V/results/v2/trk_${TAG}_full_bytetrack_c$c.csv
done
