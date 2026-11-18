"""V2: cham mot model tren tap test sach (data/v2/test_clean: anh 640x640 da dung san; DUT + Det-Fly chia theo nhom).
Cach cham giong eval_detector.py: conf 0.001, NMS iou 0.7, khop tham lam theo conf voi IoU>=0.5, mien 'ignore' (khung bi cat) khong tinh FP.
Ghi results/v2/clean_<tag>.csv (tom tat) + results/v2/raw_clean_<tag>.csv (tung GT). Chay: python -I eval_clean_v2.py --tag ft --weights W
"""
import argparse, os, csv, glob
import numpy as np, torch
torch.set_num_threads(10)
from PIL import Image
from ultralytics import YOLO

V = '/mnt/d/Personal/Drone-Tracking/vision'
T = V + '/data/v2/test_clean'
BINS = [(0, 10), (10, 20), (20, 40), (40, 1e9)]; BN = ['<10', '10-20', '20-40', '>40']


def iou(a, B):
    if len(B) == 0:
        return np.zeros(0)
    ix = np.maximum(0, np.minimum(a[2], B[:, 2]) - np.maximum(a[0], B[:, 0])); iy = np.maximum(0, np.minimum(a[3], B[:, 3]) - np.maximum(a[1], B[:, 1]))
    i = ix * iy; u = (a[2] - a[0]) * (a[3] - a[1]) + (B[:, 2] - B[:, 0]) * (B[:, 3] - B[:, 1]) - i
    return i / np.maximum(u, 1e-9)


def rd(p, norm=True):
    if not os.path.exists(p):
        return np.zeros((0, 4))
    out = []
    for ln in open(p).read().split('\n'):
        if ln.strip():
            v = list(map(float, ln.split()))
            if norm:
                _, cx, cy, w, h = v; out.append([(cx - w / 2) * 640, (cy - h / 2) * 640, (cx + w / 2) * 640, (cy + h / 2) * 640])
            else:
                out.append(v)
    return np.array(out, float).reshape(-1, 4)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--tag', required=True); ap.add_argument('--weights', required=True); a = ap.parse_args()
    m = YOLO(a.weights)
    names = sorted(os.path.basename(p)[:-4] for p in glob.glob(T + '/images/*.jpg'))
    gts = []  # (name, src, wg, conf_matched, wp)
    dets = {'all': [], 'dut': [], 'detfly': []}; nimg = collections_n = {'all': 0, 'dut': 0, 'detfly': 0}
    for k in range(0, len(names), 16):
        chunk = names[k:k + 16]
        res = m.predict([f'{T}/images/{n}.jpg' for n in chunk], imgsz=640, conf=0.001, iou=0.7, max_det=100, device='cpu', verbose=False)
        for n, r in zip(chunk, res):
            src = 'dut' if n.startswith('dut') else 'detfly'
            gt = rd(f'{T}/labels/{n}.txt'); ig = rd(f'{T}/ignore/{n}.txt', norm=False)
            xy = r.boxes.xyxy.cpu().numpy(); cf = r.boxes.conf.cpu().numpy(); cl = r.boxes.cls.cpu().numpy().astype(int)
            o = np.argsort(-cf); xy, cf = xy[o], cf[o]
            used = np.zeros(len(gt), bool); match = np.full(len(gt), -1)
            for j in range(len(xy)):
                ious = iou(xy[j], gt); ious[used] = -1
                mi = int(np.argmax(ious)) if len(gt) else -1
                if mi >= 0 and ious[mi] >= 0.5:
                    used[mi] = True; match[mi] = j; tp = 1
                elif len(ig) and iou(xy[j], ig).max() >= 0.5:
                    continue
                else:
                    tp = 0
                for s in ('all', src):
                    dets[s].append((cf[j], tp))
            for s in ('all', src):
                nimg[s] += 1
            for i in range(len(gt)):
                wg = gt[i, 2] - gt[i, 0]
                gts.append((n, src, wg, cf[match[i]] if match[i] >= 0 else 0.0, (xy[match[i]][2] - xy[match[i]][0]) if match[i] >= 0 else np.nan))
    os.makedirs(V + '/results/v2', exist_ok=True)
    with open(f'{V}/results/v2/raw_clean_{a.tag}.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['name', 'source', 'w_gt_px', 'conf_matched', 'w_pred_px']); w.writerows(gts)
    rows = []
    for s in ('all', 'dut', 'detfly'):
        G = [g for g in gts if s == 'all' or g[1] == s]; D = np.array(dets[s], float).reshape(-1, 2)
        for c in (0.25, 0.5):
            sel = D[D[:, 0] >= c]; tp = int(sel[:, 1].sum()); fp = len(sel) - tp
            hit = [g[3] >= c for g in G]
            row = dict(tag=a.tag, subset=s, conf=c, n_img=nimg[s], n_gt=len(G), precision=round(tp / max(len(sel), 1), 4), recall=round(tp / max(len(G), 1), 4),
                       fp_per_100img=round(100 * fp / max(nimg[s], 1), 2))
            for b, (lo, hi) in enumerate(BINS):
                ids = [i for i, g in enumerate(G) if lo <= g[2] < hi]
                row[f'n_{BN[b]}'] = len(ids); row[f'rec_{BN[b]}'] = round(sum(hit[i] for i in ids) / len(ids), 4) if ids else ''
            ok = [g for g, h in zip(G, hit) if h]
            e = np.array([abs(g[4] - g[2]) for g in ok]); pe = np.array([100 * abs(g[4] - g[2]) / g[2] for g in ok])
            row.update(w_err_med_px=round(float(np.median(e)), 2), w_err_p90_px=round(float(np.percentile(e, 90)), 2),
                       w_err_med_pct=round(float(np.median(pe)), 2), w_err_p90_pct=round(float(np.percentile(pe, 90)), 2))
            rows.append(row)
    with open(f'{V}/results/v2/clean_{a.tag}.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for r in rows:
        print(r)


main()
