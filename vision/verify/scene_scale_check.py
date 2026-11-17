"""Gia thuyet e: recall nhom 20-40 px tu nhien duoc huong loi tu canh ro ri (cung canh, cung co muc tieu). Chay: python -I scene_scale_check.py"""
import csv, numpy as np, os
R='/mnt/d/Personal/Drone-Tracking/vision/results/verify'; D='/mnt/d/Personal/Drone-Tracking/vision/data/dut-yolo'
st=list(csv.DictReader(open(D+'/stats.csv')))
fw={}
for r in st:
    k=(r['split'],r['stem'])
    if k not in fw: fw[k]=float(r['x2'])-float(r['x1'])
leak=list(csv.DictReader(open(R+'/leak_test_vs_train.csv')))
bins=[(10,20),(20,40),(40,1e9)]
for lo,hi in bins:
    L=[r for r in leak if lo<=fw[('test',r['test_stem'])]<hi]
    ok=[r for r in L if float(r['corr_train'])>=0.95]
    same=[r for r in ok if lo<=fw[('train',r['train_stem'])]<hi]
    ratio=[fw[('train',r['train_stem'])]/fw[('test',r['test_stem'])] for r in ok]
    print(f'nhom test {lo}-{hi}: n={len(L)}; co anh train cung canh (corr>=0.95): {len(ok)} ({len(ok)/max(len(L),1):.2f}); trong do anh train gan nhat cung nhom be rong: {len(same)} ({len(same)/max(len(ok),1):.2f}); ti le be rong train/test trung vi {np.median(ratio) if ratio else float("nan"):.2f}')