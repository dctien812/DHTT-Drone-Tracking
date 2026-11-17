"""Doc thong tin hai best.pt cu (duoc phep nap). Chi in lop, imgsz, tham so, train_args."""
import torch
torch.set_num_threads(4)
from ultralytics import YOLO
P = {'AI-7': '/mnt/d/Personal/DHTT-UAV-Testing-CLEAN/AI-7/best.pt',
     'finetune': '/mnt/d/Personal/DHTT-UAV-Testing-CLEAN/finetune/best.pt'}
for k, p in P.items():
    m = YOLO(p)
    ck = torch.load(p, map_location='cpu', weights_only=False)
    ta = ck.get('train_args', {})
    print('==', k, 'task', m.task, 'names', m.names, 'nc', len(m.names))
    print('  model cls', type(ck['model']).__name__, 'epoch', ck.get('epoch'), 'date', ck.get('date'), 'version', ck.get('version'))
    print('  train_args', {a: ta.get(a) for a in ('model', 'data', 'imgsz', 'epochs', 'batch', 'pretrained')})
    print('  best_fitness', ck.get('best_fitness'), 'train_metrics', {a: v for a, v in (ck.get('train_metrics') or {}).items() if 'metrics/' in a})
    m.info()
