"""Do ro ri train/val/test: dac trung xam 32x32 (tuong quan Pearson) + dHash 8x8(64 bit). Chay: python -I leak_features.py"""
import os, cv2, numpy as np
D='/mnt/d/Personal/Drone-Tracking/vision/data/dut-yolo'
OUT='/mnt/d/Personal/Drone-Tracking/vision/results/verify'
SCR=os.environ.get('SCR','/tmp')
cv2.setNumThreads(2)
for sp in ('train','val','test'):
    stems=sorted(f[:-4] for f in os.listdir(f'{D}/images/{sp}'))
    F=np.zeros((len(stems),1024),np.float32); H=np.zeros((len(stems),64),bool); WH=np.zeros((len(stems),2),int)
    for i,s in enumerate(stems):
        g=cv2.imread(f'{D}/images/{sp}/{s}.jpg',cv2.IMREAD_REDUCED_GRAYSCALE_4)
        if g is None: raise SystemExit('doc loi '+s)
        WH[i]=g.shape[::-1]
        F[i]=cv2.resize(g,(32,32),interpolation=cv2.INTER_AREA).ravel()
        d=cv2.resize(g,(9,8),interpolation=cv2.INTER_AREA).astype(np.int16)
        H[i]=(d[:,1:]>d[:,:-1]).ravel()
    np.savez(f'{SCR}/feat_{sp}.npz',stems=np.array(stems),F=F,H=H,WH=WH)
    print(sp,len(stems),flush=True)