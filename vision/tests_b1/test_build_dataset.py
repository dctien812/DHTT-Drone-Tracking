"""Test pha do cho vision/scripts/b1a/build_dataset.py (ham thuan/nho cho script dung tap va huan luyen).

Chu ky da chot:
  plan_fold(split, birds_train, birds_fa, base_seeds=None) -> [job, ...]\n     base_seeds mac dinh {"pos": 6001, "off": 6002, "bg": 6003} (dung nhu run_step6.py)
     split = {"train": {seg: [khung]}, "val": {...}, "test": {...}} ; birds_* = [ten anh chim]
     job = {"split": "train"|"val"|"test"|"birds_fa", "seg": seg | "birds", "frame": ten, "kind": "pos"|"bg"|"off"|"bird",
            "seed": int}
     train, val: moi khung 1 pos + 1 bg ; test: moi khung pos + off + bg ; birds_train -> split "train", kind "bird"
     (nhan rong) ; birds_fa -> split "birds_fa", kind "bird" ; seed = prep_crops.frame_seed(base_seeds[kind], seg, frame) (anh chim: int bat ky, khong co trong chi muc buoc 6):
     CHI phu thuoc (base_seed, kind, seg, frame), khong phu thuoc tap/luot -> dung lai duoc giua cac luot.
     (doan, khung) cua test xuat hien o train/val -> ValueError. Ket qua tat dinh, khong phu thuoc thu tu dict dau vao.
  dataset_yaml(root, names=("airplane",)) -> chuoi yaml: path: <root> ; train: images/train ; val: images/val ;
     test: images/test ; names: {0: airplane}
  train_args(fold, seed, device, epochs=40, imgsz=480, batch=16) -> dict cho YOLO.train (khong co khoa "data");
     device khac "cpu" -> them "_pre": {"cudnn_enabled": False}
"""
import csv
import os
import re

import pytest

HERE_SEGS = ["D/Top_Down", "D'/Top_Down", "E/Top_Down", "E'/Top_Down"]


def fr(n, p="0_0_"):
    return [p + "%06d" % i for i in range(1, n + 1)]


def make_split():
    return {"train": {"D/Top_Down": fr(10), "D'/Top_Down": fr(6)},
            "val": {"D/Top_Down": fr(3), "D'/Top_Down": fr(2)},
            "test": {"E/Top_Down": fr(5)}}


def key(j):
    return (j["split"], j["seg"], j["frame"], j["kind"])


def test_plan_counts_follow_formula():
    from build_dataset import plan_fold
    # val dung ten khung khac train de khong bi tinh la rong nhau (khong lien quan den kiem tra test)
    split = {"train": {"D/Top_Down": fr(10)}, "val": {"D/Top_Down": fr(3, "9_0_")}, "test": {"E/Top_Down": fr(5)}}
    jobs = plan_fold(split, ["b1", "b2"], ["f1", "f2", "f3"])
    by = lambda s, k: [j for j in jobs if j["split"] == s and j["kind"] == k]
    assert len(by("train", "pos")) == 10 and len(by("train", "bg")) == 10
    assert len(by("val", "pos")) == 3 and len(by("val", "bg")) == 3
    assert len(by("test", "pos")) == 5 and len(by("test", "off")) == 5 and len(by("test", "bg")) == 5
    assert len(by("train", "bird")) == 2 and len(by("birds_fa", "bird")) == 3
    assert len(jobs) == 2 * (10 + 3) + 3 * 5 + 2 + 3
    assert not [j for j in jobs if j["split"] in ("train", "val") and j["kind"] == "off"]
    assert not [j for j in jobs if j["split"] == "test" and j["kind"] == "bird"]
    assert all(j["seg"] == "birds" for j in jobs if j["kind"] == "bird")
    assert {j["frame"] for j in jobs if j["kind"] == "bird"} == {"b1", "b2", "f1", "f2", "f3"}


def test_plan_birds_fa_stay_out_of_train():
    from build_dataset import plan_fold
    jobs = plan_fold(make_split(), ["b1"], ["f1"])
    assert [j["frame"] for j in jobs if j["split"] == "train" and j["kind"] == "bird"] == ["b1"]
    assert [j["frame"] for j in jobs if j["split"] == "birds_fa"] == ["f1"]
    assert not [j for j in jobs if j["frame"] == "f1" and j["split"] != "birds_fa"]


def test_plan_rejects_test_frames_in_train_or_val():
    from build_dataset import plan_fold
    bad = make_split()
    bad["train"]["E/Top_Down"] = fr(2)                      # 2 khung dau cua doan test lot vao train
    with pytest.raises(ValueError):
        plan_fold(bad, [], [])
    bad2 = make_split()
    bad2["val"]["E/Top_Down"] = fr(1)
    with pytest.raises(ValueError):
        plan_fold(bad2, [], [])


def test_plan_is_deterministic_and_order_independent():
    from build_dataset import plan_fold
    a = make_split()
    b = {k: dict(reversed(list(v.items()))) for k, v in reversed(list(a.items()))}
    assert plan_fold(a, ["x", "y"], ["z"]) == plan_fold(a, ["x", "y"], ["z"])
    assert sorted(map(str, plan_fold(a, ["x", "y"], ["z"]))) == sorted(map(str, plan_fold(b, ["y", "x"], ["z"])))


def test_plan_seeds_default_to_step6_bases_and_override():
    from build_dataset import plan_fold
    from prep_crops import frame_seed
    jobs = plan_fold(make_split(), [], [])
    want = {"pos": 6001, "off": 6002, "bg": 6003}
    for j in jobs:
        assert j["seed"] == frame_seed(want[j["kind"]], j["seg"], j["frame"])
    assert {j["kind"] for j in jobs} == {"pos", "bg", "off"}
    jobs2 = plan_fold(make_split(), [], [], base_seeds={"pos": 1, "off": 2, "bg": 3})
    assert all(j["seed"] == frame_seed({"pos": 1, "off": 2, "bg": 3}[j["kind"]], j["seg"], j["frame"]) for j in jobs2)


def test_plan_seeds_are_per_kind_per_frame_and_independent_of_fold():
    from build_dataset import plan_fold
    jobs = plan_fold(make_split(), ["b1", "b2"], [])
    seeds = {j["kind"]: j["seed"] for j in jobs
             if j["seg"] == "D/Top_Down" and j["frame"] == "0_0_000001" and j["split"] == "train"}
    assert set(seeds) == {"pos", "bg"} and seeds["pos"] != seeds["bg"]
    assert all(isinstance(j["seed"], int) for j in jobs)
    pos_seeds = [j["seed"] for j in jobs if j["kind"] == "pos" and j["split"] == "train" and j["seg"] == "D/Top_Down"]
    assert len(set(pos_seeds)) == len(pos_seeds)             # khac khung -> khac seed
    other = {"train": {"E/Top_Down": fr(4)}, "val": {"E/Top_Down": fr(1, "9_0_")},
             "test": {"D/Top_Down": fr(10)}}
    s2 = {j["kind"]: j["seed"] for j in plan_fold(other, [], [])
          if j["seg"] == "D/Top_Down" and j["frame"] == "0_0_000001"}
    assert s2["pos"] == seeds["pos"] and s2["bg"] == seeds["bg"] and "off" in s2


INDEX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "b1a", "index")


def _index_rows(name, n=10):
    p = os.path.join(INDEX_DIR, name + ".csv")
    if not os.path.isfile(p):
        return None
    with open(p, newline="") as f:
        rows = list(csv.DictReader(f))
    step = max(1, len(rows) // n)
    return rows[::step][:n]


@pytest.mark.skipif(not os.path.isdir(INDEX_DIR), reason="khong co chi muc that cua buoc 6")
def test_plan_seeds_match_real_step6_index():
    """30 khoa (10 moi tap) lay tu chi muc csv that: seed plan_fold sinh ra == cot seed da luu."""
    from build_dataset import plan_fold
    checked = 0
    for part in ("train", "val", "test"):
        rows = _index_rows(part)
        if not rows:
            pytest.skip("thieu chi muc " + part)
        split = {"train": {}, "val": {}, "test": {}}
        for r in rows:
            split[part].setdefault(r["segment"], []).append(r["frame"])
        got = {(j["seg"], j["frame"], j["kind"]): j["seed"] for j in plan_fold(split, [], [])}
        for r in rows:
            assert got[(r["segment"], r["frame"], r["kind"])] == int(r["seed"]), r
            checked += 1
    assert checked == 30

def test_dataset_yaml_single_class_relative_paths():
    from build_dataset import dataset_yaml
    text = dataset_yaml("data/b1a/foldE")
    lines = [ln.rstrip() for ln in text.splitlines()]
    assert "path: data/b1a/foldE" in lines
    assert "train: images/train" in lines and "val: images/val" in lines and "test: images/test" in lines
    assert "names:" in lines and "  0: airplane" in lines
    try:
        import yaml
    except ImportError:
        return
    d = yaml.safe_load(text)
    assert d["names"] == {0: "airplane"} and d["train"] == "images/train" and d["path"] == "data/b1a/foldE"


def test_dataset_yaml_custom_names():
    from build_dataset import dataset_yaml
    lines = dataset_yaml("r", names=("a", "b")).splitlines()
    assert "  0: a" in lines and "  1: b" in lines


EXPECTED = dict(single_cls=True, imgsz=480, deterministic=True, workers=3,
                hsv_h=0.015, hsv_s=0.7, hsv_v=0.4, fliplr=0.5, flipud=0.0, mosaic=0.5, close_mosaic=10,
                scale=0.25, epochs=40, batch=16)


def test_train_args_pinned_values_cpu():
    from build_dataset import train_args
    a = train_args("EE", 1, "cpu")
    for k, v in EXPECTED.items():
        assert a[k] == v, k
    assert a["amp"] is False                          # amp bi bo qua tren CPU
    assert a["seed"] == 1 and a["device"] == "cpu"
    assert "_pre" not in a and "data" not in a
    assert a["project"].replace("\\", "/").endswith("runs/b1a")


def test_train_args_overrides_and_gpu_prestep_and_amp():
    from build_dataset import train_args
    a = train_args("DD", 2, "0", epochs=5, imgsz=480, batch=8)
    assert a["epochs"] == 5 and a["batch"] == 8 and a["device"] == "0"
    assert a["amp"] is True
    assert a["_pre"] == {"cudnn_enabled": False}
    g = train_args("EE", 0, "cuda:0")
    assert g["_pre"] == {"cudnn_enabled": False} and g["amp"] is True


def test_split_pre_separates_pre_key():
    from build_dataset import split_pre, train_args
    gpu = train_args("EE", 0, "0")
    kw, pre = split_pre(gpu)
    assert "_pre" not in kw and pre == {"cudnn_enabled": False}
    assert kw == {k: v for k, v in gpu.items() if k != "_pre"}
    assert "_pre" in gpu                              # khong sua dict dau vao
    kw2, pre2 = split_pre(train_args("EE", 0, "cpu"))
    assert pre2 == {} and "_pre" not in kw2


def test_train_args_name_unique_per_fold_and_seed_and_filesystem_safe():
    from build_dataset import train_args
    names = set()
    for fold in ("DD", "EE", "final"):
        for seed in (0, 1):
            n = train_args(fold, seed, "cpu")["name"]
            assert re.fullmatch(r"[A-Za-z0-9_.-]+", n), n
            names.add(n)
    assert len(names) == 6


def test_train_args_has_no_machine_absolute_paths():
    from build_dataset import train_args
    for dev in ("cpu", "0"):
        for k, v in train_args("EE", 0, dev).items():
            if isinstance(v, str):
                assert not v.startswith("/") and not re.match(r"^[A-Za-z]:[\\/]", v), (k, v)
                assert "\\" not in v, (k, v)
