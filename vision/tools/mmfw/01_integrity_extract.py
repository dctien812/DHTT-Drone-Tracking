"""MMFW-UAV: (a) sha256 + CRC (testzip) tung zip, (b) giai nen toan bo (bo qua ._* va __MACOSX), dem lai theo thu muc.
Chay: python -I vision/tools/mmfw/01_integrity_extract.py   (chay 4 zip song song; tu dong bo qua file da giai nen dung kich thuoc)
Ket qua: vision/results/mmfw_stats/integrity.csv, extract_counts.csv
"""
import csv, hashlib, os, sys, time, zipfile, collections
from multiprocessing import Pool

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DATA = os.path.join(ROOT, "data", "mmfw-uav")
OUT = os.path.join(DATA, "extracted")
RES = os.path.join(ROOT, "results", "mmfw_stats")
ZIPS = ["Fixed-wing-UAV-D.zip", "Fixed-wing-UAV-D'.zip", "Fixed-wing-UAV-E.zip", "Fixed-wing-UAV-E'.zip"]


def junk(name):
    return name.startswith("__MACOSX/") or os.path.basename(name.rstrip("/")).startswith("._")


def work(zn):
    zp = os.path.join(DATA, zn)
    t0 = time.time()
    h = hashlib.sha256()
    with open(zp, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    t_sha = time.time() - t0
    z = zipfile.ZipFile(zp)
    t0 = time.time()
    bad = z.testzip()
    t_crc = time.time() - t0
    # catalog (khong tinh file rac)
    cat = collections.Counter()
    for i in z.infolist():
        if i.is_dir() or junk(i.filename):
            continue
        cat[(os.path.dirname(i.filename), i.filename.rsplit(".", 1)[-1].lower())] += 1
    t0 = time.time()
    nex = 0
    for i in z.infolist():
        if junk(i.filename):
            continue
        dest = os.path.join(OUT, *i.filename.split("/"))
        if i.is_dir():
            os.makedirs(dest, exist_ok=True)
            continue
        if os.path.exists(dest) and os.path.getsize(dest) == i.file_size:
            continue
        z.extract(i, OUT)
        nex += 1
    t_ex = time.time() - t0
    return dict(zip=zn, size=os.path.getsize(zp), sha256=h.hexdigest(), testzip=("OK" if bad is None else "BAD:" + bad),
                n_entries=len(z.infolist()), t_sha=round(t_sha), t_crc=round(t_crc), t_extract=round(t_ex), newly_extracted=nex,
                cat=dict(cat))


if __name__ == "__main__":
    os.makedirs(RES, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    with Pool(4) as p:
        rs = p.map(work, ZIPS)
    with open(os.path.join(RES, "integrity.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["zip", "bytes", "sha256", "testzip_crc", "entries", "sec_sha", "sec_crc", "sec_extract"])
        for r in rs:
            w.writerow([r["zip"], r["size"], r["sha256"], r["testzip"], r["n_entries"], r["t_sha"], r["t_crc"], r["t_extract"]])
    # dem lai tren dia va doi chieu voi muc luc
    with open(os.path.join(RES, "extract_counts.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["dir", "ext", "catalog", "on_disk", "match"])
        allok = True
        for r in rs:
            for (d, ext), n in sorted(r["cat"].items()):
                dd = os.path.join(OUT, *d.split("/"))
                cnt = len([x for x in os.listdir(dd) if x.lower().endswith("." + ext) and not x.startswith("._")]) if os.path.isdir(dd) else 0
                ok = cnt == n
                allok &= ok
                w.writerow([d, ext, n, cnt, "OK" if ok else "MISMATCH"])
    for r in rs:
        print(r["zip"], r["testzip"], r["sha256"], r["size"])
    print("ALL_COUNTS_MATCH" if allok else "COUNT_MISMATCH")
    leftovers = [os.path.join(dp, x) for dp, _, fs in os.walk(OUT) for x in fs if x.startswith("._")]
    print("junk_on_disk", len(leftovers))
