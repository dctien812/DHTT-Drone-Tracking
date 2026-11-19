"""Test pha do cho vision/scripts/b1a/prep_split.py (chia tap theo doan video).

Chu ky da chot:
  segment_id(set_name, direction) -> "D'/Top_Down"
  parse_segment_id(seg) -> (set_name, direction)
  parse_frame_name(name) -> (a, b, idx)            # "0_0_000012[.jpg]" -> (0, 0, 12)
  discover_segments(root) -> {seg_id: [ten khung (khong duoi), sap theo idx so]}
        root chua Fixed-wing-UAV-<bo>/<huong>/Wide_Imgs/*.jpg ; chi doc Wide_Imgs
  split_segments(frames_by_seg, sparse_n=6, val_frac=0.15, buffer=60)
        -> {"train": {seg: [...]}, "val": {seg: [...]}, "test": {seg: [...]}}
  write_test_manifest(split, path) -> sha256 hex ; ghi them path + ".sha256"
  verify_test_manifest(path) -> bool
  segment_groups(seg_ids, merge_pairs=()) -> {seg_id: nhom}
        mac dinh moi doan (bo x huong) la mot nhom; merge_pairs=[("E","E'")] gop theo (cap, huong)
        -> E/Top_Down va E'/Top_Down cung nhom (tap kiem thu con 3 nhom)
"""
import hashlib
import os

import pytest

SETS = ["D", "D'", "E", "E'"]
DIRS = ["Top_Down", "Horizontal", "Bottom_Up"]


def name(i):
    return "0_0_%06d" % i


def make_frames(n):
    return [name(i) for i in range(1, n + 1)]


def all_segments(n=1000):
    return {"%s/%s" % (s, d): make_frames(n) for s in SETS for d in DIRS}


def test_segment_id_distinguishes_primed_set():
    from prep_split import segment_id, parse_segment_id
    assert segment_id("D'", "Top_Down") == "D'/Top_Down"
    assert segment_id("D", "Top_Down") != segment_id("D'", "Top_Down")
    assert parse_segment_id("D'/Top_Down") == ("D'", "Top_Down")
    assert parse_segment_id("E/Bottom_Up") == ("E", "Bottom_Up")


def test_parse_frame_name():
    from prep_split import parse_frame_name
    assert parse_frame_name("0_0_000012") == (0, 0, 12)
    assert parse_frame_name("3_1_001425.jpg") == (3, 1, 1425)
    with pytest.raises(ValueError):
        parse_frame_name("khong_phai_ten_khung")


def test_discover_segments_reads_wide_only_and_sorts_numerically(tmp_path):
    from prep_split import discover_segments
    for s in SETS:
        for d in DIRS:
            wide = tmp_path / ("Fixed-wing-UAV-" + s) / d / "Wide_Imgs"
            wide.mkdir(parents=True)
            for i in (10, 2, 1):                     # tao khong theo thu tu
                (wide / (name(i) + ".jpg")).write_bytes(b"x")
            zoom = tmp_path / ("Fixed-wing-UAV-" + s) / d / "Zoom_Imgs"
            zoom.mkdir()
            (zoom / (name(99) + ".jpg")).write_bytes(b"x")
    segs = discover_segments(str(tmp_path))
    assert len(segs) == 12
    assert "D'/Top_Down" in segs and "E'/Bottom_Up" in segs
    assert segs["D'/Top_Down"] == [name(1), name(2), name(10)]   # sap theo so, khong theo chuoi, khong lan Zoom


def test_train_sets_vs_test_sets_and_no_segment_in_two_sets():
    from prep_split import split_segments
    out = split_segments(all_segments())
    train_segs = {s for s in out["train"] if out["train"][s]}
    assert train_segs == {"%s/%s" % (s, d) for s in ("D", "D'") for d in DIRS}
    assert set(out["val"]) == train_segs
    assert set(out["test"]) == {"%s/%s" % (s, d) for s in ("E", "E'") for d in DIRS}
    # khong doan nao o hai tap hoc/kiem thu
    assert not (set(out["train"]) & set(out["test"]))
    assert not (set(out["val"]) & set(out["test"]))


def test_test_set_keeps_every_frame_unthinned():
    from prep_split import split_segments
    out = split_segments(all_segments(1000), sparse_n=6)
    for seg, frames in out["test"].items():
        assert frames == make_frames(1000), seg


def test_val_is_last_15_percent_and_60_frame_buffer_is_dropped():
    from prep_split import split_segments
    frames = make_frames(1000)
    out = split_segments({"D/Top_Down": frames}, sparse_n=6)
    # val = 150 khung cuoi; dem = 60 khung ngay truoc val; train = 790 khung dau, lay thua moi 6
    assert out["val"]["D/Top_Down"] == frames[850:]
    assert out["train"]["D/Top_Down"] == [frames[i] for i in range(0, 790, 6)]
    buffered = set(frames[790:850])
    assert not buffered & set(out["train"]["D/Top_Down"])
    assert not buffered & set(out["val"]["D/Top_Down"])


def test_val_size_rounds_down():
    from prep_split import split_segments
    out = split_segments({"D/Top_Down": make_frames(999)})
    assert len(out["val"]["D/Top_Down"]) == 149      # floor(0.15 * 999)


def test_sparse_step_applies_to_train_only_and_is_parameter():
    from prep_split import split_segments
    frames = make_frames(1000)
    for n in (1, 4, 6, 10):
        out = split_segments({"D/Top_Down": frames, "E/Top_Down": frames}, sparse_n=n)
        assert out["train"]["D/Top_Down"] == [frames[i] for i in range(0, 790, n)]
        assert len(out["val"]["D/Top_Down"]) == 150            # val khong lay thua
        assert out["test"]["E/Top_Down"] == frames             # kiem thu khong lay thua


def test_default_sparse_step_is_6():
    from prep_split import split_segments
    frames = make_frames(1000)
    assert split_segments({"D/Top_Down": frames}) == split_segments({"D/Top_Down": frames}, sparse_n=6)
    assert len(split_segments({"D/Top_Down": frames})["train"]["D/Top_Down"]) == len(range(0, 790, 6))


def test_primed_set_names_are_routed_correctly():
    from prep_split import split_segments
    frames = make_frames(500)
    out = split_segments({"D'/Horizontal": frames, "E'/Horizontal": frames})
    assert "D'/Horizontal" in out["train"] and "D'/Horizontal" not in out["test"]
    assert "E'/Horizontal" in out["test"] and "E'/Horizontal" not in out["train"]


def test_split_is_deterministic_and_independent_of_input_order():
    from prep_split import split_segments
    a = all_segments(300)
    b = {k: list(reversed(v)) for k, v in reversed(list(a.items()))}
    assert split_segments(a) == split_segments(a)
    assert split_segments(a) == split_segments(b)


def test_short_segment_gives_empty_train_without_error():
    from prep_split import split_segments
    out = split_segments({"D/Top_Down": make_frames(70)})
    assert len(out["val"]["D/Top_Down"]) == 10        # floor(10.5)
    assert out["train"]["D/Top_Down"] == []           # 70 - 10 - 60 = 0


@pytest.mark.parametrize("n,n_val", [(50, 7), (1, 0), (0, 0), (60, 9), (69, 10)])
def test_very_short_segments_never_leak_into_train(n, n_val):
    """n - val - 60 am: cat tho frames[:n-val-60] se tra phan tu (loi); train phai rong."""
    from prep_split import split_segments
    frames = make_frames(n)
    out = split_segments({"D/Top_Down": frames})
    assert out["train"]["D/Top_Down"] == []
    assert out["val"]["D/Top_Down"] == frames[n - n_val:]
    assert len(out["val"]["D/Top_Down"]) == n_val


def test_frame_names_with_other_prefix_sort_and_parse():
    """Bo D dung tien to 1_0_ (bo khac 0_0_)."""
    from prep_split import parse_frame_name, split_segments
    assert parse_frame_name("1_0_000005") == (1, 0, 5)
    frames = ["1_0_%06d" % i for i in range(1, 501)]
    out = split_segments({"D/Horizontal": list(reversed(frames))})
    assert out["val"]["D/Horizontal"] == frames[500 - 75:]
    assert out["train"]["D/Horizontal"] == [frames[i] for i in range(0, 500 - 75 - 60, 6)]


def test_unknown_set_raises():
    from prep_split import split_segments
    with pytest.raises(ValueError):
        split_segments({"F/Top_Down": make_frames(100)})


def test_manifest_hash_matches_file_and_verifies(tmp_path):
    from prep_split import split_segments, write_test_manifest, verify_test_manifest
    split = split_segments(all_segments(200))
    p = str(tmp_path / "test_list.txt")
    digest = write_test_manifest(split, p)
    assert digest == hashlib.sha256(open(p, "rb").read()).hexdigest()
    assert open(p + ".sha256").read().strip().split()[0] == digest
    text = open(p, encoding="utf-8").read()
    assert "E'/Top_Down" in text and name(1) in text
    assert "D'/Top_Down" not in text                   # chi chua tap kiem thu
    assert verify_test_manifest(p) is True


def test_manifest_detects_tampering_and_missing_digest(tmp_path):
    from prep_split import split_segments, write_test_manifest, verify_test_manifest
    split = split_segments(all_segments(200))
    p = str(tmp_path / "test_list.txt")
    write_test_manifest(split, p)
    with open(p, "ab") as f:
        f.write(b"E/Top_Down\t0_0_999999\n")
    assert verify_test_manifest(p) is False
    q = str(tmp_path / "other.txt")
    write_test_manifest(split, q)
    os.remove(q + ".sha256")
    assert verify_test_manifest(q) is False


def test_manifest_bytes_do_not_depend_on_dict_order(tmp_path):
    from prep_split import split_segments, write_test_manifest
    a = split_segments(all_segments(200))
    b = {"train": a["train"], "val": a["val"],
         "test": dict(reversed(list(a["test"].items())))}
    assert write_test_manifest(a, str(tmp_path / "a.txt")) == write_test_manifest(b, str(tmp_path / "b.txt"))


def test_segment_groups_default_is_one_group_per_segment():
    from prep_split import segment_groups
    ids = ["%s/%s" % (s, d) for s in SETS for d in DIRS]
    g = segment_groups(ids)
    assert set(g) == set(ids)
    assert len(set(g.values())) == 12


def test_segment_groups_merge_is_per_pair_and_direction():
    """Gop (cap, huong): E/Top_Down + E'/Top_Down la mot nhom; khac huong thi khac nhom."""
    from prep_split import segment_groups
    ids = ["%s/%s" % (s, d) for s in SETS for d in DIRS]
    g = segment_groups(ids, merge_pairs=[("D", "D'"), ("E", "E'")])
    assert len(set(g.values())) == 6                   # 12 doan -> 6 nhom
    assert g["D/Top_Down"] == g["D'/Top_Down"]
    assert g["E/Bottom_Up"] == g["E'/Bottom_Up"]
    assert g["E/Top_Down"] != g["E'/Horizontal"]
    assert g["D/Top_Down"] != g["E/Top_Down"]
    test_ids = [i for i in ids if i.startswith("E")]
    gt = segment_groups(test_ids, merge_pairs=[("E", "E'")])
    assert len(set(gt.values())) == 3                  # tap kiem thu con 3 nhom khi gop
    # chi gop mot cap: D, D' van rieng le theo doan
    g1 = segment_groups(ids, merge_pairs=[("E", "E'")])
    assert g1["D/Top_Down"] != g1["D'/Top_Down"]
    assert len(set(g1.values())) == 6 + 3


def test_segment_groups_default_test_set_has_six_groups():
    from prep_split import segment_groups
    ids = ["%s/%s" % (s, d) for s in ("E", "E'") for d in DIRS]
    assert len(set(segment_groups(ids).values())) == 6


MMFW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "mmfw-uav", "extracted")


@pytest.mark.skipif(not os.path.isdir(MMFW), reason="khong co du lieu MMFW that")
def test_smoke_real_data_has_12_segments_and_expected_counts():
    from prep_split import discover_segments, split_segments
    segs = discover_segments(MMFW)
    assert len(segs) == 12
    out = split_segments(segs)
    assert sum(len(v) for k, v in segs.items() if k.split("/")[0] in ("D", "D'")) == 8552
    assert sum(len(v) for v in out["test"].values()) == 10103



# ---------------- kiem cheo THEO CAP bo (DD / EE) + final ----------------
def _seg_of(seg):
    return seg.split("/")[0]


PAIRS = {"DD": ("D", "D'"), "EE": ("E", "E'")}


def test_fold_split_accepts_one_set_or_a_sequence_of_sets():
    from prep_split import fold_split
    segs = all_segments(1000)
    one = fold_split(segs, "E'")
    assert {_seg_of(s) for s in one["test"]} == {"E'"}
    for ts in (("E", "E'"), ["E", "E'"]):
        out = fold_split(segs, ts)
        assert {_seg_of(s) for s in out["test"]} == {"E", "E'"}
        assert all(out["test"][s] == make_frames(1000) for s in out["test"])      # test day du, khong lay thua
        learn = {_seg_of(s) for s in list(out["train"]) + list(out["val"])}
        assert learn == {"D", "D'"}
        assert not (set(out["test"]) & (set(out["train"]) | set(out["val"])))


@pytest.mark.parametrize("held", [("D",), ("D'",), ("E",), ("E'",), ("D", "D'"), ("E", "E'")])
def test_fold_split_prime_names_never_confused(held):
    from prep_split import fold_split
    out = fold_split(all_segments(300), held)
    assert {_seg_of(s) for s in out["test"]} == set(held)
    learn = {_seg_of(s) for s in list(out["train"]) + list(out["val"])}
    assert learn == set(SETS) - set(held)
    assert len(out["test"]) == 3 * len(held)


def test_fold_split_uses_the_old_rules_for_train_and_val():
    from prep_split import fold_split
    frames = make_frames(1000)
    segs = {"D/Top_Down": frames, "E/Top_Down": frames, "E'/Top_Down": frames}
    out = fold_split(segs, ("E'",))
    assert out["val"]["D/Top_Down"] == frames[850:]
    assert out["train"]["D/Top_Down"] == [frames[i] for i in range(0, 790, 6)]
    assert out["val"]["E/Top_Down"] == frames[850:]                       # E la bo hoc khi chi giu E'
    assert out["test"] == {"E'/Top_Down": frames}
    out4 = fold_split(segs, "E'", sparse_n=4, val_frac=0.2, buffer=30)
    assert out4["val"]["D/Top_Down"] == frames[800:]
    assert out4["train"]["D/Top_Down"] == [frames[i] for i in range(0, 770, 4)]


def test_fold_split_val_sparse_only_thins_val():
    from prep_split import fold_split
    frames = make_frames(1000)
    segs = {"D/Top_Down": frames, "E/Top_Down": frames}
    base = fold_split(segs, "E")
    out = fold_split(segs, "E", val_sparse_n=3)
    assert out["val"]["D/Top_Down"] == frames[850:][::3]
    assert len(out["val"]["D/Top_Down"]) == 50
    assert out["train"] == base["train"] and out["test"] == base["test"]
    assert fold_split(segs, "E", val_sparse_n=1) == base                  # mac dinh 1 = nhu cu


def test_fold_split_unknown_or_empty_test_set_raises_and_is_deterministic():
    from prep_split import fold_split
    for bad in ("F", "e'", ("E", "F"), ()):
        with pytest.raises(ValueError):
            fold_split(all_segments(100), bad)
    a = all_segments(300)
    b = {k: list(reversed(v)) for k, v in reversed(list(a.items()))}
    assert fold_split(a, ("D", "D'")) == fold_split(a, ("D", "D'")) == fold_split(b, ("D'", "D"))


def test_all_folds_default_is_DD_and_EE_partitioning_every_frame_once():
    from prep_split import all_folds
    segs = all_segments(200)
    folds = all_folds(segs)
    assert set(folds) == {"DD", "EE"}
    seen = []
    for name, f in folds.items():
        seen += [(s, fr) for s, frames in f["test"].items() for fr in frames]
        assert {_seg_of(s) for s in f["test"]} == set(PAIRS[name])
        learn = {_seg_of(s) for s in list(f["train"]) + list(f["val"])}
        assert learn == set(SETS) - set(PAIRS[name])                 # khong hoc tren bo anh em
    allf = {(s, fr) for s, frames in segs.items() for fr in frames}
    assert len(seen) == len(set(seen)) == len(allf)                  # doi mot roi nhau
    assert set(seen) == allf                                         # hop = toan bo khung


def test_all_folds_custom_folds_and_options_pass_through():
    from prep_split import all_folds
    segs = {k: v for k, v in all_segments(500).items() if _seg_of(k) in ("D", "E")}
    folds = all_folds(segs, folds={"x": ("D",), "y": ("E",)}, sparse_n=3, val_sparse_n=2)
    assert set(folds) == {"x", "y"}
    assert folds["y"]["train"]["D/Top_Down"] == [make_frames(500)[i] for i in range(0, 500 - 75 - 60, 3)]
    assert folds["y"]["val"]["D/Top_Down"] == make_frames(500)[500 - 75:][::2]


def test_EE_fold_equals_existing_split_segments_in_all_three_parts():
    """Du lieu buoc 6 (chia E+E' lam kiem thu) dung lai nguyen ven."""
    from prep_split import all_folds, split_segments
    segs = all_segments(400)
    assert all_folds(segs)["EE"] == split_segments(segs)
    segs2 = all_segments(321)
    assert all_folds(segs2, sparse_n=5)["EE"] == split_segments(segs2, sparse_n=5)


def test_final_split_trains_on_all_four_sets_with_empty_test():
    from prep_split import final_split
    frames = make_frames(1000)
    out = final_split(all_segments(1000))
    assert out["test"] == {}
    assert {_seg_of(s) for s in out["train"]} == set(SETS)
    assert {_seg_of(s) for s in out["val"]} == set(SETS)
    assert out["val"]["E'/Horizontal"] == frames[850:]
    assert out["train"]["E'/Horizontal"] == [frames[i] for i in range(0, 790, 6)]
    assert final_split(all_segments(1000), val_sparse_n=3)["val"]["D/Top_Down"] == frames[850:][::3]


def test_EE_fold_manifest_equals_frozen_manifest_by_set(tmp_path):
    from prep_split import all_folds, split_segments, write_test_manifest, verify_test_manifest

    def lines(p):
        return {ln for ln in open(p, encoding="utf-8").read().splitlines() if "\t" in ln}
    segs = all_segments(200)
    old, new = str(tmp_path / "old.txt"), str(tmp_path / "ee.txt")
    write_test_manifest(split_segments(segs), old)
    write_test_manifest(all_folds(segs)["EE"], new)
    assert verify_test_manifest(new) is True
    assert lines(new) == lines(old) and len(lines(old)) == 6 * 200
