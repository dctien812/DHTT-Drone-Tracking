"""V2: tai anh AM (may bay, chim) tu COCO 2017 chinh thuc (cocodataset.org). Chi tai file chu thich train2017 roi tai RIENG tung anh
co lop airplane/bird theo coco_url. Chi giu anh co giay phep cho phep dung lai (COCO license id 4 CC BY, 5 CC BY-SA, 7 No known copyright,
8 US Gov). Anh luu nguyen ban (khong nhan) vao data/coco-neg/{airplane,bird}/ + manifest.csv. Chi doc anh/JSON, khong chay gi trong goi.
Chay: python -I download_coco_neg_v2.py [n_airplane n_bird]
"""
import os, sys, json, csv, random, zipfile, urllib.request, concurrent.futures as cf

D = '/mnt/d/Personal/Drone-Tracking/vision/data/coco-neg'
NA = int(sys.argv[1]) if len(sys.argv) > 1 else 1600
NB = int(sys.argv[2]) if len(sys.argv) > 2 else 1200
ZIP = D + '/annotations_trainval2017.zip'
LIC_OK = {4, 5, 7, 8}
os.makedirs(D + '/airplane', exist_ok=True); os.makedirs(D + '/bird', exist_ok=True)
if not os.path.exists(ZIP) or os.path.getsize(ZIP) < 240_000_000:
    urllib.request.urlretrieve('http://images.cocodataset.org/annotations/annotations_trainval2017.zip', ZIP)
print('zip bytes', os.path.getsize(ZIP), flush=True)
with zipfile.ZipFile(ZIP) as z:
    js = json.loads(z.read('annotations/instances_train2017.json'))
cat = {c['name']: c['id'] for c in js['categories']}
imgs = {i['id']: i for i in js['images']}
per = {}
for a in js['annotations']:
    per.setdefault(a['image_id'], {}).setdefault(a['category_id'], []).append(a['area'])
sel = {}
for name, n in (('airplane', NA), ('bird', NB)):
    cid = cat[name]
    ids = sorted(i for i, c in per.items() if cid in c and imgs[i]['license'] in LIC_OK)
    print(name, 'tong anh co lop', sum(1 for c in per.values() if cid in c), 'sau loc giay phep', len(ids))
    random.Random(7).shuffle(ids)
    sel[name] = ids[:n]


def get(t):
    name, i = t
    im = imgs[i]; p = f"{D}/{name}/{im['file_name']}"
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return (name, i, im['file_name'], im['license'], im['flickr_url'], 'ok')
    try:
        urllib.request.urlretrieve(im['coco_url'], p)
        return (name, i, im['file_name'], im['license'], im['flickr_url'], 'ok')
    except Exception as e:
        return (name, i, im['file_name'], im['license'], im['flickr_url'], 'loi ' + str(e)[:60])


jobs = [(n, i) for n in sel for i in sel[n]]
rows = []
with cf.ThreadPoolExecutor(8) as ex:
    for k, r in enumerate(ex.map(get, jobs)):
        rows.append(r)
        if k % 300 == 0:
            print(k, '/', len(jobs), flush=True)
with open(D + '/manifest.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['class', 'coco_id', 'file', 'license_id', 'flickr_url', 'status']); w.writerows(rows)
print('ok', sum(r[5] == 'ok' for r in rows), 'loi', sum(r[5] != 'ok' for r in rows))
