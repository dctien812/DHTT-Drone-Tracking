import torch
from ultralytics import YOLO
for p in ['/mnt/d/Personal/Drone-Tracking/vision/weights/ft_v8n_best.pt','/mnt/d/Personal/DHTT-TRACKING-TEST/AI-6/best.pt','/mnt/d/Personal/DHTT-TRACKING-TEST/AI-5/weights/best.pt']:
    m = YOLO(p); ck = torch.load(p, map_location='cpu', weights_only=False); ta = ck.get('train_args', {})
    print('==', p, m.task, m.names, type(ck['model']).__name__, ta.get('model'), ta.get('imgsz'))
    m.info()