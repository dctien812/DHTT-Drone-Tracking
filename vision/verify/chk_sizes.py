import os,csv,collections
from PIL import Image
D='/mnt/d/Personal/Drone-Tracking/vision/data/dut-yolo'
rows=list(csv.DictReader(open(D+'/stats.csv')))
c=collections.Counter(); ex=[]
for r in rows:
    if r['split']!='test': continue
    im=Image.open(f"{D}/images/test/{r['stem']}.jpg"); 
    k=(im.size==(int(r['W']),int(r['H'])))
    c[k]+=1
    if not k and len(ex)<5: ex.append((r['stem'],im.size,r['W'],r['H']))
print(c,ex)
for sp in ('train','val','test'):
    print(sp,collections.Counter(Image.open(f"{D}/images/{sp}/{f}").size for f in sorted(os.listdir(D+'/images/'+sp))[::20]).most_common(6))
