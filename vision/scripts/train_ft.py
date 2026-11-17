"""Tinh chinh yolov8n (trong so chinh thuc cua ultralytics) tren tap crop/full DUT. CPU, 6 luong, toi da ~84 phut."""
import os
os.environ['OMP_NUM_THREADS'] = '6'
import torch
torch.set_num_threads(6)
from ultralytics import YOLO

ROOT = '/mnt/d/Personal/Drone-Tracking/vision'
os.chdir(ROOT + '/weights')  # yolov8n.pt chinh thuc se duoc tai ve day (da gitignore)
m = YOLO('yolov8n.pt')
print('threads', torch.get_num_threads())
m.train(data=ROOT + '/data/dut-train.yaml', imgsz=640, epochs=40, time=1.4, batch=16, workers=4, device='cpu',
        project=ROOT + '/runs', name='ft_v8n', exist_ok=True, patience=100, plots=False, seed=0, deterministic=False,
        close_mosaic=3)
print('DONE', m.trainer.best)
