"""B1a buoc 12 (a): dung 3 tap huan luyen YOLO (EE, DD, final) tu vung cat buoc 6 co san.

Khong tao vung cat moi: vung cat pos/bg cua moi khung da co trong data/b1a/yolo (hoc/val = D,D' ; test = E,E')
vi do_frame tat dinh theo (loai, doan, khung) nen vung cat cua khung E dung cho lượt DD la chinh vung cat da tao.
Moi anh/nhan duoc HARD-LINK (cung o dia, khong chep du lieu) vao data/b1a/sets/<fold>/images|labels/<train|val>.
Chay: python run_build.py     (can .venv-gpu hoac bat ky python co numpy; chi doc/ghi lien ket, nhe nhung CHI chay sau _srchG3_DONE)
"""
import csv
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_dataset as bd  # noqa: E402
import prep_split as ps  # noqa: E402

VISION = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.join(VISION, "data", "mmfw-uav", "extracted")
DATA = os.path.join(VISION, "data", "b1a")
YOLO = os.path.join(DATA, "yolo")
INDEX = os.path.join(DATA, "index")
BIRD_FA = os.path.join(DATA, "birds_fa")
SETS = os.path.join(DATA, "sets")
MANIFEST = os.path.join(DATA, "split", "test_manifest.tsv")
MANIFEST_SHA = "7c67757cee4d2c3a81d3f87bc9d5519e5765c95f35e976a2178d48b07859e848"
OUT = os.path.join(VISION, "results", "b1a", "train")
EXPECT = {"DD": (1375, 506, 8552), "EE": (1153, 428, 10103), "final": (2528, 934, 0)}
VAL_SPARSE_N = 3


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def link(src, dst):
    if os.path.exists(dst):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        import shutil
        shutil.copyfile(src, dst)


def read_index():
    idx, name_to_frame = {}, {}
    for part in ("train", "val", "test"):
        with open(os.path.join(INDEX, part + ".csv"), newline="") as f:
            for r in csv.DictReader(f):
                idx[(r["segment"], r["frame"], r["kind"])] = r
                if r["path"]:
                    name_to_frame[os.path.splitext(os.path.basename(r["path"]))[0]] = (r["segment"], r["frame"])
    return idx, name_to_frame


def flat(part):
    return {(s, f) for s, fr in part.items() for f in fr}


def main():
    assert sha(MANIFEST) == MANIFEST_SHA, "test_manifest sha256 khac truoc khi dung"
    print("sha256 manifest TRUOC:", sha(MANIFEST))
    frames = ps.discover_segments(ROOT)
    folds = ps.all_folds(frames, val_sparse_n=VAL_SPARSE_N)
    folds["final"] = ps.final_split(frames, val_sparse_n=VAL_SPARSE_N)
    man = set()
    with open(MANIFEST) as f:
        for line in f:
            s, fr = line.rstrip("\n").split("\t")
            man.add((s, fr))
    idx, n2f = read_index()
    birds_train = sorted(os.path.splitext(n)[0] for n in os.listdir(os.path.join(YOLO, "images", "train")) if n.startswith("bird_"))
    birds_fa = sorted(os.path.splitext(n)[0] for n in os.listdir(BIRD_FA))
    print("chim hoc:", len(birds_train), "chim bao dong gia (khong dung hoc):", len(birds_fa))
    report = {"manifest_sha_before": sha(MANIFEST), "val_sparse_n": VAL_SPARSE_N, "folds": {}}
    ok_all = True
    for fold in ("EE", "DD", "final"):
        sp = folds[fold]
        n_tr, n_va, n_te = (sum(len(v) for v in sp[k].values()) for k in ("train", "val", "test"))
        exp = EXPECT[fold]
        print("\n== %s: khung hoc/val/kiem = %d/%d/%d (mong doi %s) %s" % (fold, n_tr, n_va, n_te, exp, "KHOP" if (n_tr, n_va, n_te) == exp else "LECH"))
        ok_all &= (n_tr, n_va, n_te) == exp
        tr, va, te = flat(sp["train"]), flat(sp["val"]), flat(sp["test"])
        print("   khung kiem thu nam trong hoc:", len(te & tr), "| trong val:", len(te & va), "| hoc va val trung nhau:", len(tr & va))
        ok_all &= not (te & tr) and not (te & va) and not (tr & va)
        if fold == "EE":
            print("   tap kiem EE == manifest dong bang:", te == man)
            ok_all &= te == man
        if fold == "final":
            print("   (final khong co tap kiem; khung manifest nam trong hoc/val: %d, dung thiet ke)" % len((tr | va) & man))
        jobs = bd.plan_fold(sp, birds_train, birds_fa)  # nem ValueError neu khung kiem lot vao hoc/val
        cnt = {}
        for part in ("train", "val"):
            n_img = n_none = n_pos = 0
            for j in (x for x in jobs if x["split"] == part and x["kind"] != "bird"):
                r = idx[(j["seg"], j["frame"], j["kind"])]
                assert str(j["seed"]) == r["seed"], ("seed lech", j, r["seed"])
                if not r["path"]:
                    n_none += 1
                    continue
                name = os.path.splitext(os.path.basename(r["path"]))[0]
                src_split = r["split"]
                link(os.path.join(YOLO, "images", r["path"]), os.path.join(SETS, fold, "images", part, name + ".png"))
                link(os.path.join(YOLO, "labels", src_split, name + ".txt"), os.path.join(SETS, fold, "labels", part, name + ".txt"))
                n_img += 1
                n_pos += j["kind"] == "pos"
            nb = 0
            if part == "train":
                for b in birds_train:
                    link(os.path.join(YOLO, "images", "train", b + ".png"), os.path.join(SETS, fold, "images", "train", b + ".png"))
                    link(os.path.join(YOLO, "labels", "train", b + ".txt"), os.path.join(SETS, fold, "labels", "train", b + ".txt"))
                    nb += 1
            cnt[part] = {"pos": n_pos, "bg": n_img - n_pos, "bg_none": n_none, "birds": nb, "total_images": n_img + nb}
        os.makedirs(os.path.join(SETS, fold, "images", "test"), exist_ok=True)  # dataset_yaml co khoa test
        yml = os.path.join(SETS, fold, "data.yaml")
        with open(yml, "w", newline="\n") as f:
            f.write(bd.dataset_yaml(os.path.join(SETS, fold).replace("\\", "/")))
        # kiem lai tren dia: ten anh thuc te -> khung; khong khung kiem nao
        disk = {}
        for part in ("train", "val"):
            im = sorted(os.listdir(os.path.join(SETS, fold, "images", part)))
            lb = sorted(os.listdir(os.path.join(SETS, fold, "labels", part)))
            assert [os.path.splitext(a)[0] for a in im] == [os.path.splitext(a)[0] for a in lb], part
            fr = {n2f[os.path.splitext(a)[0]] for a in im if not a.startswith("bird_")}
            disk[part] = {"images": len(im), "labels": len(lb), "distinct_frames": len(fr),
                          "frames_in_test": len(fr & te), "frames_in_frozen_manifest": len(fr & man) if fold != "final" else None}
            print("   tren dia %s: anh %d nhan %d, khung %d, trung khung kiem cung luot: %d" % (part, len(im), len(lb), len(fr), len(fr & te)))
            ok_all &= len(fr & te) == 0
        print("   so vung cat:", cnt)
        report["folds"][fold] = {"frames": {"train": n_tr, "val": n_va, "test": n_te}, "crops": cnt, "disk": disk, "yaml": yml}
    after = sha(MANIFEST)
    print("\nsha256 manifest SAU:", after, "| khong doi:", after == MANIFEST_SHA)
    ok_all &= after == MANIFEST_SHA and ps.verify_test_manifest(MANIFEST)
    report["manifest_sha_after"] = after
    report["all_checks_ok"] = bool(ok_all)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "build_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    print("TONG KET:", "DAT" if ok_all else "KHONG DAT")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
