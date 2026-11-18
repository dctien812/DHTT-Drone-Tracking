#!/bin/bash
cd ~/dtrack/models
export TMPDIR=~/dtrack/tmp
rm -rf ft_v8n_best_ncnn_model
~/dtrack/venv/bin/python - <<'EOF' 2>&1 | grep -E "export success|ERROR|Error|failed|^EXP" 
from ultralytics import YOLO
import shutil, os
for fmt, ext in (("ncnn","_ncnn_model"),("onnx",".onnx"),("openvino","_openvino_model")):
    for sz in (640,480,320):
        try:
            m = YOLO("ft_v8n_best.pt")
            m.export(format=fmt, imgsz=sz, half=False, verbose=False)
            src = "ft_v8n_best"+ext; dst = f"ft_v8n_{sz}"+ext
            if os.path.exists(dst): shutil.rmtree(dst) if os.path.isdir(dst) else os.remove(dst)
            os.rename(src, dst); print("EXP ok", fmt, sz)
        except Exception as e:
            print("EXP FAIL", fmt, sz, repr(e)[:300])
EOF
ls ~/dtrack/models; du -sh ~/dtrack/models