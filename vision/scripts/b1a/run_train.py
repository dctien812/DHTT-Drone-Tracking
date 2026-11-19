"""B1a buoc 12 (b): huan luyen YOLOv8n 1 lop tren card (ROCm). Dung: python run_train.py <EE|DD|final>  |  python run_train.py collect
Tham so lay tu build_dataset.train_args (khong doi) + split_pre. Chi them: epochs=60, patience=15 (ke hoach khong ghi so epoch),
project tuyet doi vao results/b1a/train/runs, plots=False (tranh tai font), data=yaml cua tap, model=weights/yolov8n.pt (khoi dau tu COCO).
"""
import csv
import hashlib
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
VISION = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(VISION, "results", "b1a", "train")
RUNS = os.path.join(OUT, "runs")
SETS = os.path.join(VISION, "data", "b1a", "sets")
WEIGHTS = os.path.join(VISION, "weights", "yolov8n.pt")
SEED = 0
EPOCHS, PATIENCE = 60, 15
FOLDS = ("EE", "DD", "final")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_results(csv_path):
    with open(csv_path, newline="") as f:
        return [{k.strip(): v for k, v in r.items()} for r in csv.DictReader(f)]


def train_one(fold):
    import torch
    import build_dataset as bd
    from ultralytics import YOLO
    args = bd.train_args(fold, SEED, 0, epochs=EPOCHS)
    kwargs, pre = bd.split_pre(args)
    if pre.get("cudnn_enabled") is False:
        torch.backends.cudnn.enabled = False
    assert torch.backends.cudnn.enabled is False and torch.cuda.is_available()
    kwargs.update(project=RUNS, patience=PATIENCE, plots=False, data=os.path.join(SETS, fold, "data.yaml"), exist_ok=False)
    assert kwargs["device"] == 0 and kwargs["amp"] is True
    os.makedirs(OUT, exist_ok=True)
    print("args:", json.dumps(kwargs, default=str), flush=True)
    model = YOLO(WEIGHTS)
    t0 = time.time()
    err = None
    save_dir = None
    try:
        model.train(**kwargs)
        save_dir = str(model.trainer.save_dir)
    except BaseException:
        err = traceback.format_exc()
        print(err, flush=True)
        try:
            save_dir = str(model.trainer.save_dir)
        except Exception:
            pass
    wall = time.time() - t0
    summ = {"fold": fold, "seed": SEED, "wall_s": round(wall, 1), "error": err, "save_dir": save_dir,
            "args": kwargs, "epochs_planned": EPOCHS, "patience": PATIENCE,
            "torch": torch.__version__, "device_name": torch.cuda.get_device_name(0)}
    if save_dir and os.path.exists(os.path.join(save_dir, "results.csv")):
        rows = read_results(os.path.join(save_dir, "results.csv"))
        n = len(rows)
        summ["epochs_run"] = n
        summ["s_per_epoch"] = round(wall / n, 2) if n else None
        summ["results_csv_time_last_s"] = float(rows[-1]["time"]) if n and "time" in rows[-1] else None
        summ["map50_last"] = float(rows[-1]["metrics/mAP50(B)"])
        best = max(rows, key=lambda r: float(r["metrics/mAP50-95(B)"]) * 0.9 + float(r["metrics/mAP50(B)"]) * 0.1)
        summ["best_epoch_by_fitness"] = int(float(best["epoch"]))
        summ["map50_at_best_epoch"] = float(best["metrics/mAP50(B)"])
        summ["last_row"] = rows[-1]
    bp = os.path.join(save_dir, "weights", "best.pt") if save_dir else None
    if bp and os.path.exists(bp):
        summ["best_pt"] = bp
        summ["best_pt_sha256"] = sha(bp)
    with open(os.path.join(OUT, "%s_summary.json" % fold), "w") as f:
        json.dump(summ, f, indent=1, default=str)
    marker = os.path.join(OUT, "%s.%s" % (fold, "failed" if err else "done"))
    open(marker, "w").write("%s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    print("XONG", fold, "wall %.1fs" % wall, flush=True)
    return 1 if err else 0


def collect():
    import torch
    import ultralytics
    runs = {"torch": torch.__version__, "ultralytics": ultralytics.__version__, "folds": {}, "total_wall_s": 0.0}
    for fold in FOLDS:
        p = os.path.join(OUT, "%s_summary.json" % fold)
        if not os.path.exists(p):
            runs["folds"][fold] = {"status": "chua chay"}
            continue
        s = json.load(open(p))
        keep = {k: s.get(k) for k in ("seed", "wall_s", "epochs_run", "epochs_planned", "patience", "s_per_epoch", "results_csv_time_last_s",
                                       "map50_last", "best_epoch_by_fitness", "map50_at_best_epoch", "best_pt", "best_pt_sha256",
                                       "save_dir", "error", "device_name")}
        runs["folds"][fold] = keep
        runs["total_wall_s"] += s.get("wall_s") or 0
    runs["total_wall_s"] = round(runs["total_wall_s"], 1)
    with open(os.path.join(OUT, "runs.json"), "w") as f:
        json.dump(runs, f, indent=1)
    print(json.dumps(runs, indent=1))


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else ""
    if a == "collect":
        collect()
    elif a in FOLDS:
        sys.exit(train_one(a))
    else:
        raise SystemExit("dung: run_train.py EE|DD|final|collect")
