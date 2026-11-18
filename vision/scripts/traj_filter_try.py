"""THU NGHIEM NGOAI TUYEN: phan biet may bay / drone bang dac trung quy dao cua vet bam (track). KHONG tich hop vao lab.
Dung lai runs/b1_det/ft_full/*.npz (nhan dien theo khung, model ft_v8n cu), chay lai ByteTrack tren npz (khong chay model),
tinh dac trung tren N khung dau cua moi track, chon nguong kieu bo-ra-mot-video (4 fold), in bang ket qua.
Chay: bash scripts/run_traj_filter_try.sh   (hoac python -I traj_filter_try.py [--conf 0.25] [--no-cam])
Ra: results/traj/{tracks_c*.csv, camshift.csv, features_*.csv, results.csv}   (chi numpy, khong can pandas)
"""
import argparse, csv, glob, os, sys, time
import numpy as np

ROOT = '/mnt/d/Personal/Drone-Tracking/vision'
DET = ROOT + '/runs/b1_det/ft_full'
OUT = ROOT + '/results/traj'
sys.path.insert(0, ROOT + '/scripts')
import track_videos as tv  # chi dung make_tracker, _R, vids (khong chay main)

WINS = (15, 30, 60)          # so khung quan sat (0,5 / 1 / 2 giay o 30 fps)
FEATS = ['straight', 'lin_res', 'speed_w', 'speed_cv', 'acc_w', 'turn', 'dlogw', 'logw_res', 'ar_mean', 'ar_std', 'w_med']


def label(v):
    return 1 if v.startswith('V_AIRPLANE') else 0  # VIDEO.MOV (xem bang mat 3 khung) la drone


def write_csv(f, header, rows):
    with open(f, 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(header); w.writerows(rows)


def read_csv(f):
    with open(f) as fh:
        r = csv.reader(fh); h = next(r); return h, list(r)


# ---------------------------------------------------------------- 1. track tu npz -> {video: {id: array(frame,x1,y1,x2,y2,conf)}}
def run_tracks(conf):
    f = f'{OUT}/tracks_c{conf}.csv'
    if not os.path.exists(f):
        rows = []
        for p in sorted(glob.glob(DET + '/*.npz')):
            name = os.path.basename(p)[:-4]
            z = np.load(p); dets = z['dets']; n, fps, W, H = z['meta']
            tk = tv.make_tracker('bytetrack', conf, fps)
            for k in range(int(n)):
                d = dets[dets[:, 0] == k][:, 1:] if len(dets) else np.zeros((0, 5), np.float32)
                r = tk.update(tv._R(d), None) if len(d) else tk.update(tv._R(np.zeros((0, 5), np.float32)), None)
                for q in r:
                    rows.append((name, k, int(q[4]), *[round(float(x), 2) for x in q[:4]], round(float(q[5]), 3)))
        write_csv(f, ['video', 'frame', 'id', 'x1', 'y1', 'x2', 'y2', 'conf'], rows)
    _, rows = read_csv(f)
    tr = {}
    for r in rows:
        tr.setdefault(r[0], {}).setdefault(int(r[2]), []).append([float(x) for x in (r[1], *r[3:])])
    return {v: {i: np.array(a) for i, a in d.items()} for v, d in tr.items()}


# ---------------------------------------------------------------- 2. chuyen dong camera (dich tinh tien toan cuc, phaseCorrelate)
def run_cam():
    f = f'{OUT}/camshift.csv'
    if not os.path.exists(f):
        import cv2
        cv2.setNumThreads(1)
        rows = []
        for p in tv.vids():
            name = os.path.splitext(os.path.basename(p))[0]
            c = cv2.VideoCapture(p); prev = None; k = 0; win = None
            while True:
                ok, fr = c.read()
                if not ok: break
                g = cv2.cvtColor(cv2.resize(fr, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
                if win is None: win = cv2.createHanningWindow((g.shape[1], g.shape[0]), cv2.CV_32F)
                if prev is None: dx = dy = resp = 0.0
                else:
                    (dx, dy), resp = cv2.phaseCorrelate(prev, g, win)  # dich noi dung anh prev->g (o nua do phan giai)
                    dx *= 2; dy *= 2
                rows.append((name, k, round(dx, 3), round(dy, 3), round(resp, 3))); prev = g; k += 1
        write_csv(f, ['video', 'frame', 'dx', 'dy', 'resp'], rows)
    _, rows = read_csv(f)
    cam = {}
    for r in rows: cam.setdefault(r[0], []).append([float(x) for x in r[2:]])
    return {v: np.array(a) for v, a in cam.items()}  # cot dx,dy,resp theo khung


# ---------------------------------------------------------------- 3. dac trung (tren N dong dau cua track)
def feats(a, cam, N):
    """a: array track (frame,x1,y1,x2,y2,conf) sap theo frame. cam: array (n,3) dx,dy,resp hoac None."""
    if len(a) < N: return None
    a = a[:N]
    t = a[:, 0].astype(int)
    if t[-1] - t[0] > 1.5 * N: return None
    g = np.arange(t[0], t[-1] + 1)
    w = a[:, 3] - a[:, 1]; h = a[:, 4] - a[:, 2]
    cx = (a[:, 1] + a[:, 3]) / 2; cy = (a[:, 2] + a[:, 4]) / 2
    if cam is not None:  # tru dich tich luy cua nen -> vi tri so voi nen
        cum = np.cumsum(cam[:, :2], 0); cx = cx - cum[t, 0]; cy = cy - cum[t, 1]
    I = lambda z: np.interp(g, t, z)
    cx, cy, w, h = I(cx), I(cy), I(w), I(h)
    wm = float(np.median(w))
    k5 = np.ones(5) / 5
    sx, sy = np.convolve(cx, k5, 'valid'), np.convolve(cy, k5, 'valid')
    v = np.stack([np.diff(sx), np.diff(sy)], 1); sp = np.hypot(v[:, 0], v[:, 1])
    path = sp.sum(); net = np.hypot(sx[-1] - sx[0], sy[-1] - sy[0])
    tt = g - g.mean()
    res = [z - np.polyval(np.polyfit(tt, z, 1), tt) for z in (cx, cy)]
    lin_res = float(np.sqrt(np.mean(res[0] ** 2 + res[1] ** 2))) / wm
    acc = np.diff(np.stack([sx, sy], 1), 2, axis=0)
    v5 = np.stack([sx[5:] - sx[:-5], sy[5:] - sy[:-5]], 1)
    ok = np.hypot(v5[:, 0], v5[:, 1]) > 0.25 * wm
    if ok.sum() >= 3:
        ang = np.arctan2(v5[ok, 1], v5[ok, 0]); turn = float(np.abs((np.diff(ang) + np.pi) % (2 * np.pi) - np.pi).mean())
    else:
        turn = np.pi  # dung yen / khong du chuyen dong -> coi nhu rat doi huong (giong drone)
    lw = np.log(np.maximum(w, 1.0)); co = np.polyfit(tt, lw, 1); lres = lw - np.polyval(co, tt)
    ar = w / np.maximum(h, 1.0)
    return dict(straight=net / (path + 1e-6), lin_res=lin_res, speed_w=float(np.median(sp)) / wm,
                speed_cv=float(sp.std() / (sp.mean() + 0.01 * wm)), acc_w=float(np.sqrt(np.mean(np.sum(acc ** 2, 1)))) / wm,
                turn=turn, dlogw=abs(float(co[0])), logw_res=float(np.sqrt(np.mean(lres ** 2))),
                ar_mean=float(np.median(ar)), ar_std=float(ar.std() / ar.mean()), w_med=wm)


def build_features(tr, cam):
    """-> dict N -> dict cot (video[], id[], y[], len[], feat...) chi gom track co du N khung; them 'all' = tat ca track"""
    allt = [(v, i, len(a)) for v in sorted(tr) for i, a in sorted(tr[v].items())]
    out = {}
    for N in WINS:
        rows = []
        for v in sorted(tr):
            for i, a in sorted(tr[v].items()):
                a = a[np.argsort(a[:, 0])]
                f = feats(a, cam[v] if cam is not None else None, N)
                if f: rows.append(dict(video=v, id=i, y=label(v), len=len(a), **f))
        out[N] = {k: np.array([r[k] for r in rows]) for k in ['video', 'id', 'y', 'len'] + FEATS}
    return out, allt


# ---------------------------------------------------------------- 4. danh gia bo-ra-mot-video
def auc(s, y, wt):
    """AUC co trong so (diem cao = may bay); dong hang tinh nua."""
    pos, neg = y == 1, y == 0
    if wt[pos].sum() == 0 or wt[neg].sum() == 0: return float('nan')
    tot = 0.0
    for p, sp in zip(wt[pos], s[pos]):
        tot += p * (wt[neg][s[neg] < sp].sum() + 0.5 * wt[neg][s[neg] == sp].sum())
    return tot / (wt[pos].sum() * wt[neg].sum())


def pick(s, y, wt, mode):
    """nguong tren tap train: loai neu s >= thr (s da doi dau, cao = may bay)."""
    P, D = wt[y == 1].sum(), wt[y == 0].sum()
    best = None
    for t in np.unique(s):
        r = s >= t
        tpr = wt[r & (y == 1)].sum() / P; fpr = wt[r & (y == 0)].sum() / D
        if mode == 'youden': val = tpr - fpr
        else:
            if fpr > float(mode[3:]) / 100: continue
            val = tpr - 1e-3 * fpr
        if best is None or val > best[0]: best = (val, t)
    return best[1] if best else np.inf


def evaluate(D, N, tot, feat, mode, folds):
    """4 fold: moi fold giu ra 1 video may bay + 1/4 video drone (xen ke); nguong/huong chon tren phan con lai."""
    rej = {0: 0.0, 1: 0.0}; trej = {0: 0, 1: 0}; tev = {0: 0, 1: 0}; vid = {}; dirs = ''
    fo = np.array([folds[v] for v in D['video']]); y = D['y']; L = D['len'].astype(float); s0 = D[feat]
    for k in range(4):
        trn, tst = fo != k, fo == k
        a = auc(s0[trn], y[trn], L[trn]); sg = 1 if (np.isnan(a) or a >= 0.5) else -1; dirs += '+' if sg > 0 else '-'
        thr = pick(sg * s0[trn], y[trn], L[trn], mode)
        r = (sg * s0 >= thr) & tst
        for yv in (0, 1):
            m = tst & (y == yv); tev[yv] += int(m.sum()); trej[yv] += int((r & m).sum()); rej[yv] += float((L[r & m] - N).sum())
        for v in set(D['video'][tst]):
            if label(v):
                m = r & (D['video'] == v); vid[v] = float((L[m] - N).sum()) / max(sum(l for vv, _, l in tot if vv == v), 1)
    fr = {yv: sum(l for v, _, l in tot if label(v) == yv) for yv in (0, 1)}
    return dict(auc_pooled=round(auc(s0, y, L), 3), dirs=dirs, air_trk_rej=f'{trej[1]}/{tev[1]}', drone_trk_rej=f'{trej[0]}/{tev[0]}',
                air_frame_rej=round(rej[1] / fr[1], 3), drone_frame_rej=round(rej[0] / fr[0], 3), vid=vid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--conf', type=float, default=0.25)
    ap.add_argument('--no-cam', action='store_true')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    tr = run_tracks(a.conf)
    ntr = sum(len(d) for d in tr.values())
    print(f'tracks: {ntr} track, {len(tr)} video ({sum(label(v) for v in tr)} may bay) [{time.time()-t0:.0f}s]', flush=True)
    cam = None if a.no_cam else run_cam()
    if cam is not None:
        sh = {v: np.hypot(c[:, 0], c[:, 1]) for v, c in cam.items()}
        pl = [round(float(np.median(sh[v])), 2) for v in sh if label(v)]
        dm = np.array([np.median(sh[v]) for v in sh if not label(v)])
        write_csv(f'{OUT}/camshift_summary.csv', ['video', 'y', 'median_px_per_frame', 'p90', 'median_resp'],
                  [(v, label(v), round(float(np.median(sh[v])), 3), round(float(np.percentile(sh[v], 90)), 3), round(float(np.median(cam[v][:, 2])), 3)) for v in sorted(sh)])
        print('dich nen/khung (px, 640x512): may bay median', pl, '| drone: median-of-median %.2f, p90 %.2f, max %.2f; so drone >1 px/khung: %d/%d  [%ds]' % (
            np.median(dm), np.percentile(dm, 90), dm.max(), (dm > 1).sum(), len(dm), time.time() - t0), flush=True)
    vs = sorted(tr); dr = [v for v in vs if not label(v)]; pl = [v for v in vs if label(v)]
    folds = {v: i for i, v in enumerate(pl)}
    folds.update({v: j % 4 for j, v in enumerate(dr)})
    res = []
    for cmode in (['raw'] if cam is None else ['raw', 'comp']):
        FT, allt = build_features(tr, cam if cmode == 'comp' else None)
        for N in WINS:
            for feat in FEATS:
                for mode in ('youden', 'fpr10'):
                    o = evaluate(FT[N], N, allt, feat, mode, folds)
                    res.append(dict(cam=cmode, secs=round(N / 30, 2), N=N, feat=feat, mode=mode, **{k: v for k, v in o.items() if k != 'vid'},
                                    **{('air_' + v[-3:]): round(x, 3) for v, x in sorted(o['vid'].items())}))
        write_csv(f'{OUT}/features_{cmode}_c{a.conf}.csv', ['N', 'video', 'id', 'y', 'len'] + FEATS,
                  [[N, FT[N]['video'][i], FT[N]['id'][i], FT[N]['y'][i], FT[N]['len'][i]] + [round(float(FT[N][f][i]), 4) for f in FEATS] for N in WINS for i in range(len(FT[N]['y']))])
        if cmode == 'raw':
            fa = sum(l for v, _, l in allt if label(v)); fd = sum(l for v, _, l in allt if not label(v))
            print('\nso track (conf %.2f): may bay %d (%d khung-co-track) | drone %d (%d khung-co-track)' % (
                a.conf, sum(label(v) for v, _, _ in allt), fa, sum(1 - label(v) for v, _, _ in allt), fd))
            for N in WINS: print(f'  N={N}: track du khung: may bay {(FT[N]["y"]==1).sum()}, drone {(FT[N]["y"]==0).sum()}')
    keys = ['cam', 'secs', 'N', 'feat', 'mode', 'auc_pooled', 'dirs', 'air_trk_rej', 'drone_trk_rej', 'air_frame_rej', 'drone_frame_rej'] + sorted({k for r in res for k in r if k.startswith('air_00')})
    write_csv(f'{OUT}/results.csv', keys, [[r.get(k, '') for k in keys] for r in res])
    print('\nMOC KHONG LOC: khung may bay bi loai 0% (con goi drone 100%), khung drone bi loai nham 0%')
    print('BANG (bo-ra-mot-video 4 fold; air_frame_rej = ti le khung may bay bi loai SAU khi quyet dinh; drone_frame_rej = khung drone bi loai nham;')
    print('      *_trk_rej = so track bi loai / so track du N khung; auc_pooled = AUC tren toan bo, KHONG phai bo-ra-mot):')
    for cmode in sorted({r['cam'] for r in res}):
        for mode in ('youden', 'fpr10'):
            print(f'\n--- cam={cmode} mode={mode} ---')
            print('secs feat       auc    dirs  air_trk  drone_trk   air_fr  drone_fr')
            for r in res:
                if r['cam'] == cmode and r['mode'] == mode:
                    print('%4.1f %-10s %5.3f %5s %8s %10s %7.3f %8.3f' % (r['secs'], r['feat'], r['auc_pooled'], r['dirs'], r['air_trk_rej'], r['drone_trk_rej'], r['air_frame_rej'], r['drone_frame_rej']))
    print(f'\nxong {time.time()-t0:.0f}s; csv: {OUT}/results.csv')


if __name__ == '__main__':
    main()
