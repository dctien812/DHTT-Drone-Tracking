"""B1a: ham thuan cho script dung tap (ke hoach mau) va tham so huan luyen."""
from prep_crops import frame_seed


def plan_fold(split, birds_train, birds_fa, base_seeds=None):
    base_seeds = {"pos": 6001, "off": 6002, "bg": 6003} if base_seeds is None else base_seeds
    test_keys = {(s, f) for s, frames in split["test"].items() for f in frames}
    for part in ("train", "val"):
        for s, frames in split[part].items():
            for f in frames:
                if (s, f) in test_keys:
                    raise ValueError("khung kiem thu lot vao %s: %s %s" % (part, s, f))

    def job(sp, seg, frame, kind):
        return {"split": sp, "seg": seg, "frame": frame, "kind": kind,
                "seed": frame_seed(base_seeds.get(kind, 6004), seg, frame)}

    jobs = []
    kinds = {"train": ("pos", "bg"), "val": ("pos", "bg"), "test": ("pos", "off", "bg")}
    for sp in ("train", "val", "test"):
        for seg in sorted(split[sp]):
            for frame in sorted(split[sp][seg]):
                jobs += [job(sp, seg, frame, k) for k in kinds[sp]]
    jobs += [job("train", "birds", b, "bird") for b in sorted(birds_train)]
    jobs += [job("birds_fa", "birds", b, "bird") for b in sorted(birds_fa)]
    return jobs


def dataset_yaml(root, names=("airplane",)):
    lines = ["path: %s" % root, "train: images/train", "val: images/val", "test: images/test", "names:"]
    lines += ["  %d: %s" % (i, n) for i, n in enumerate(names)]
    return "\n".join(lines) + "\n"


def train_args(fold, seed, device, epochs=40, imgsz=480, batch=16):
    args = dict(project="runs/b1a", name="b1a_%s_s%d" % (fold.replace("'", "p"), seed),
                epochs=epochs, imgsz=imgsz, batch=batch, seed=seed, device=device,
                single_cls=True, deterministic=True, amp=device != "cpu", workers=3,
                hsv_h=0.015, hsv_s=0.7, hsv_v=0.4, fliplr=0.5, flipud=0.0, mosaic=0.5,
                close_mosaic=10, scale=0.25)
    if device != "cpu":
        args["_pre"] = {"cudnn_enabled": False}
    return args


def split_pre(args):
    """Tach khoa "_pre" (buoc chuan bi, khong phai doi so Ultralytics): (kwargs, pre)."""
    return {k: v for k, v in args.items() if k != "_pre"}, dict(args.get("_pre", {}))
