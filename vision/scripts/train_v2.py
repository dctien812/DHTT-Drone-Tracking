"""V2: tinh chinh yolov8n (trong so chinh thuc cua ultralytics) tren tap ft2 (co anh am). CPU, 7 luong torch + 3 worker du lieu (<=10).
Chay: python -I train_v2.py [--epochs 30] [--hours 4.8] [--limit N] [--resume]   (limit: chi dung N anh dau cua moi nhom ten de giam cuc/giam gio)
Ket qua: runs/ft2_v8n/weights/{best,last}.pt ; log: runs/train_v2.log (do run_train_v2.sh ghi)."""
import os, sys, argparse, glob, random
os.environ['OMP_NUM_THREADS'] = '7'
import torch
torch.set_num_threads(7)
from ultralytics import YOLO

ap = argparse.ArgumentParser()
ap.add_argument('--epochs', type=int, default=30); ap.add_argument('--hours', type=float, default=0)
ap.add_argument('--limit', type=int, default=0); ap.add_argument('--resume', action='store_true'); ap.add_argument('--name', default='ft2_v8n')
a = ap.parse_args()
V = '/mnt/d/Personal/Drone-Tracking/vision'
D = V + '/data/v2'
os.chdir(V + '/weights')
train = D + '/ft2/train/images'
if a.limit:  # chon ngau nhien (hat giong co dinh) a.limit anh trong tap hoc, giu ti le cac nhom ten
    fs = sorted(glob.glob(train + '/*.jpg')); random.Random(0).shuffle(fs); train = f'{D}/ft2/train_list.txt'
    open(train, 'w').write('\n'.join(fs[:a.limit]) + '\n')
open(f'{D}/ft2.yaml', 'w').write(f'path: {D}\ntrain: {train}\nval: {D}/ft2/val/images\nnames:\n  0: drone\n')
if a.resume:
    m = YOLO(f'{V}/runs/{a.name}/weights/last.pt'); m.train(resume=True)
else:
    m = YOLO('yolov8n.pt')
    kw = dict(time=a.hours) if a.hours else {}
    m.train(data=f'{D}/ft2.yaml', imgsz=640, epochs=a.epochs, batch=16, workers=3, device='cpu', project=V + '/runs', name=a.name,
            exist_ok=True, patience=100, plots=False, seed=0, deterministic=False, close_mosaic=3, save_period=1, **kw)
print('DONE', m.trainer.best)
