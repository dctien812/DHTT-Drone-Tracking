"""Tong hop a/b/d. Chay: python -I analyze.py"""
import csv, numpy as np, math
R='/mnt/d/Personal/Drone-Tracking/vision/results/verify'
def rd(p): return list(csv.DictReader(open(p)))
# a) tai lap
print('## a) tai lap (3 lan chay, cung cau hinh)')
sm=rd(f'{R}/v1rerun/summary_metrics.csv')
for mode in ('crop','full'):
    for c in ('0.25','0.5'):
        rows=[r for r in sm if r['mode']==mode and r['conf']==c]
        print(mode,c,'n_run',len(rows),'P',sorted({r['precision'] for r in rows}),'R',sorted({r['recall'] for r in rows}),'FP/100',sorted({r['fp_per_100img'] for r in rows}),'mAP50',sorted({r['mAP50'] for r in rows}))
rb=rd(f'{R}/v1rerun/recall_by_width.csv')
for mode in ('crop','full'):
    for c in ('0.25','0.5'):
        out=[]
        for b in ('<10','10-20','20-40','>40'):
            vals={(r['n_gt'],r['recall']) for r in rb if r['mode']==mode and r['conf']==c and r['width_basis']=='native' and r['width_bin_px']==b}
            out.append((b,sorted(vals)))
        print('recall native',mode,c,out)
# b) kiem cheo
def wil(k,n,z=1.96):
    if n==0: return (float('nan'),)*2
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d; return c-h,c+h
def load(prefix):
    img={r['stem']:r for r in rd(prefix+'_img.csv')}; gt=rd(prefix+'_gt.csv'); return img,gt
def metr(img,gt,stems,thr='25'):
    tp=sum(int(img[s]['tp'+thr]) for s in stems); fp=sum(int(img[s]['fp'+thr]) for s in stems)
    ngt=sum(int(img[s]['n_gt']) for s in stems)
    return tp,fp,ngt,len(stems)
print('## b) kiem cheo ma rieng, mau 400 (V1: 396 anh/400 GT, 0.25: P .8113 R .9350; 0.5: P .9332 R .9075; FP/100 21.97 / 6.57)')
img,gt=load(f'{R}/my_crop640_lim400')
for thr in ('25','50'):
    tp,fp,n,ni=metr(img,gt,list(img),thr); print('mine thr',thr,'img',ni,'gt',n,'P',round(tp/(tp+fp),4),'R',round(tp/n,4),'FP/100',round(100*fp/ni,2))
print('## b2) toan test: ma rieng vs V1 (V1 .25: P .8519 R .9312 FP 16.30; .5: P .9519 R .8991 FP 4.57)')
img,gt=load(f'{R}/my_crop640')
for thr in ('25','50'):
    tp,fp,n,ni=metr(img,gt,list(img),thr); print('mine thr',thr,'img',ni,'gt',n,'P',round(tp/(tp+fp),4),'R',round(tp/n,4),'FP/100',round(100*fp/ni,2))
# so tung GT voi raw V1 (conf_matched>=thr)
raw=rd(f'{R}/v1rerun/raw/ft_v8n_rep1_crop_640.csv')
v1={(r['stem']):[] for r in raw}
for r in raw: v1[r['stem']].append(float(r['conf_matched']))
mine={}
for r in gt: mine.setdefault(r['stem'],[]).append((int(r['hit25']),int(r['hit50'])))
dif=0; tot=0
for s in mine:
    a=sorted(int(c>=0.25) for c in v1.get(s,[])); b=sorted(h[0] for h in mine[s]); tot+=1; dif+= a!=b
print('so khop theo anh (hit 0.25): so anh khac',dif,'/',tot)
# d) tap sach
leak={r['test_stem']:r for r in rd(f'{R}/leak_test_vs_train.csv')}
BINS=[(0,10,'<10'),(10,20,'10-20'),(20,40,'20-40'),(40,1e9,'>40')]
def table(name,stems):
    stems=[s for s in stems if s in img]
    lines=[]
    for thr in ('25','50'):
        tp,fp,n,ni=metr(img,gt,stems,thr)
        g=[r for r in gt if r['stem'] in set(stems)]
        bl=[]
        for lo,hi,nm in BINS:
            gg=[r for r in g if lo<=float(r['w_native'])<hi]; h=sum(int(r['hit'+thr]) for r in gg); L,U=wil(h,len(gg))
            bl.append(f'{nm}: {h/len(gg):.3f} (n={len(gg)}, CI {L:.2f}-{U:.2f})' if gg else f'{nm}: n=0')
        print(f'{name} | thr 0.{thr[0]}{"" if thr=="25" else ""} | anh {ni} GT {n} | P {tp/max(tp+fp,1):.3f} R {tp/max(n,1):.3f} FP/100 {100*fp/max(ni,1):.2f} | '+' ; '.join(bl))
allst=list(img)
c=lambda r,k: float(r[k])
sets={
 'TOAN TEST':allst,
 'ro ri (corr_train>=0.95)':[s for s in allst if c(leak[s],'corr_train')>=0.95],
 'sach95 (corr_train<0.95)':[s for s in allst if c(leak[s],'corr_train')<0.95],
 'sach95 train+val':[s for s in allst if c(leak[s],'corr_train')<0.95 and c(leak[s],'corr_val')<0.95],
 'sach80 train+val (corr<0.8)':[s for s in allst if c(leak[s],'corr_train')<0.8 and c(leak[s],'corr_val')<0.8],
 'sach95 vs tap con V1 2250 anh':[s for s in allst if c(leak[s],'corr_v1subset')<0.95],
}
for k,v in sets.items(): table(k,v)