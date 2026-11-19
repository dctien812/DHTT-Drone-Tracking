"""MMFW-UAV: (c) nhan, (d) thong ke khung theo to hop, (e) quy doi ve anh 2304 px, (f) chuoi, (g) cap Wide/Zoom - tinh tren TOAN BO.
Chay: python -I vision/tools/mmfw/02_labels_stats.py   (can numpy + PIL; doc vision/data/mmfw-uav/extracted)
Ket qua: vision/results/mmfw_stats/{boxes.csv,label_summary.csv,stats_combo.csv,project_scale.csv,sequences.csv,pairs.csv}
"""
import csv, os, re, sys, json, collections
import xml.etree.ElementTree as ET
from multiprocessing import Pool
import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
EX = os.path.join(ROOT, "data", "mmfw-uav", "extracted")
RES = os.path.join(ROOT, "results", "mmfw_stats")
SETS = {"D": "Fixed-wing-UAV-D", "D'": "Fixed-wing-UAV-D'", "E": "Fixed-wing-UAV-E", "E'": "Fixed-wing-UAV-E'"}
DIRS = ["Top_Down", "Horizontal", "Bottom_Up"]
TYPES = ["Wide", "Zoom", "Infrared"]
GAP_BREAK = 10      # chuoi moi neu khoang cach chi so khung > 10
JUMP_BREAK = 0.15   # hoac tam khung nhay > 15% be rong anh
PCT = [5, 25, 50, 75, 95]


def parse_one(a):
    s, d, t = a
    ad = os.path.join(EX, SETS[s], d, t + "_Anns")
    idr = os.path.join(EX, SETS[s], d, t + "_Imgs")
    rows = []
    xs = {f[:-4] for f in os.listdir(ad) if f.endswith(".xml") and not f.startswith("._")}
    js = {f[:-4] for f in os.listdir(idr) if f.endswith(".jpg") and not f.startswith("._")}
    for stem in sorted(xs | js):
        r = dict(set=s, dir=d, type=t, stem=stem, has_xml=stem in xs, has_jpg=stem in js, xw=0, xh=0, iw=0, ih=0, fn_ok=1, nobj=0,
                 names="", boxes="", err="")
        if stem in js:
            try:
                with Image.open(os.path.join(idr, stem + ".jpg")) as im:
                    r["iw"], r["ih"] = im.size
            except Exception as e:
                r["err"] = "jpg:" + repr(e)[:60]
        if stem in xs:
            try:
                root = ET.parse(os.path.join(ad, stem + ".xml")).getroot()
                r["xw"] = int(root.find("size/width").text)
                r["xh"] = int(root.find("size/height").text)
                r["fn_ok"] = int((root.findtext("filename") or "") == stem + ".jpg")
                bs, ns = [], []
                for o in root.findall("object"):
                    ns.append(o.findtext("name"))
                    bb = o.find("bndbox")
                    bs.append([int(float(bb.findtext(k))) for k in ("xmin", "ymin", "xmax", "ymax")])
                r["nobj"] = len(bs)
                r["names"] = "|".join(ns)
                r["boxes"] = json.dumps(bs)
            except Exception as e:
                r["err"] += " xml:" + repr(e)[:60]
        rows.append(r)
    return rows


def pc(a):
    a = np.asarray(a, float)
    return [round(float(x), 4) for x in np.percentile(a, PCT)] if len(a) else [""] * 5


def main():
    os.makedirs(RES, exist_ok=True)
    tasks = [(s, d, t) for s in SETS for d in DIRS for t in TYPES]
    with Pool(8) as p:
        res = p.map(parse_one, tasks)
    rows = [r for rs in res for r in rs]
    fields = list(rows[0].keys())
    with open(os.path.join(RES, "boxes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows)

    # ---------- (c) tom tat nhan ----------
    names = collections.Counter()
    nobj_hist = collections.Counter()
    with open(os.path.join(RES, "label_summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["set", "dir", "type", "images", "xml", "missing_xml", "missing_jpg", "read_err", "xml_size_ne_jpg", "filename_tag_ne_stem",
                    "no_box", "no_box_pct", "multi_box", "max_boxes", "box_out_of_image", "box_zero_size", "box_touch_edge", "box_touch_edge_pct"])
        for key, grp in itertools_groupby(rows, lambda r: (r["set"], r["dir"], r["type"])):
            n = len(grp)
            nx = sum(r["has_xml"] for r in grp)
            miss_x = sum(1 for r in grp if not r["has_xml"])
            miss_j = sum(1 for r in grp if not r["has_jpg"])
            err = sum(1 for r in grp if r["err"])
            sz = sum(1 for r in grp if r["has_xml"] and r["has_jpg"] and (r["xw"], r["xh"]) != (r["iw"], r["ih"]))
            fnb = sum(1 for r in grp if r["has_xml"] and not r["fn_ok"])
            nb = 0; mb = 0; mx = 0; oob = 0; zero = 0; edge = 0; nbox = 0
            for r in grp:
                for nm in (r["names"].split("|") if r["names"] else []):
                    names[nm] += 1
                nobj_hist[r["nobj"]] += 1
                if r["has_xml"] and r["nobj"] == 0:
                    nb += 1
                if r["nobj"] > 1:
                    mb += 1
                mx = max(mx, r["nobj"])
                W, H = (r["iw"] or r["xw"]), (r["ih"] or r["xh"])
                for x0, y0, x1, y1 in (json.loads(r["boxes"]) if r["boxes"] else []):
                    nbox += 1
                    if x0 < 0 or y0 < 0 or x1 > W or y1 > H:
                        oob += 1
                    if x1 <= x0 or y1 <= y0:
                        zero += 1
                    if x0 <= 1 or y0 <= 1 or x1 >= W - 1 or y1 >= H - 1:
                        edge += 1
            w.writerow([*key, n, nx, miss_x, miss_j, err, sz, fnb, nb, round(100 * nb / max(nx, 1), 3), mb, mx, oob, zero, edge,
                        round(100 * edge / max(nbox, 1), 3)])
    print("class names:", dict(names))
    print("boxes/image histogram (all combos):", dict(sorted(nobj_hist.items())))

    # ---------- (d)(e) thong ke theo to hop (khung lon nhat moi anh) ----------
    def big_box(r):
        bs = json.loads(r["boxes"]) if r["boxes"] else []
        return max(bs, key=lambda b: (b[2] - b[0]) * (b[3] - b[1])) if bs else None

    with open(os.path.join(RES, "stats_combo.csv"), "w", newline="", encoding="utf-8") as f, \
            open(os.path.join(RES, "project_scale.csv"), "w", newline="", encoding="utf-8") as g:
        w = csv.writer(f)
        w.writerow(["set", "dir", "type", "images_with_box", "resolution(s)"] + [f"w_px_p{p}" for p in PCT] + [f"h_px_p{p}" for p in PCT] +
                   [f"w_ratio_p{p}" for p in PCT] + [f"h_ratio_p{p}" for p in PCT] + ["touch_edge_pct"])
        v = csv.writer(g)
        v.writerow(["set", "dir", "type", "images_with_box"] + [f"w2304_p{p}" for p in PCT] +
                   ["pct_lt16", "pct_16_57", "pct_57_200", "pct_gt200"])
        groups = list(itertools_groupby(rows, lambda r: (r["set"], r["dir"], r["type"])))
        # them dong gop theo huong x loai (4 bo gop) va tat ca
        pooled = collections.defaultdict(list)
        for key, grp in groups:
            pooled[("ALL", key[1], key[2])] += grp
            pooled[("ALL", "ALL", key[2])] += grp
        for key, grp in groups + sorted(pooled.items()):
            ws, hs, wr, hr, e, W2 = [], [], [], [], 0, []
            res_c = collections.Counter()
            for r in grp:
                b = big_box(r)
                if b is None:
                    continue
                W = r["iw"] or r["xw"]
                res_c[f'{W}x{r["ih"] or r["xh"]}'] += 1
                bw, bh = b[2] - b[0], b[3] - b[1]
                ws.append(bw); hs.append(bh); wr.append(bw / W); hr.append(bh / W)
                W2.append(bw / W * 2304)
                H = r["ih"] or r["xh"]
                if b[0] <= 1 or b[1] <= 1 or b[2] >= W - 1 or b[3] >= H - 1:
                    e += 1
            if not ws:
                continue
            n = len(ws)
            w.writerow([*key, n, ";".join(f"{k}:{c}" for k, c in res_c.most_common())] + pc(ws) + pc(hs) + pc(wr) + pc(hr) + [round(100 * e / n, 3)])
            W2 = np.array(W2)
            v.writerow([*key, n] + pc(W2) + [round(100 * float((W2 < 16).mean()), 2), round(100 * float(((W2 >= 16) & (W2 < 57)).mean()), 2),
                                             round(100 * float(((W2 >= 57) & (W2 <= 200)).mean()), 2), round(100 * float((W2 > 200).mean()), 2)])

    # ---------- (f) chuoi + (g) cap ----------
    idx = {}
    for r in rows:
        idx[(r["set"], r["dir"], r["type"], r["stem"])] = r
    pat = re.compile(r"^(\d+)_(\d+)_(\d+)$")
    with open(os.path.join(RES, "sequences.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["set", "dir", "type", "images", "name_prefixes", "idx_min", "idx_max", "pairs_gap1", "pairs_gap_gt1", "gap_gt10", "gap_gt100",
                    "step_p50_pct_W", "step_p95_pct_W", "step_max_pct_W", "pairs_jump_gt15pct", "sequences(gap>10|jump>15%)", "sequences(gap>1)",
                    "sequences(gap>100)", "seq_len_min", "seq_len_median", "seq_len_max"])
        for key, grp in groups:
            items = []
            for r in grp:
                m = pat.match(r["stem"])
                b = big_box(r)
                if m and b:
                    W = r["iw"] or r["xw"]
                    items.append((m.group(1) + "_" + m.group(2), int(m.group(3)), (b[0] + b[2]) / 2 / W, (b[1] + b[3]) / 2 / W))
            items.sort()
            gaps, steps, brk, br1, br100, jumps = [], [], 1, 1, 1, 0
            lens, cur = [], 1
            for a, b in zip(items, items[1:]):
                if a[0] != b[0]:
                    gaps.append(10 ** 9); brk += 1; br1 += 1; br100 += 1; lens.append(cur); cur = 1
                    continue
                g = b[1] - a[1]
                gaps.append(g)
                st = float(np.hypot(b[2] - a[2], b[3] - a[3]))
                if g == 1:
                    steps.append(st)
                j = st > JUMP_BREAK
                jumps += j
                if g > 1: br1 += 1
                if g > 100: br100 += 1
                if g > GAP_BREAK or j:
                    brk += 1; lens.append(cur); cur = 1
                else:
                    cur += 1
            lens.append(cur)
            gp = np.array(gaps)
            w.writerow([*key, len(items), len({i[0] for i in items}), items[0][1], items[-1][1], int((gp == 1).sum()), int((gp > 1).sum()),
                        int((gp > 10).sum()), int((gp > 100).sum()),
                        round(100 * float(np.median(steps)), 3) if steps else "", round(100 * float(np.percentile(steps, 95)), 3) if steps else "",
                        round(100 * float(max(steps)), 3) if steps else "", jumps, brk, br1, br100, min(lens), int(np.median(lens)), max(lens)])

    with open(os.path.join(RES, "pairs.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["set", "dir", "stems_wide", "stems_zoom", "stems_ir", "same_stem_set_W_Z", "same_stem_set_W_IR", "n_pairs_with_box",
                    "zoom_over_wide_w_p5", "p50", "p95", "corr_dlogw_wide_zoom_adjacent", "corr_log_w_wide_zoom"])
        for s in SETS:
            for d in DIRS:
                st = {t: {r["stem"] for r in rows if (r["set"], r["dir"], r["type"]) == (s, d, t) and r["has_jpg"]} for t in TYPES}
                ratio, lw, lz, seq = [], [], [], []
                for stem in sorted(st["Wide"] & st["Zoom"]):
                    bw, bz = big_box(idx[(s, d, "Wide", stem)]), big_box(idx[(s, d, "Zoom", stem)])
                    if bw and bz:
                        rw = idx[(s, d, "Wide", stem)]; rz = idx[(s, d, "Zoom", stem)]
                        ww = (bw[2] - bw[0]) / (rw["iw"] or rw["xw"]); wz = (bz[2] - bz[0]) / (rz["iw"] or rz["xw"])
                        if ww > 0 and wz > 0:
                            ratio.append(wz / ww); lw.append(np.log(ww)); lz.append(np.log(wz)); seq.append(stem)
                # chenh lech lien tiep chi cho cac cap co chi so khung lien tiep
                dw, dz = [], []
                for i in range(1, len(seq)):
                    a, b = pat.match(seq[i - 1]), pat.match(seq[i])
                    if a and b and a.group(1, 2) == b.group(1, 2) and int(b.group(3)) - int(a.group(3)) == 1:
                        dw.append(lw[i] - lw[i - 1]); dz.append(lz[i] - lz[i - 1])
                c1 = float(np.corrcoef(dw, dz)[0, 1]) if len(dw) > 3 else ""
                c2 = float(np.corrcoef(lw, lz)[0, 1]) if len(lw) > 3 else ""
                w.writerow([s, d, len(st["Wide"]), len(st["Zoom"]), len(st["Infrared"]), st["Wide"] == st["Zoom"], st["Wide"] == st["Infrared"], len(ratio)] +
                           (pc(ratio)[:1] + pc(ratio)[2:3] + pc(ratio)[4:5] if ratio else ["", "", ""]) + [round(c1, 4) if c1 != "" else "", round(c2, 4) if c2 != "" else ""])
    print("done 02")


def itertools_groupby(rows, keyf):
    d = collections.OrderedDict()
    for r in rows:
        d.setdefault(keyf(r), []).append(r)
    return list(d.items())


if __name__ == "__main__":
    main()
