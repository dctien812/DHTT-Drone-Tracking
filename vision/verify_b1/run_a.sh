#!/bin/bash
# Muc a: chay lai NGUYEN script cua nguoi lam (scripts/track_videos.py, khong sua) tren mau 24 video, ghi ra verify_b1/det_*, results/verify_b1/
source ~/venv-vision/bin/activate
cd ~
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
H=/mnt/d/Personal/Drone-Tracking/vision
V=$H/verify_b1
R=$H/results/verify_b1
S=$H/scripts
FT=$H/weights/ft_v8n_best.pt
mkdir -p $R $V/tracks
python -I $V/select_samples.py
ONLY=$(paste -sd, $V/samples_a.txt)
for mode in full crop; do
  for i in 0 1 2 3; do
    nice -n 10 taskset -c $((2*i)),$((2*i+1)) python -I $S/track_videos.py detect --weights $FT --cls 0 --mode $mode --win 320 --threads 2 --shard $i/4 --only $ONLY --out $V/det_$mode > $V/log_det_${mode}_$i.txt 2>&1 &
  done
  wait
  for c in 0.25 0.5; do
    python -I $S/track_videos.py track --det $V/det_$mode --tracker bytetrack --conf $c --out $R/trk_ft_${mode}_bytetrack_c$c.csv --tracks-dir $V/tracks/${mode}_c$c
  done
done
echo DONE
