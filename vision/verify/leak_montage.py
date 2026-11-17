import csv,sys,cv2,numpy as np
D='/mnt/d/Personal/Drone-Tracking/vision/data/dut-yolo'
OUT=sys.argv[1]
rows=list(csv.DictReader(open('/mnt/d/Personal/Drone-Tracking/vision/results/verify/leak_test_vs_train.csv')))
rows.sort(key=lambda r:r['test_stem'])
import random; rg=random.Random(5)
sel=[]
for lo,hi in ((0.99,1.01),(0.95,0.99),(0.9,0.95),(0.8,0.9),(0.4,0.8)):
    c=[r for r in rows if lo<=float(r['corr_train'])<hi]; sel+=rg.sample(c,3)
def rd(p): 
    im=cv2.imread(p); return cv2.resize(im,(320,180))
lines=[]
for r in sel:
    a=rd(f"{D}/images/test/{r['test_stem']}.jpg"); b=rd(f"{D}/images/train/{r['train_stem']}.jpg")
    t=np.hstack([a,b]); cv2.putText(t,f"test {r['test_stem']} / train {r['train_stem']} c={r['corr_train']}",(4,16),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,255),1)
    lines.append(t)
cv2.imwrite(OUT,np.vstack([np.hstack(lines[i:i+3]) if False else lines[i] for i in range(0,5)]))
cv2.imwrite(OUT.replace('.jpg','_b.jpg'),np.vstack(lines[5:10]))
cv2.imwrite(OUT.replace('.jpg','_c.jpg'),np.vstack(lines[10:15]))
print([(r['test_stem'],r['train_stem'],r['corr_train']) for r in sel])