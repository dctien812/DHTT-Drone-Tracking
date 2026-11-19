"""B1a buoc 6(c): kiem ro ri cheo giua 12 doan. Dac trung: xam 32x32 (nhu verify/leak_features.py) tu anh goc
doc giam 1/4 (960x540). Do: tuong quan Pearson (corr) va RMS chenh lech muc xam (rms) cua lang gieng gan nhat.
Chay (WSL): cd /mnt/d/Personal/Drone-Tracking/vision && ~/venv-vision/bin/python scripts/b1a/leak_step6.py feats|frames|bg
"""
import csv
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cv2  # noqa: E402
import numpy as np  # noqa: E402

import prep_split as ps  # noqa: E402

cv2.setNumThreads(1)
VISION = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.join(VISION, "data", "mmfw-uav", "extracted")
RES = os.path.join(VISION, "results", "b1a", "step6")
DATA = os.path.join(VISION, "data", "b1a")
N_SAMPLE = 400
THRS = (0.90, 0.95, 0.98, 0.99)


def feat(path):
    g = cv2.imread(path, cv2.IMREAD_REDUCED_GRAYSCALE_4)
    if g is None:
        raise SystemExit("doc loi " + path)
    return cv2.resize(g, (32, 32), interpolation=cv2.INTER_AREA).ravel().astype(np.float32)


def feat_crop(path):
    g = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    return cv2.resize(g, (32, 32), interpolation=cv2.INTER_AREA).ravel().astype(np.float32)


def norm(F):
    F = F - F.mean(1, keepdims=True)
    return F / np.maximum(np.linalg.norm(F, axis=1, keepdims=True), 1e-6)


def nn_corr(Q, R, self_excl=False):
    C = norm(Q) @ norm(R).T
    if self_excl:
        np.fill_diagonal(C, -2)
    return C.max(1)


def nn_rms(Q, R, self_excl=False):
    q2 = (Q ** 2).sum(1)[:, None]
    r2 = (R ** 2).sum(1)[None, :]
    D = np.maximum(q2 + r2 - 2 * Q @ R.T, 0) / Q.shape[1]
    if self_excl:
        np.fill_diagonal(D, 1e9)
    return np.sqrt(D.min(1))


def stage_feats():
    segs = ps.discover_segments(ROOT)
    keys, jobs = [], []
    for s in sorted(segs):
        a, d = ps.parse_segment_id(s)
        for fr in segs[s]:
            keys.append((s, fr))
            jobs.append(os.path.join(ROOT, ps._PREFIX + a, d, "Wide_Imgs", fr + ".jpg"))
    with Pool(12) as p:
        F = np.array(p.map(feat, jobs, chunksize=32), np.float32)
    np.savez(os.path.join(RES, "leak_feats.npz"), seg=np.array([k[0] for k in keys]),
             frame=np.array([k[1] for k in keys]), F=F)
    print("feats", F.shape)


def sample_idx(n, k=N_SAMPLE):
    return np.unique(np.linspace(0, n - 1, min(k, n)).round().astype(int))


def matrix_report(feats_by_seg, title, L):
    segs = sorted(feats_by_seg)
    n = len(segs)
    Mc = np.zeros((n, n))
    Mr = np.zeros((n, n))
    Mf = np.zeros((n, n))
    pooled = {}
    for i, a in enumerate(segs):
        for j, b in enumerate(segs):
            c = nn_corr(feats_by_seg[a], feats_by_seg[b], a == b)
            r = nn_rms(feats_by_seg[a], feats_by_seg[b], a == b)
            Mc[i, j], Mr[i, j], Mf[i, j] = np.median(c), np.median(r), np.mean(c >= 0.95)
            pooled[(a, b)] = (c, r)
    names = [s.replace("/", ":").replace("Top_Down", "TD").replace("Horizontal", "HZ").replace("Bottom_Up", "BU") for s in segs]
    for nm, M, fmt in (("trung vi corr gan nhat (hang -> cot; cheo = cung doan, bo chinh no)", Mc, "%.2f"),
                       ("ti le corr>=0.95", Mf, "%.2f"),
                       ("trung vi RMS muc xam gan nhat", Mr, "%.1f")):
        L.append("\n### %s: %s (n mau/doan: %s)" % (title, nm, sorted({len(v) for v in feats_by_seg.values()})))
        L.append("| |" + "|".join(names) + "|")
        L.append("|" + "---|" * (n + 1))
        for i in range(n):
            L.append("| %s |" % names[i] + "|".join(fmt % M[i, j] for j in range(n)) + "|")
    return segs, pooled


def set_of(s):
    return ps.parse_segment_id(s)[0]


def group_stats(segs, pooled, title, L):
    def agg(fa, fb, same_dir=None, label=""):
        cs, rs = [], []
        for a in segs:
            for b in segs:
                if not (fa(a) and fb(b)) or a == b:
                    continue
                da, db = ps.parse_segment_id(a)[1], ps.parse_segment_id(b)[1]
                if same_dir is True and da != db:
                    continue
                if same_dir is False and da == db:
                    continue
                cs.append(pooled[(a, b)][0])
                rs.append(pooled[(a, b)][1])
        if not cs:
            return
        c, r = np.concatenate(cs), np.concatenate(rs)
        L.append("| %s | %d | %.3f | %.3f | %.3f | %s | %.1f |" % (
            label, len(c), np.median(c), np.percentile(c, 5), np.percentile(c, 95),
            " / ".join("%.3f" % np.mean(c >= t) for t in THRS), np.median(r)))
    L.append("\n### %s: tong hop theo nhom (moi mau cua nhom hang -> lang gieng gan nhat trong doan cot)" % title)
    L.append("| nhom | n mau | corr trung vi | p5 | p95 | ti le >=0.90/0.95/0.98/0.99 | RMS trung vi |")
    L.append("|---|---|---|---|---|---|---|")
    self_c = [(pooled[(a, a)][0], pooled[(a, a)][1]) for a in segs]
    c, r = np.concatenate([x[0] for x in self_c]), np.concatenate([x[1] for x in self_c])
    L.append("| CUNG DOAN (moc 'ro chac chan') | %d | %.3f | %.3f | %.3f | %s | %.1f |" % (
        len(c), np.median(c), np.percentile(c, 5), np.percentile(c, 95),
        " / ".join("%.3f" % np.mean(c >= t) for t in THRS), np.median(r)))
    D = lambda s: set_of(s) in ("D",)
    Dp = lambda s: set_of(s) == "D'"
    E = lambda s: set_of(s) == "E"
    Ep = lambda s: set_of(s) == "E'"
    TR = lambda s: set_of(s) in ("D", "D'")
    TE = lambda s: set_of(s) in ("E", "E'")
    for lab, fa, fb in (("D -> D'", D, Dp), ("D' -> D", Dp, D), ("E -> E'", E, Ep), ("E' -> E", Ep, E),
                        ("D,D' -> E,E'", TR, TE), ("E,E' -> D,D'", TE, TR), ("D -> E", D, E), ("D' -> E'", Dp, Ep)):
        for sd, sl in ((True, "cung huong"), (False, "khac huong")):
            agg(fa, fb, sd, "%s, %s" % (lab, sl))
        agg(fa, fb, None, "%s, moi huong" % lab)
    # giua cac doan KHAC trong cung bo
    agg(D, D, False, "D -> D khac huong")
    agg(E, E, False, "E -> E khac huong")


def stage_frames():
    z = np.load(os.path.join(RES, "leak_feats.npz"))
    seg, frame, F = z["seg"], z["frame"], z["F"]
    L = ["# Ro ri cheo (khung): dac trung xam 32x32\n"]
    by = {s: np.where(seg == s)[0] for s in sorted(set(seg))}
    feats = {s: F[idx[sample_idx(len(idx))]] for s, idx in by.items()}
    L.append("Mau: %d khung/doan chia deu theo thu tu (doan co %s khung)." % (N_SAMPLE, {s: len(i) for s, i in by.items()}))
    # lien ke
    L.append("\n### Moc: tuong quan khung i ~ i+1 trong doan (day du)")
    for s, idx in by.items():
        X = norm(F[idx])
        a = (X[:-1] * X[1:]).sum(1)
        L.append("- %s: trung vi %.4f, p5 %.4f" % (s, np.median(a), np.percentile(a, 5)))
    segs, pooled = matrix_report(feats, "KHUNG", L)
    group_stats(segs, pooled, "KHUNG", L)
    # kiem thu vs hoc/val (day du)
    L.append("\n### Kiem thu (10.103 khung) -> hoc/val that su dung (1.153 + 1.279) va -> toan bo D, D' (8.552)")
    key = {(s, f): i for i, (s, f) in enumerate(zip(seg, frame))}
    tv = []
    for k in ("train", "val"):
        with open(os.path.join(DATA, "split", k + ".txt")) as f:
            tv += [key[(l.split("\t")[1], l.rstrip("\n").split("\t")[2])] for l in f]
    te = [i for i, s in enumerate(seg) if set_of(s) in ("E", "E'")]
    allD = [i for i, s in enumerate(seg) if set_of(s) in ("D", "D'")]
    for nm, ref in (("hoc+val dung that", tv), ("toan bo D,D'", allD)):
        c = nn_corr(F[te], F[ref])
        r = nn_rms(F[te], F[ref])
        L.append("- kiem thu -> %s (n_ref=%d): corr gan nhat min/p5/p50/p95/max = %s; ti le>=0.90/0.95/0.98/0.99 = %s; RMS nho nhat = %.2f, p5 %.2f, p50 %.2f"
                 % (nm, len(ref), np.round(np.percentile(c, [0, 5, 50, 95, 100]), 3).tolist(),
                    [round(float(np.mean(c >= t)), 4) for t in THRS], r.min(), np.percentile(r, 5), np.median(r)))
        top = np.argsort(-c)[:5]
        L.append("    - 5 khung kiem thu giong nhat: %s" % [(seg[te[i]], frame[te[i]], round(float(c[i]), 4)) for i in top])
    # E-E' day du
    Ei = [i for i, s in enumerate(seg) if set_of(s) == "E"]
    Epi = [i for i, s in enumerate(seg) if set_of(s) == "E'"]
    for nm, a, b in (("E -> E' (day du)", Ei, Epi), ("E' -> E (day du)", Epi, Ei)):
        c = nn_corr(F[a], F[b])
        L.append("- %s: corr trung vi %.3f, p5 %.3f, ti le>=0.95 %.3f, >=0.99 %.3f" % (
            nm, np.median(c), np.percentile(c, 5), np.mean(c >= .95), np.mean(c >= .99)))
    open(os.path.join(RES, "leak_frames.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


def stage_near():
    """Khung kiem thu co lang gieng hoc/val voi corr>=0.98: thuoc doan nao, khop voi doan hoc nao."""
    z = np.load(os.path.join(RES, "leak_feats.npz"))
    seg, frame, F = z["seg"], z["frame"], z["F"]
    key = {(s, f): i for i, (s, f) in enumerate(zip(seg, frame))}
    tv = []
    for k in ("train", "val"):
        with open(os.path.join(DATA, "split", k + ".txt")) as f:
            tv += [key[(l.split("\t")[1], l.rstrip("\n").split("\t")[2])] for l in f]
    te = [i for i, s in enumerate(seg) if set_of(s) in ("E", "E'")]
    C = norm(F[te]) @ norm(F[tv]).T
    j, c = C.argmax(1), C.max(1)
    q2 = (F[te] ** 2).sum(1)
    out = []
    for th in (0.95, 0.98):
        sel = np.where(c >= th)[0]
        L = {}
        for i in sel:
            L[str(seg[te[i]])] = L.get(str(seg[te[i]]), 0) + 1
        print("corr>=%.2f: %d khung kiem thu; theo doan: %s" % (th, len(sel), L))
        M = {}
        for i in sel:
            k = (str(seg[te[i]]), str(seg[tv[j[i]]]))
            M[k] = M.get(k, 0) + 1
        print("   cap (doan kiem thu, doan hoc/val gan nhat):", M)
    for i in np.argsort(-c)[:8]:
        rms = float(np.sqrt(((F[te[i]] - F[tv[j[i]]]) ** 2).mean()))
        print("   ", seg[te[i]], frame[te[i]], "<->", seg[tv[j[i]]], frame[tv[j[i]]], "corr %.4f rms %.2f" % (c[i], rms))


def stage_bg():
    L = ["# Ro ri cheo (vung cat nen): xam 32x32 tren vung 480x480\n"]
    feats = {}
    for k in ("train", "val", "test"):
        with open(os.path.join(DATA, "index", k + ".csv")) as f:
            rows = [r for r in csv.DictReader(f) if r["kind"] == "bg" and r["path"]]
        by = {}
        for r in rows:
            by.setdefault(r["segment"], []).append(r["path"])
        for s, ps_ in by.items():
            by[s] = ps_
        for s, lst in by.items():
            feats.setdefault(s, []).extend(os.path.join(DATA, "yolo", "images", p) for p in lst)
    out = {}
    with Pool(12) as p:
        for s, lst in feats.items():
            lst = sorted(lst)
            idx = sample_idx(len(lst))
            out[s] = np.array(p.map(feat_crop, [lst[i] for i in idx]), np.float32)
    L.append("So vung nen mau/doan: %s (train+val+test cua doan)" % {s: len(v) for s, v in out.items()})
    segs, pooled = matrix_report(out, "NEN", L)
    group_stats(segs, pooled, "NEN", L)
    open(os.path.join(RES, "leak_bg.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"feats": stage_feats, "frames": stage_frames, "bg": stage_bg, "near": stage_near}[sys.argv[1]]()
