source ~/venv-vision/bin/activate
cd ~
P=/mnt/d/Personal/Drone-Tracking/vision
rm -rf $P/runs/b1_videos/ft_c25
python -I $P/scripts/render_b1.py $P/runs/b1_det/ft_crop $P/runs/b1_videos/best_ft_crop 0.25 V_DRONE_001,V_DRONE_021,V_DRONE_045,V_DRONE_075,V_DRONE_100,V_DRONE_106,V_DRONE_109,V_AIRPLANE_001,V_AIRPLANE_002
python -I $P/scripts/grab_b1.py $P/runs/b1_videos/best_ft_crop $P/runs/b1_videos/best_ft_crop/check
ls -l $P/runs/b1_videos/best_ft_crop