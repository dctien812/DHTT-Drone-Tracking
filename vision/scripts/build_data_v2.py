"""V2 buoc 3: dung tap hoc/val/test tu cac nhom da chia (split_v2.py). Moi anh dau ra la 640x640 (hoac anh thu nho DUT), nhan YOLO 1 lop.
Nguon: DUT (dut-yolo + split_dut.csv), Det-Fly (det-fly + split_detfly.csv; 'drop' khong dung), COCO am (data/coco-neg, khong nhan).
Anh test sach (data/v2/test_clean): DUT cat 640 o do phan giai goc quanh muc tieu; Det-Fly thu nho ngau nhien (be rong muc tieu logU 8..80 px,
nen xam 114 neu anh nho hon 640 - giong letterbox) roi cat 640. Hat giong theo ten anh. Khung bi cat mot phan -> luu vao ignore/ (khong tinh).
Anh hoc: xem PLAN. Ghep (composite): dan mien quanh muc tieu (drone) hoac quanh may bay/chim COCO (am) len nen khong muc tieu, cung ky thuat
lam mo vien -> mo hinh khong hoc "co duong ghep = am".  Chay: python -I build_data_v2.py
"""
import os, io, csv, json, math, random, hashlib, shutil, zipfile, collections
import xml.etree.ElementTree as ET
from multiprocessing import Pool
import numpy as np, cv2
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
cv2.setNumThreads(1)

V = '/mnt/d/Personal/Drone-Tracking/vision'
DUT = V + '/data/dut-yolo'; DF = V + '/data/det-fly'; COCO = V + '/data/coco-neg'
OUT = V + '/data/v2'
PLAN = dict(  # so anh
    train=dict(dut_crop=1200, dut_full=400, dut_scaled=400, df_big=600, df_small=800, comp_pos=400, comp_neg_air=550, comp_neg_bird=350,
               coco_air=300, coco_bird=200, dut_bg=150, df_bg=250),
    val=dict(dut_crop=120, dut_full=40, df_big=60, df_small=80, comp_pos=40, comp_neg_air=40, comp_neg_bird=30, coco_air=20, coco_bird=15, dut_bg=15, df_bg=25))
TEST_N = None  # None = dung het anh test cua tung bo


def rs(*k):
    return random.Random(int(hashlib.md5('|'.join(map(str, k)).encode()).hexdigest()[:8], 16))


def logu(r, a, b):
    return math.exp(r.uniform(math.log(a), math.log(b)))


def dut_item(orig, stem):
    p = f'{DUT}/images/{orig}/{stem}.jpg'
    im = Image.open(p).convert('RGB'); W, H = im.size
    bx = []
    for ln in open(f'{DUT}/labels/{orig}/{stem}.txt').read().split('\n'):
        if ln.strip():
            _, cx, cy, w, h = map(float, ln.split()); bx.append([(cx - w / 2) * W, (cy - h / 2) * H, (cx + w / 2) * W, (cy + h / 2) * H])
    return im, bx


def df_item(sc, stem):
    r = ET.parse(f'{DF}/Annotations/{sc}/{stem}.xml').getroot()
    bx = []
    for o in r.findall('object'):
        b = o.find('bndbox'); bx.append([float(b.find(k).text) for k in ('xmin', 'ymin', 'xmax', 'ymax')])
    return f'{DF}/JPEGImages/{sc}/{stem}.jpg', bx


def df_load(path, bx, s):
    """tai anh Det-Fly (4K) thu nho ti le s (dung draft cua JPEG cho nhanh); tra (anh, boxes theo px moi)"""
    im = Image.open(path); W, H = im.size
    im.draft('RGB', (max(1, int(W * s)), max(1, int(H * s)))); im = im.convert('RGB')
    nw, nh = max(1, round(W * s)), max(1, round(H * s))
    if im.size != (nw, nh):
        im = im.resize((nw, nh), Image.LANCZOS)
    return im, [[v * nw / W if i % 2 == 0 else v * nh / H for i, v in enumerate(b)] for b in bx]


def axis_place(size, t1, t2, r):
    """truc 640: tra (src0, dst0, len). anh >=640: cat quanh muc tieu; anh nho: dan len nen xam."""
    if size >= 640:
        lo = max(0, int(math.ceil(t2)) - 640); hi = min(size - 640, int(t1))
        if lo > hi:
            lo = hi = max(0, min(size - 640, int((t1 + t2) / 2 - 320)))
        return r.randint(lo, hi), 0, 640
    return 0, r.randint(0, 640 - size), size


def axis_free(size, r):
    return (r.randint(0, size - 640), 0, 640) if size >= 640 else (0, r.randint(0, 640 - size), size)


def window(im, bx, r, around=True):
    """cat/dan 640x640. around=True: chua muc tieu dau tien. False: nen khong chua phan nao cua muc tieu (None neu khong tim duoc).
    Tra (anh, boxes_trong, boxes_bi_cat)"""
    W, H = im.size; arr = np.asarray(im)
    for _ in range(30):
        if around:
            t = bx[0]; sx, dx, lx = axis_place(W, t[0], t[2], r); sy, dy, ly = axis_place(H, t[1], t[3], r)
        else:
            sx, dx, lx = axis_free(W, r); sy, dy, ly = axis_free(H, r)
        # vung anh that nam trong cua so: x in [sx, sx+lx) -> dst dx..
        if not around:
            region = (sx, sy, sx + lx, sy + ly)
            if any(not (b[2] < region[0] - 16 or b[0] > region[2] + 16 or b[3] < region[1] - 16 or b[1] > region[3] + 16) for b in bx):
                continue
        break
    else:
        return None
    canvas = np.full((640, 640, 3), 114, np.uint8); canvas[dy:dy + ly, dx:dx + lx] = arr[sy:sy + ly, sx:sx + lx]
    inside, cut = [], []
    for b in bx:
        g = [b[0] - sx + dx, b[1] - sy + dy, b[2] - sx + dx, b[3] - sy + dy]
        full = g[0] >= dx and g[1] >= dy and g[2] <= dx + lx and g[3] <= dy + ly
        if full:
            inside.append(g)
        elif g[2] > dx and g[3] > dy and g[0] < dx + lx and g[1] < dy + ly:
            cut.append([max(g[0], dx), max(g[1], dy), min(g[2], dx + lx), min(g[3], dy + ly)])
    return Image.fromarray(canvas), inside, cut


def paste(bg, patch, r):
    """dan patch (RGB np, vien mo) vao bg PIL 640 o vi tri ngau nhien. Tra (anh, (x1,y1,x2,y2) cua mien patch)"""
    ph, pw = patch.shape[:2]
    x0 = r.randint(0, 640 - pw); y0 = r.randint(0, 640 - ph)
    return x0, y0


def make_patch(im, box, wd, r):
    """cat mien quanh box (le 25%), thu ve be rong box = wd px; tra (patch RGB np, mask float, box trong patch)"""
    W, H = im.size; bw, bh = box[2] - box[0], box[3] - box[1]
    mx, my = max(6, 0.25 * bw), max(6, 0.25 * bh)
    x1, y1 = int(max(0, box[0] - mx)), int(max(0, box[1] - my)); x2, y2 = int(min(W, box[2] + mx)), int(min(H, box[3] + my))
    k = wd / bw
    reg = im.crop((x1, y1, x2, y2)); nw, nh = max(4, round((x2 - x1) * k)), max(4, round((y2 - y1) * k))
    reg = np.asarray(reg.resize((nw, nh), Image.LANCZOS))
    m = max(2, int(round(0.18 * min(nw, nh))))
    mask = np.zeros((nh, nw), np.float32); mask[m:nh - m, m:nw - m] = 1
    mask = cv2.GaussianBlur(mask, (0, 0), max(1.0, m / 2.0))
    return reg, mask, [(box[0] - x1) * k, (box[1] - y1) * k, (box[2] - x1) * k, (box[3] - y1) * k]


def composite(bg, reg, mask, pb, r):
    ph, pw = reg.shape[:2]
    if ph >= 640 or pw >= 640:
        return None
    x0 = r.randint(0, 640 - pw); y0 = r.randint(0, 640 - ph)
    a = np.asarray(bg).astype(np.float32); m = mask[..., None]
    a[y0:y0 + ph, x0:x0 + pw] = a[y0:y0 + ph, x0:x0 + pw] * (1 - m) + reg.astype(np.float32) * m
    return Image.fromarray(a.clip(0, 255).astype(np.uint8)), [pb[0] + x0, pb[1] + y0, pb[2] + x0, pb[3] + y0]


def save(img, boxes, setname, name, ignore=None):
    d = f'{OUT}/{setname}'
    os.makedirs(f'{d}/images', exist_ok=True); os.makedirs(f'{d}/labels', exist_ok=True)
    img.save(f'{d}/images/{name}.jpg', quality=95)
    w, h = img.size
    with open(f'{d}/labels/{name}.txt', 'w') as f:
        for b in boxes:
            f.write(f'0 {(b[0]+b[2])/2/w:.6f} {(b[1]+b[3])/2/h:.6f} {(b[2]-b[0])/w:.6f} {(b[3]-b[1])/h:.6f}\n')
    if ignore:
        os.makedirs(f'{d}/ignore', exist_ok=True)
        with open(f'{d}/ignore/{name}.txt', 'w') as f:
            for b in ignore:
                f.write(' '.join(f'{v:.1f}' for v in b) + '\n')


# ---------------- nguon ----------------
S = {}


def init():
    S['dut'] = {k: [] for k in ('train', 'val', 'test')}
    for r in csv.DictReader(open(f'{OUT}/split_dut.csv')):
        if r['split'] in S['dut']:
            S['dut'][r['split']].append((r['orig_split'], r['stem']))
    S['df'] = {k: [] for k in ('train', 'val', 'test')}
    for r in csv.DictReader(open(f'{OUT}/split_detfly.csv')):
        if r['split'] in S['df']:
            S['df'][r['split']].append((r['scene_dir'], r['stem']))
    S['coco'] = json.load(open(f'{COCO}/bbox.json'))


def pick(r, lst):
    return lst[r.randrange(len(lst))]


def background(r, sp):
    """anh nen 640 khong co muc tieu (DUT hoac Det-Fly cua split sp)"""
    for _ in range(20):
        if r.random() < 0.5:
            orig, st = pick(r, S['dut'][sp]); im, bx = dut_item(orig, st)
            if min(im.size) < 640:
                continue
            w = window(im, bx, r, around=False)
        else:
            sc, st = pick(r, S['df'][sp]); p, bx = df_item(sc, st); s = logu(r, 0.25, 0.8)
            im, bx = df_load(p, bx, s); w = window(im, bx, r, around=False)
        if w:
            return w[0]
    return None


def drone_source(r, sp):
    if r.random() < 0.5:
        orig, st = pick(r, S['dut'][sp]); im, bx = dut_item(orig, st)
        if not bx:
            return None
        return im, bx[0]
    sc, st = pick(r, S['df'][sp]); p, bx = df_item(sc, st); s = logu(r, 0.3, 1.0)
    im, bx = df_load(p, bx, s)
    return im, bx[0]


def job(t):
    kind, sp, i, ex = t
    r = rs(kind, sp, i, ex)
    dest = {'train': 'ft2/train', 'val': 'ft2/val', 'test': 'test_clean'}[sp]
    name = f'{kind}_{i:05d}'
    try:
        if kind == 'dut_crop' or kind == 'dut_scaled':
            orig, st = ex; im, bx = dut_item(orig, st)
            if not bx or min(im.size) < 640:
                return None
            if kind == 'dut_scaled':
                s = logu(r, 0.35, 0.9); im = im.resize((round(im.size[0] * s), round(im.size[1] * s)), Image.LANCZOS)
                bx = [[v * s for v in b] for b in bx]
            w = window(im, bx, r)
            if not w or not w[1]:
                return None
            save(w[0], w[1], dest, name, w[2]); return (dest, name, kind, 'dut', w[1])
        if kind == 'dut_full':
            orig, st = ex; im, bx = dut_item(orig, st)
            if not bx:
                return None
            s = 640 / max(im.size); im = im.resize((round(im.size[0] * s), round(im.size[1] * s)), Image.LANCZOS)
            bx = [[v * s for v in b] for b in bx]; save(im, bx, dest, name); return (dest, name, kind, 'dut', bx)
        if kind in ('df_big', 'df_small', 'df_test'):
            sc, st = ex; p, bx = df_item(sc, st); w0 = bx[0][2] - bx[0][0]
            if kind == 'df_big':
                s = logu(r, 0.3, 1.0)
            elif kind == 'df_small':
                s = logu(r, 0.06, 0.3)
            else:
                s = min(1.0, max(0.04, logu(r, 8, 80) / w0))
            im, bx = df_load(p, bx, s); w = window(im, bx, r)
            if not w or not w[1]:
                return None
            save(w[0], w[1], dest, name, w[2]); return (dest, name, kind, 'detfly', w[1])
        if kind == 'dut_test':
            orig, st = ex; im, bx = dut_item(orig, st)
            if not bx or min(im.size) < 640 or (bx[0][2] - bx[0][0]) > 640 or (bx[0][3] - bx[0][1]) > 640:
                return None
            w = window(im, bx, r)
            if not w or not w[1]:
                return None
            save(w[0], w[1], dest, name, w[2]); return (dest, name, kind, 'dut', w[1])
        if kind in ('dut_bg', 'df_bg'):
            for _ in range(10):
                if kind == 'dut_bg':
                    orig, st = pick(r, S['dut'][sp]); im, bx = dut_item(orig, st)
                    if min(im.size) < 640:
                        continue
                    w = window(im, bx, r, around=False)
                else:
                    sc, st = pick(r, S['df'][sp]); p, bx = df_item(sc, st); im, bx = df_load(p, bx, logu(r, 0.15, 0.9)); w = window(im, bx, r, around=False)
                if w:
                    save(w[0], [], dest, name); return (dest, name, kind, kind[:-3], [])
            return None
        if kind == 'comp_pos':
            bg = background(r, sp); src = drone_source(r, sp)
            if bg is None or src is None:
                return None
            reg, mask, pb = make_patch(src[0], src[1], logu(r, 8, 60), r); c = composite(bg, reg, mask, pb, r)
            if c is None:
                return None
            save(c[0], [c[1]], dest, name); return (dest, name, kind, 'composite', [c[1]])
        if kind in ('comp_neg_air', 'comp_neg_bird'):
            cls = 'airplane' if kind.endswith('air') else 'bird'
            lst = [e for e in S['coco'][sp] if e['cls'] == cls and e['big']]
            e = pick(r, lst); bg = background(r, sp)
            if bg is None:
                return None
            im = Image.open(f"{COCO}/{cls}/{e['file']}").convert('RGB')
            reg, mask, pb = make_patch(im, e['big'], logu(r, 8, 60), r); c = composite(bg, reg, mask, pb, r)
            if c is None:
                return None
            save(c[0], [], dest, name); return (dest, name, kind, 'coco-' + cls, [])
        if kind in ('coco_air', 'coco_bird'):
            cls = 'airplane' if kind.endswith('air') else 'bird'
            e = pick(r, [e for e in S['coco'][sp] if e['cls'] == cls])
            im = Image.open(f"{COCO}/{cls}/{e['file']}").convert('RGB'); save(im, [], dest, name); return (dest, name, kind, 'coco-' + cls, [])
    except Exception as ex_:
        print('LOI', kind, i, repr(ex_)[:120], flush=True)
    return None


def coco_meta():
    p = f'{COCO}/bbox.json'
    if os.path.exists(p):
        return
    z = zipfile.ZipFile(f'{COCO}/annotations_trainval2017.zip'); js = json.loads(z.read('annotations/instances_train2017.json'))
    cat = {c['id']: c['name'] for c in js['categories']}; imgs = {i['id']: i for i in js['images']}
    man = [r for r in csv.DictReader(open(f'{COCO}/manifest.csv')) if r['status'] == 'ok']
    byid = {int(r['coco_id']): r for r in man}
    inst = collections.defaultdict(list)
    for a in js['annotations']:
        if a['image_id'] in byid and cat[a['category_id']] == byid[a['image_id']]['class'] and not a['iscrowd']:
            x, y, w, h = a['bbox']; inst[a['image_id']].append([x, y, x + w, y + h])
    ids = sorted(byid); out = {'train': [], 'val': []}
    for k, i in enumerate(ids):
        bs = sorted(inst[i], key=lambda b: -(b[2] - b[0]) * (b[3] - b[1]))
        big = bs[0] if bs and (bs[0][2] - bs[0][0]) >= 32 and (bs[0][3] - bs[0][1]) >= 20 else None
        out['val' if k % 10 == 0 else 'train'].append(dict(cls=byid[i]['class'], file=byid[i]['file'], big=big))
    json.dump(out, open(p, 'w'))
    print('coco bbox.json', {k: len(v) for k, v in out.items()}, flush=True)


if __name__ == '__main__':
    coco_meta(); init()
    if os.path.isdir(OUT + '/ft2'):
        shutil.rmtree(OUT + '/ft2')
    if os.path.isdir(OUT + '/test_clean'):
        shutil.rmtree(OUT + '/test_clean')
    tasks = []
    for sp, plan in PLAN.items():
        for kind, n in plan.items():
            if kind.startswith('dut_') and kind != 'dut_bg':
                pool = list(S['dut'][sp]); random.Random(5).shuffle(pool)
            elif kind.startswith('df_') and kind != 'df_bg':
                pool = list(S['df'][sp]); random.Random(6).shuffle(pool)
            else:
                pool = [0]
            for i in range(n):
                tasks.append((kind, sp, i, pool[i % len(pool)]))
    for i, e in enumerate(S['dut']['test'][:TEST_N]):
        tasks.append(('dut_test', 'test', i, e))
    for i, e in enumerate(S['df']['test'][:TEST_N]):
        tasks.append(('df_test', 'test', i, e))
    print('so tac vu', len(tasks), flush=True)
    rows = []
    with Pool(9) as P:
        for k, r in enumerate(P.imap_unordered(job, tasks, chunksize=8)):
            if r:
                rows.append(r)
            if k % 500 == 0:
                print(k, '/', len(tasks), flush=True)
    with open(f'{OUT}/manifest.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['set', 'name', 'kind', 'source', 'n_box', 'w_first_px']);
        for sp, name, kind, src, bx in sorted(rows):
            w.writerow([sp, name, kind, src, len(bx), f'{bx[0][2]-bx[0][0]:.1f}' if bx else ''])
    print('xong', len(rows), 'anh')
    c = collections.Counter((r[0], r[2]) for r in rows)
    for k in sorted(c):
        print(k, c[k])
