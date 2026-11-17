"""Cham mot model tren tap test DUT (1 lop drone). Chay trong venv-vision, CPU, <=6 luong.

  python -I eval_detector.py --tag finetune_old --weights /path/best.pt --cls 0 --mode full --imgsz 640
  mode full : thu nho ca anh (letterbox) ve imgsz.
  mode crop : cat vung 640x640 o do phan giai GOC quanh 1 muc tieu (lech tam ngau nhien), suy luan imgsz=640 (ti le 1:1).

Ghi: results/raw/<tag>_<mode>_<imgsz>.csv (moi GT: width goc/infer, khop hay khong, sai so) + 1 dong vao
results/summary_metrics.csv, results/recall_by_width.csv, results/width_error.csv (ghi them, khong xoa dong cu cua tag khac).
"""
import argparse, os, csv, time, random, hashlib
import numpy as np
import torch
torch.set_num_threads(6)
from PIL import Image
from ultralytics import YOLO

ROOT = '/mnt/d/Personal/Drone-Tracking/vision'
DATA = ROOT + '/data/dut-yolo'
RES = '/mnt/d/Personal/Drone-Tracking/vision/results/verify/v1rerun'
BINS = [(0, 10), (10, 20), (20, 40), (40, 1e9)]
BN = ['<10', '10-20', '20-40', '>40']
CONFS = [0.1, 0.25, 0.5]


def binof(w):
    for i, (a, b) in enumerate(BINS):
        if a <= w < b:
            return i
    return 3


def load_gt(split, stem, W, H):
    out = []
    p = f'{DATA}/labels/{split}/{stem}.txt'
    for ln in open(p).read().split('\n'):
        if not ln.strip():
            continue
        _, cx, cy, w, h = map(float, ln.split())
        out.append([(cx - w / 2) * W, (cy - h / 2) * H, (cx + w / 2) * W, (cy + h / 2) * H])
    return np.array(out, dtype=float).reshape(-1, 4)


def iou(a, B):
    if len(B) == 0:
        return np.zeros(0)
    ix = np.maximum(0, np.minimum(a[2], B[:, 2]) - np.maximum(a[0], B[:, 0]))
    iy = np.maximum(0, np.minimum(a[3], B[:, 3]) - np.maximum(a[1], B[:, 1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (B[:, 2] - B[:, 0]) * (B[:, 3] - B[:, 1]) - inter
    return inter / np.maximum(ua, 1e-9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', required=True); ap.add_argument('--weights', required=True)
    ap.add_argument('--cls', type=int, default=0, help='chi so lop drone trong model')
    ap.add_argument('--mode', default='full', choices=['full', 'crop', 'sweep']); ap.add_argument('--imgsz', type=int, default=640)
    ap.add_argument('--tw', type=float, default=0, help='mode sweep: be rong muc tieu mong muon (px) sau khi thu nho anh')
    ap.add_argument('--split', default='test'); ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    os.makedirs(RES + '/raw', exist_ok=True)
    model = YOLO(a.weights)
    stems = sorted(f[:-4] for f in os.listdir(f'{DATA}/images/{a.split}'))
    if a.limit:
        random.Random(1).shuffle(stems); stems = sorted(stems[:a.limit])
    dets_all = []  # (conf, tp, img_idx)
    gts = []       # rows per GT
    n_img = 0; times = []; ign_dets = 0
    for k, stem in enumerate(stems):
        path = f'{DATA}/images/{a.split}/{stem}.jpg'
        im = Image.open(path).convert('RGB'); W, H = im.size
        gt = load_gt(a.split, stem, W, H)
        ox = oy = 0; ignore = np.zeros((0, 4))
        if a.mode == 'crop':
            if min(W, H) < 640 or len(gt) == 0:
                continue
            seed = int(hashlib.md5(stem.encode()).hexdigest()[:8], 16)
            rng = random.Random(seed)
            t = gt[0]
            tw, th = t[2] - t[0], t[3] - t[1]
            if tw > 640 or th > 640:
                continue
            lo_x = max(0, int(np.ceil(t[2])) - 640); hi_x = min(W - 640, int(t[0]))
            lo_y = max(0, int(np.ceil(t[3])) - 640); hi_y = min(H - 640, int(t[1]))
            if lo_x > hi_x or lo_y > hi_y:
                continue
            ox = rng.randint(lo_x, hi_x); oy = rng.randint(lo_y, hi_y)
            im = im.crop((ox, oy, ox + 640, oy + 640))
            g2 = gt - np.array([ox, oy, ox, oy])
            inside = (g2[:, 0] >= 0) & (g2[:, 1] >= 0) & (g2[:, 2] <= 640) & (g2[:, 3] <= 640)
            part = (~inside) & (g2[:, 2] > 0) & (g2[:, 3] > 0) & (g2[:, 0] < 640) & (g2[:, 1] < 640)
            ignore = np.clip(g2[part], 0, 640)
            gt = g2[inside]
            Wc, Hc = 640, 640
        elif a.mode == 'sweep':
            # thu nho ca anh sao cho muc tieu dau tien rong a.tw px, dat len khung 640x640 xam (114), lech tam ngau nhien
            if len(gt) == 0 or gt[0][2] - gt[0][0] < 40:
                continue
            s = a.tw / (gt[0][2] - gt[0][0])
            rng = random.Random(int(hashlib.md5(stem.encode()).hexdigest()[:8], 16))
            gs = gt * s; t = gs[0]
            ox = rng.randint(int(np.ceil(t[2])) - 640, int(t[0])); oy = rng.randint(int(np.ceil(t[3])) - 640, int(t[1]))
            ims = im.resize((max(1, round(W * s)), max(1, round(H * s))), Image.LANCZOS)
            canvas = Image.new('RGB', (640, 640), (114, 114, 114)); canvas.paste(ims, (-ox, -oy)); im = canvas
            g2 = gs - np.array([ox, oy, ox, oy])
            inside = (g2[:, 0] >= 0) & (g2[:, 1] >= 0) & (g2[:, 2] <= 640) & (g2[:, 3] <= 640)
            part = (~inside) & (g2[:, 2] > 0) & (g2[:, 3] > 0) & (g2[:, 0] < 640) & (g2[:, 1] < 640)
            ignore = np.clip(g2[part], 0, 640)
            gt = g2[inside]
            Wc, Hc = 640, 640
        else:
            Wc, Hc = W, H
        scale = a.imgsz / max(Wc, Hc) if a.mode == 'full' else a.imgsz / 640.0
        r = model.predict(np.asarray(im)[:, :, ::-1], imgsz=a.imgsz, conf=0.001, iou=0.7, max_det=100,
                          device='cpu', verbose=False)[0]
        if k >= 3:
            times.append((r.speed['preprocess'], r.speed['inference'], r.speed['postprocess']))
        b = r.boxes
        cls = b.cls.cpu().numpy().astype(int); keep = cls == a.cls
        xy = b.xyxy.cpu().numpy()[keep]; cf = b.conf.cpu().numpy()[keep]
        o = np.argsort(-cf); xy = xy[o]; cf = cf[o]
        used = np.zeros(len(gt), bool); n_img += 1
        gi_match = np.full(len(gt), -1)
        gidx0 = len(gts)
        for j in range(len(xy)):
            ious = iou(xy[j], gt); ious[used] = -1
            m = int(np.argmax(ious)) if len(gt) else -1
            if m >= 0 and ious[m] >= 0.5:
                used[m] = True; gi_match[m] = j
                dets_all.append((cf[j], 1, n_img)); continue
            if len(ignore) and iou(xy[j], ignore).max() >= 0.5:
                ign_dets += 1; continue
            dets_all.append((cf[j], 0, n_img))
        for m in range(len(gt)):
            wg = gt[m, 2] - gt[m, 0]; hg = gt[m, 3] - gt[m, 1]
            if gi_match[m] >= 0:
                p = xy[gi_match[m]]; wp = p[2] - p[0]; c = cf[gi_match[m]]
            else:
                wp = np.nan; c = 0.0
            gts.append((stem, wg, wg * scale, c, wp, (wp - wg)))
    # --- tong hop
    gts_a = np.array([g[1:] for g in gts], dtype=float)  # wg, wg_inf, conf, wp, err
    dets = np.array(dets_all, dtype=float).reshape(-1, 3)
    ngt = len(gts)
    # AP50 (all-point)
    o = np.argsort(-dets[:, 0]); tp = dets[o, 1]; fp = 1 - tp
    ctp = np.cumsum(tp); cfp = np.cumsum(fp)
    rec = ctp / max(ngt, 1); prec = ctp / np.maximum(ctp + cfp, 1e-9)
    mrec = np.concatenate([[0], rec, [1]]); mpre = np.concatenate([[1], prec, [0]])
    mpre = np.maximum.accumulate(mpre[::-1])[::-1]
    idx = np.where(mrec[1:] != mrec[:-1])[0]
    ap50 = float(np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1]))
    tm = np.mean(times, axis=0) if times else np.zeros(3)
    ML = a.mode if a.mode != 'sweep' else f'sweep{a.tw:g}'
    tag =f'{a.tag}_{ML}_{a.imgsz}' + (f'_lim{a.limit}' if a.limit else '')
    with open(f'{RES}/raw/{tag}.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['stem', 'w_native', 'w_infer', 'conf_matched', 'w_pred_native', 'w_err_native'])
        w.writerows(gts)

    def app(fn, header, rows):
        new = not os.path.exists(fn)
        with open(fn, 'a', newline='') as f:
            w = csv.writer(f)
            if new:
                w.writerow(header)
            w.writerows(rows)
    srows = []; rrows = []; erows = []
    for cthr in CONFS:
        sel = dets[dets[:, 0] >= cthr]
        ntp = int(sel[:, 1].sum()); nfp = len(sel) - ntp
        P = ntp / max(len(sel), 1); R = ntp / max(ngt, 1)
        srows.append([a.tag, ML, a.imgsz, a.split, n_img, ngt, cthr, f'{P:.4f}', f'{R:.4f}', f'{ap50:.4f}',
                      f'{100 * nfp / max(n_img, 1):.2f}', f'{tm[0]:.1f}', f'{tm[1]:.1f}', f'{tm[2]:.1f}', 'CPU'])
        for bset, col in (('infer', 1), ('native', 0)):
            for bi in range(4):
                msk = np.array([binof(v) == bi for v in gts_a[:, col]]) if ngt else np.zeros(0, bool)
                n = int(msk.sum()); hit = int(((gts_a[:, 2] >= cthr) & msk).sum()) if n else 0
                rrows.append([a.tag, ML, a.imgsz, cthr, bset, BN[bi], n, hit, f'{hit / n:.4f}' if n else ''])
        # sai so be rong (chi phat hien dung, native px)
        okm = gts_a[:, 2] >= cthr
        for bi in range(-1, 4):
            msk = okm & (np.array([binof(v) == bi for v in gts_a[:, 0]]) if bi >= 0 else True)
            e = gts_a[msk, 4]; wg = gts_a[msk, 0]
            if len(e) == 0:
                continue
            ae = np.abs(e); pe = 100 * ae / wg
            erows.append([a.tag, ML, a.imgsz, cthr, 'all' if bi < 0 else BN[bi], len(e), f'{np.median(ae):.2f}',
                          f'{np.percentile(ae, 90):.2f}', f'{np.median(pe):.2f}', f'{np.percentile(pe, 90):.2f}',
                          f'{np.median(100 * e / wg):.2f}'])
    app(f'{RES}/summary_metrics.csv', ['tag', 'mode', 'imgsz', 'split', 'n_img', 'n_gt', 'conf', 'precision', 'recall', 'mAP50',
                                       'fp_per_100img', 'ms_pre', 'ms_inf', 'ms_post', 'device'], srows)
    app(f'{RES}/recall_by_width.csv', ['tag', 'mode', 'imgsz', 'conf', 'width_basis', 'width_bin_px', 'n_gt', 'n_hit', 'recall'], rrows)
    app(f'{RES}/width_error.csv', ['tag', 'mode', 'imgsz', 'conf', 'width_bin_native_px', 'n', 'med_abs_px', 'p90_abs_px',
                                   'med_abs_pct', 'p90_abs_pct', 'median_signed_pct'], erows)
    print(tag, 'n_img', n_img, 'n_gt', ngt, 'ap50', round(ap50, 4), 'ms pre/inf/post', tm.round(1), 'ignored dets', ign_dets)
    for r in srows:
        print(r)


main()
