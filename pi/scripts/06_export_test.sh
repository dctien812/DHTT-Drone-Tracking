#!/bin/bash
cd ~/dtrack/models
export TMPDIR=~/dtrack/tmp
~/dtrack/venv/bin/python - <<'EOF' 2>&1 | tail -25
from ultralytics import YOLO
import time
t=time.time()
m = YOLO("ft_v8n_best.pt")
print(m.export(format="ncnn", imgsz=640, half=False))
print("secs", time.time()-t)
EOF
ls ~/dtrack/models