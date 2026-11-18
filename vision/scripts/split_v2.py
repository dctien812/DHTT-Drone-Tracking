"""V2 buoc 2: chia train/val/test THEO NHOM (khong tach nhom gan trung) cho DUT va Det-Fly + kiem ro ri sau chia.
Nhom = thanh phan lien thong cua do thi: hai anh noi nhau neu tuong quan xam 32x32 >= 0.90 (chat hon 0.95 cua buoc kiem truoc);
Det-Fly dung nguong 0.95 (0.90 gop ca bo thanh 1 nhom lon; khoi so khung lien tiep cung gop het); sau khi chia, khung train/val cach khung test <= 10 so khung bi loai (drop). Gop DUT train+val+test thanh mot bo roi chia lai.
Kiem ro ri (anh test co anh train gan trung): (1) corr >= 0.95 (nhu buoc truoc), (2) corr >= 0.90, (3) dHash 8x8 (tu anh 32x32) Hamming <= 6,
(4) Det-Fly: khoang cach khung gan nhat test-train cung thu muc.
Ghi data/v2/split_dut.csv, split_detfly.csv, results/v2/split_summary.md. Chay: python -I split_v2.py
"""
import numpy as np, csv, random, collections, cv2

V = '/mnt/d/Personal/Drone-Tracking/vision'
O = V + '/data/v2'
TARGET = {'dut': (1500, 700), 'detfly': (1500, 500)}  # (test, val) so anh
THR_GROUP = {'dut': 0.90, 'detfly': 0.95}  # Det-Fly: khung lien tiep hay tuong quan thap (may bay ban xa) nen them khoi ID, xem duoi


def norm(F):
    F = F - F.mean(1, keepdims=True)
    return F / np.maximum(np.linalg.norm(F, axis=1, keepdims=True), 1e-6)


def groups(F, thr, extra=()):
    N = norm(F); n = len(N); par = list(range(n))

    def f(x):
        while par[x] != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    for i in range(0, n, 500):
        C = N[i:i + 500] @ N.T
        ii, jj = np.nonzero(C >= thr)
        for a, b in zip(ii + i, jj):
            par[f(a)] = f(b)
    for a, b in extra:
        par[f(a)] = f(b)
    return np.array([f(i) for i in range(n)])


def assign(g, nt, nv, seed):
    ids = sorted(set(g.tolist())); cnt = collections.Counter(g.tolist())
    random.Random(seed).shuffle(ids)
    split = {}; ct = cv = 0
    for c in ids:
        s = cnt[c]
        if ct < nt and ct + s <= nt * 1.3:
            split[c] = 'test'; ct += s
        elif cv < nv and cv + s <= nv * 1.3:
            split[c] = 'val'; cv += s
        else:
            split[c] = 'train'
    return np.array([split[c] for c in g])


def dhash(F):
    out = np.zeros((len(F), 64), bool)
    for i, f in enumerate(F):
        d = cv2.resize(f.reshape(32, 32), (9, 8), interpolation=cv2.INTER_AREA).astype(np.int16)
        out[i] = (d[:, 1:] > d[:, :-1]).ravel()
    return out


def leak(F, sp, label, ids=None):
    N = norm(F); H = dhash(F)
    te = np.flatnonzero(sp == 'test'); tr = np.flatnonzero(sp == 'train')
    mx = np.zeros(len(te)); mh = np.zeros(len(te), int)
    for i in range(0, len(te), 300):
        C = N[te[i:i + 300]] @ N[tr].T
        mx[i:i + 300] = C.max(1)
        for k, t in enumerate(te[i:i + 300]):
            mh[i + k] = (H[tr] != H[t]).sum(1).min()
    r = dict(n_test=len(te), corr95=float((mx >= 0.95).mean()), corr90=float((mx >= 0.90).mean()), corr85=float((mx >= 0.85).mean()),
             dhash6=float((mh <= 6).mean()), maxcorr_median=float(np.median(mx)))
    return r


lines = ['# Chia du lieu V2 (theo nhom) va kiem ro ri', '']
for name in ('dut', 'detfly'):
    z = np.load(f'{O}/feat_{name}.npz'); F = z['F']; stem = z['stem']
    extra = []
    if name == 'detfly':
        sc = z['scene']; num = np.array([int(s) for s in stem])
    g = groups(F, THR_GROUP[name], extra)
    sp = assign(g, *TARGET[name], seed=3)
    if name == 'detfly':
        te_i = np.flatnonzero(sp == 'test')
        for i in np.flatnonzero(sp != 'test'):
            m = te_i[sc[te_i] == sc[i]]
            if len(m) and np.abs(num[m] - num[i]).min() <= 10:
                sp[i] = 'drop'
    cnt = collections.Counter(g.tolist())
    lines += [f'## {name}: {len(F)} anh, {len(cnt)} nhom (nguong {THR_GROUP[name]}), nhom lon nhat {sorted(cnt.values())[-5:]}',
              f'so anh: ' + ', '.join(f'{s}={int((sp == s).sum())}' for s in ('train', 'val', 'test', 'drop')) +
              f'; so nhom: ' + ', '.join(f'{s}={len(set(g[sp == s].tolist()))}' for s in ('train', 'val', 'test', 'drop'))]
    if name == 'detfly':
        for s in ('train', 'val', 'test'):
            lines.append(f'  Det-Fly {s}: ' + ', '.join(f'thu muc {d}: {int(((sp == s) & (sc == d)).sum())}' for d in sorted(set(sc))))
        te = np.flatnonzero(sp == 'test'); tr = np.flatnonzero(sp == 'train')
        dd = []
        for t in te:
            m = (sc[tr] == sc[t])
            dd.append(np.abs(num[tr][m] - num[t]).min() if m.any() else 99999)
        dd = np.array(dd)
        lines.append(f'  khung train gan nhat (cung thu muc) cua anh test: trung vi {int(np.median(dd))}, nho nhat {int(dd.min())}, so anh test cach <=5 khung: {int((dd <= 5).sum())}')
    r = leak(F, sp, name)
    lines.append('  ro ri (ti le anh test co anh train gan trung): ' + ', '.join(f'{k}={v:.4f}' if isinstance(v, float) else f'{k}={v}' for k, v in r.items()))
    lines.append('')
    with open(f'{O}/split_{name}.csv', 'w', newline='') as f:
        w = csv.writer(f)
        if name == 'dut':
            w.writerow(['orig_split', 'stem', 'group', 'split']); w.writerows(zip(z['split'], stem, g, sp))
        else:
            w.writerow(['scene_dir', 'stem', 'group', 'split']); w.writerows(zip(z['scene'], stem, g, sp))
    print('\n'.join(lines[-8:]), flush=True)
# so sanh: chia goc cua DUT (buoc kiem truoc)
z = np.load(f'{O}/feat_dut.npz'); r = leak(z['F'], z['split'], 'dut-goc')
lines.append('## Doi chung: chia goc cua tac gia DUT (cung phep do): ' + ', '.join(f'{k}={v:.4f}' if isinstance(v, float) else f'{k}={v}' for k, v in r.items()))
open(V + '/results/v2/split_summary.md', 'w').write('\n'.join(lines) + '\n')
print(lines[-1])
