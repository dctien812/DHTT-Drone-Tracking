#!/bin/bash
# B1: pha detect cho 3 model x (full | crop320). 4 tien trinh, moi tien trinh ghim 2 loi (taskset) = 8 loi. Co the chay lai (bo qua video da co npz).
source ~/venv-vision/bin/activate
cd ~
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
S=/mnt/d/Personal/Drone-Tracking/vision/scripts
O=/mnt/d/Personal/Drone-Tracking/vision/runs/b1_det
FT=/mnt/d/Personal/Drone-Tracking/vision/weights/ft_v8n_best.pt
A6=/mnt/d/Personal/DHTT-TRACKING-TEST/AI-6/best.pt
A5=/mnt/d/Personal/DHTT-TRACKING-TEST/AI-5/weights/best.pt
run() { # tag weights cls mode
  for i in 0 1 2 3; do
    nice -n 10 taskset -c $((2*i)),$((2*i+1)) python -I $S/track_videos.py detect --weights $2 --cls $3 --mode $4 --win 320 --threads 2 --shard $i/4 --out $O/$1_$4 > $O/log_$1_$4_$i.txt 2>&1 &
  done
  wait
}
mkdir -p $O
# do toc do 1 tien trinh 8 luong (bo qua neu da co) (5 video drone, khong song song)
for t in "ft $FT 0" "ai6 $A6 0" "ai5 $A5 38"; do
  set -- $t
  OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 nice -n 10 python -I $S/track_videos.py detect --weights $2 --cls $3 --mode full --threads 8 --only DRONE_001,DRONE_021,DRONE_045,DRONE_075,DRONE_100 --out $O/bench8_$1 > $O/log_bench_$1.txt 2>&1
done
# thu tu thuc te (ngan sach thoi gian): bench -> ft full -> ai6 full -> ft crop -> ai5 full ; ai6/ai5 crop bo qua
run ft $FT 0 full
run ai6 $A6 0 full
run ft $FT 0 crop
run ai5 $A5 38 full
echo ALLDONE > $O/ALLDONE
