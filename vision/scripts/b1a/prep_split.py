"""B1a: chia tap theo doan video (doan = (bo, huong)), khong ro ri giua hoc/val/kiem thu."""
import hashlib
import os
import re

TRAIN_SETS = ("D", "D'")
TEST_SETS = ("E", "E'")
_PREFIX = "Fixed-wing-UAV-"
_FRAME_RE = re.compile(r"^(\d+)_(\d+)_(\d+)(?:\.[A-Za-z0-9]+)?$")


def segment_id(set_name, direction):
    return "%s/%s" % (set_name, direction)


def parse_segment_id(seg):
    set_name, direction = seg.split("/", 1)
    return set_name, direction


def parse_frame_name(name):
    m = _FRAME_RE.match(name)
    if not m:
        raise ValueError("ten khung khong hop le: %r" % name)
    return tuple(int(g) for g in m.groups())


def discover_segments(root):
    """{seg_id: [ten khung khong duoi, sap theo so]}; chi doc Wide_Imgs."""
    segs = {}
    for entry in sorted(os.listdir(root)):
        if not entry.startswith(_PREFIX):
            continue
        set_name = entry[len(_PREFIX):]
        for direction in sorted(os.listdir(os.path.join(root, entry))):
            wide = os.path.join(root, entry, direction, "Wide_Imgs")
            if not os.path.isdir(wide):
                continue
            names = [os.path.splitext(f)[0] for f in os.listdir(wide) if f.lower().endswith(".jpg")]
            segs[segment_id(set_name, direction)] = sorted(names, key=parse_frame_name)
    return segs


def split_segments(frames_by_seg, sparse_n=6, val_frac=0.15, buffer=60):
    out = {"train": {}, "val": {}, "test": {}}
    for seg in sorted(frames_by_seg):
        set_name, _ = parse_segment_id(seg)
        frames = sorted(frames_by_seg[seg], key=parse_frame_name)
        if set_name in TEST_SETS:
            out["test"][seg] = frames
        elif set_name in TRAIN_SETS:
            n = len(frames)
            n_val = int(n * val_frac + 1e-9)
            train_end = max(0, n - n_val - buffer)
            out["train"][seg] = frames[:train_end:sparse_n]
            out["val"][seg] = frames[n - n_val:]
        else:
            raise ValueError("bo khong biet: %r (doan %s)" % (set_name, seg))
    return out


def fold_split(frames_by_seg, test_sets, sparse_n=6, val_frac=0.15, buffer=60, val_sparse_n=1):
    """Giu cac bo trong test_sets (ten hoac day ten) lam kiem thu; con lai hoc/val theo quy tac cu."""
    test_sets = (test_sets,) if isinstance(test_sets, str) else tuple(test_sets)
    if not test_sets or any(t not in TRAIN_SETS + TEST_SETS for t in test_sets):
        raise ValueError("bo khong biet hoac rong: %r" % (test_sets,))
    held = {s: f for s, f in frames_by_seg.items() if parse_segment_id(s)[0] in test_sets}
    rest = {s: f for s, f in frames_by_seg.items() if s not in held}
    out = final_split(rest, sparse_n=sparse_n, val_frac=val_frac, buffer=buffer, val_sparse_n=val_sparse_n)
    out["test"] = {s: sorted(held[s], key=parse_frame_name) for s in sorted(held)}
    return out


def all_folds(frames_by_seg, folds=None, **kw):
    folds = {"DD": ("D", "D'"), "EE": ("E", "E'")} if folds is None else folds
    return {name: fold_split(frames_by_seg, sets, **kw) for name, sets in folds.items()}


def final_split(frames_by_seg, sparse_n=6, val_frac=0.15, buffer=60, val_sparse_n=1):
    out = {"train": {}, "val": {}, "test": {}}
    for seg in sorted(frames_by_seg):
        if parse_segment_id(seg)[0] not in TRAIN_SETS + TEST_SETS:
            raise ValueError("bo khong biet: %r (doan %s)" % (parse_segment_id(seg)[0], seg))
        frames = sorted(frames_by_seg[seg], key=parse_frame_name)
        n = len(frames)
        n_val = int(n * val_frac + 1e-9)
        train_end = max(0, n - n_val - buffer)
        out["train"][seg] = frames[:train_end:sparse_n]
        out["val"][seg] = frames[n - n_val:][::val_sparse_n]
    return out


def write_test_manifest(split, path):
    lines = []
    for seg in sorted(split["test"]):
        for fr in split["test"][seg]:
            lines.append("%s\t%s\n" % (seg, fr))
    data = "".join(lines).encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)
    digest = hashlib.sha256(data).hexdigest()
    with open(path + ".sha256", "w") as f:
        f.write("%s  %s\n" % (digest, os.path.basename(path)))
    return digest


def verify_test_manifest(path):
    try:
        with open(path + ".sha256") as f:
            want = f.read().split()[0]
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest() == want
    except (OSError, IndexError):
        return False


def segment_groups(seg_ids, merge_pairs=()):
    """Mac dinh moi doan la mot nhom; merge_pairs gop theo (cap, huong)."""
    pair_of = {}
    for a, b in merge_pairs:
        pair_of[a] = pair_of[b] = "%s+%s" % (a, b)
    groups = {}
    for seg in seg_ids:
        set_name, direction = parse_segment_id(seg)
        groups[seg] = segment_id(pair_of[set_name], direction) if set_name in pair_of else seg
    return groups
