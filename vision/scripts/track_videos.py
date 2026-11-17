"""B1: nhan dien + theo doi tren video ghi san (offline, chi doc video).
Hai pha:
  detect : chay model tren tung khung, luu moi phat hien (conf>=0.1) + ms moi khung vao npz (mot file/video).
  track  : doc npz, chay BYTETracker (ultralytics) o nguong conf T, tinh so do, ghi CSV.
Chay: python -I track_videos.py detect --tag T --weights W --cls 0 --mode full|crop --win 320 --out DIR [--shard i/n] [--threads 2] [--only A,B]
      python -I track_videos.py track  --det DIR --tracker bytetrack --conf 0.25 --out CSV
"""
import argparse, glob, os, sys, time, json
import numpy as np

VID = '/mnt/d/Personal/DHTT-TRACKING-TEST/AI-6/video'


def vids(only=None):
    ps = sorted(glob.glob(VID + '/*.mp4') + glob.glob(VID + '/*.MOV'))
    if only:
        ks = only.split(',')
        ps = [p for p in ps if any(k in os.path.basename(p) for k in ks)]
    return ps


def detect(a):
    import cv2, torch
    torch.set_num_threads(a.threads); cv2.setNumThreads(1)
    from ultralytics import YOLO
    m = YOLO(a.weights)
    os.makedirs(a.out, exist_ok=True)
    ps = vids(a.only)
    if a.shard:
        i, n = map(int, a.shard.split('/')); ps = ps[i::n]
    kw = dict(imgsz=a.imgsz, conf=a.dconf, classes=[a.cls], verbose=False, device='cpu', max_det=20)
    m.predict(np.zeros((512, 640, 3), np.uint8), **kw)  # khoi dong
    for p in ps:
        name = os.path.splitext(os.path.basename(p))[0]
        of = f'{a.out}/{name}.npz'
        if os.path.exists(of): continue
        c = cv2.VideoCapture(p); fps = c.get(cv2.CAP_PROP_FPS)
        rows, ms, fb, prev = [], [], [], None
        k = 0
        while True:
            ok, f = c.read()
            if not ok: break
            H, W = f.shape[:2]
            t0 = time.perf_counter(); used_fb = 0
            def run(img, ox, oy):
                r = m.predict(img, **kw)[0].boxes
                if len(r) == 0: return np.zeros((0, 5), np.float32)
                b = np.concatenate([r.xyxy.cpu().numpy(), r.conf.cpu().numpy()[:, None]], 1)
                b[:, [0, 2]] += ox; b[:, [1, 3]] += oy
                return b
            d = None
            if a.mode == 'crop' and prev is not None:
                cx, cy = prev
                x0 = int(min(max(cx - a.win / 2, 0), max(W - a.win, 0))); y0 = int(min(max(cy - a.win / 2, 0), max(H - a.win, 0)))
                d = run(f[y0:y0 + a.win, x0:x0 + a.win], x0, y0)
                if len(d) == 0: d = None; used_fb = 1  # mat muc tieu -> quet ca khung
            if d is None:
                d = run(f, 0, 0)
            ms.append((time.perf_counter() - t0) * 1000); fb.append(used_fb)
            for r in d: rows.append([k, *r])
            g = d[d[:, 4] >= 0.25]
            prev = None if len(g) == 0 else ((g[g[:, 4].argmax()][0] + g[g[:, 4].argmax()][2]) / 2, (g[g[:, 4].argmax()][1] + g[g[:, 4].argmax()][3]) / 2)
            k += 1
        np.savez(of, dets=np.array(rows, np.float32).reshape(-1, 6), ms=np.array(ms, np.float32), fb=np.array(fb, np.int8),
                 meta=np.array([k, fps, W, H], np.float64))
        print(name, k, 'frames', round(float(np.median(ms)), 1), 'ms med', flush=True)


class _R:  # doi tuong ket qua toi thieu cho BYTETracker.update
    def __init__(s, d):
        s.conf = d[:, 4].astype(np.float32); s.cls = np.zeros(len(d), np.float32)
        s.xyxy = d[:, :4]
        s.xywh = np.stack([(d[:, 0] + d[:, 2]) / 2, (d[:, 1] + d[:, 3]) / 2, d[:, 2] - d[:, 0], d[:, 3] - d[:, 1]], 1).astype(np.float32)
    def __len__(s): return len(s.conf)
    def __getitem__(s, i):
        o = _R.__new__(_R); o.conf = s.conf[i]; o.cls = s.cls[i]; o.xyxy = s.xyxy[i]; o.xywh = s.xywh[i]
        return o


def make_tracker(name, T, fps):
    from types import SimpleNamespace
    from ultralytics.trackers.byte_tracker import BYTETracker
    from ultralytics.trackers.bot_sort import BOTSORT
    cfg = dict(tracker_type=name, track_high_thresh=T, track_low_thresh=0.1, new_track_thresh=T, track_buffer=30, match_thresh=0.8, fuse_score=True)
    if name == 'botsort':
        cfg.update(gmc_method='none', proximity_thresh=0.5, appearance_thresh=0.25, with_reid=False)
        return BOTSORT(SimpleNamespace(**cfg))
    return BYTETracker(SimpleNamespace(**cfg))


def gaps(has):
    """cac doan lien tiep khong co track giua khung co track dau va cuoi"""
    idx = np.flatnonzero(has)
    if len(idx) < 2: return []
    d = np.diff(idx) - 1
    return [int(x) for x in d if x > 0]


def track(a):
    import csv
    files = sorted(glob.glob(a.det + '/*.npz'))
    rows = []
    for f in files:
        name = os.path.basename(f)[:-4]
        z = np.load(f); dets = z['dets']; ms = z['ms']; n, fps, W, H = z['meta']; n = int(n)
        tk = make_tracker(a.tracker, a.conf, fps)
        tms = np.zeros(n); ids_by_frame = [[] for _ in range(n)]; prim = [None] * n; pw = []
        life = {}
        out = []
        for k in range(n):
            d = dets[dets[:, 0] == k][:, 1:] if len(dets) else np.zeros((0, 5), np.float32)
            t0 = time.perf_counter()
            r = tk.update(_R(d), None) if len(d) else tk.update(_R(np.zeros((0, 5), np.float32)), None)
            tms[k] = (time.perf_counter() - t0) * 1000
            # cot: x1,y1,x2,y2,id,score,cls,idx
            if len(r):
                for row in r:
                    ids_by_frame[k].append(int(row[4])); life.setdefault(int(row[4]), []).append(k)
                top = r[np.argmax(r[:, 5])]
                prim[k] = int(top[4]); pw.append(float(top[2] - top[0]))
                out.append((k, int(top[4]), *[round(float(v), 1) for v in top[:4]], round(float(top[5]), 3)))
        det_ok = np.array([bool(((dets[:, 0] == k) & (dets[:, 5] >= a.conf)).any()) for k in range(n)]) if len(dets) else np.zeros(n, bool)
        ntrk = np.array([len(x) for x in ids_by_frame]); has = ntrk > 0
        g = gaps(has)
        pids = [p for p in prim if p is not None]
        idsw = sum(1 for i in range(1, len(pids)) if pids[i] != pids[i - 1])
        long_tr = sum(1 for v in life.values() if len(v) / fps > 0.5)
        tot = ms + tms
        rows.append(dict(video=name, frames=n, fps=round(float(fps), 2), conf=a.conf, tracker=a.tracker,
                         det_rate=round(float(det_ok.mean()), 4), det_frames=int(det_ok.sum()), one_target_rate=round(float((ntrk == 1).mean()), 4),
                         multi_rate=round(float((ntrk > 1).mean()), 4), tracked_rate=round(float(has.mean()), 4),
                         n_ids=len(life), id_switches=idsw, n_gaps=len(g), max_gap_frames=max(g) if g else 0, max_gap_s=round(max(g) / fps, 2) if g else 0,
                         long_tracks_0p5s=long_tr, w_median=round(float(np.median(pw)), 1) if pw else 0,
                         ms_det_med=round(float(np.median(ms)), 2), ms_det_p95=round(float(np.percentile(ms, 95)), 2),
                         ms_trk_med=round(float(np.median(tms)), 3), ms_tot_med=round(float(np.median(tot)), 2), ms_tot_p95=round(float(np.percentile(tot, 95)), 2),
                         fb_rate=round(float(z['fb'].mean()), 3)))
        if a.tracks_dir:
            os.makedirs(a.tracks_dir, exist_ok=True)
            np.savetxt(f'{a.tracks_dir}/{name}.csv', np.array(out, dtype=float).reshape(-1, 7), delimiter=',', header='frame,id,x1,y1,x2,y2,conf', comments='', fmt='%g')
    with open(a.out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(a.out, len(rows))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest='cmd', required=True)
    d = sp.add_parser('detect'); d.add_argument('--tag'); d.add_argument('--weights', required=True); d.add_argument('--cls', type=int, default=0)
    d.add_argument('--mode', default='full'); d.add_argument('--win', type=int, default=320); d.add_argument('--imgsz', type=int, default=640)
    d.add_argument('--dconf', type=float, default=0.1); d.add_argument('--threads', type=int, default=2); d.add_argument('--shard'); d.add_argument('--only'); d.add_argument('--out', required=True)
    t = sp.add_parser('track'); t.add_argument('--det', required=True); t.add_argument('--tracker', default='bytetrack'); t.add_argument('--conf', type=float, default=0.25)
    t.add_argument('--out', required=True); t.add_argument('--tracks-dir')
    a = ap.parse_args()
    detect(a) if a.cmd == 'detect' else track(a)