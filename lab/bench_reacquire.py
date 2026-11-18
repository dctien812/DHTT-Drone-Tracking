"""Đo trước/sau cho tính năng gán lại khóa (không cần trình duyệt, không cần máy chủ).

Mỗi video: chạy YOLO+ByteTrack MỘT lần theo đúng đường xử lý của labview (thu nhỏ <= max_width, cùng
Detector), lưu danh sách track từng khung vào --cache; rồi "phát lại" cùng danh sách track qua LockManager
hai lần (logic cũ = tắt gán lại, logic mới), đồng hồ ảo = chỉ số khung / fps. Khóa mục tiêu tốt nhất (conf
cao nhất) ở khung có phát hiện đầu tiên, không khóa lại sau khi bỏ khóa.
Dùng: python bench_reacquire.py --videos A.mp4 B.mp4 --cache DIR [--threads 2] [--save-frames DIR --frames-of A.mp4 ...]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cv2  # noqa: E402

from labview import overlay  # noqa: E402
from labview.config import DEFAULT_WEIGHTS  # noqa: E402
from labview.lock import LockManager, ReacquireParams, Track  # noqa: E402


def detect(path: str, threads: int, max_width: int, weights: str) -> tuple[float, list[list[list[float]]]]:
    from labview.detector import YoloTracker
    det = YoloTracker(weights, 640, 0.25, "bytetrack.yaml", "cpu", threads)
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    out = []
    while True:
        ok, img = cap.read()
        if not ok:
            break
        if max_width and img.shape[1] > max_width:
            s = max_width / img.shape[1]
            img = cv2.resize(img, (max_width, max(1, int(round(img.shape[0] * s)))), interpolation=cv2.INTER_AREA)
        out.append([[t.id, *t.box, t.conf] for t in det.track(img)])
    cap.release()
    return fps, out


def replay(frames, fps, params: ReacquireParams, timeout: float = 2.0):
    t = [0.0]
    ev: list[str] = []
    m = LockManager(timeout, lambda: t[0], ev.append, params)
    per_frame = []  # (status, tracks)
    start = None
    for i, fr in enumerate(frames):
        t[0] = i / fps
        tracks = [Track(int(r[0]), (r[1], r[2], r[3], r[4]), r[5]) for r in fr]
        if start is None:
            if tracks and m.lock_best(tracks) is not None:
                start = i
            continue
        per_frame.append((m.update(tracks), tracks))
    if start is None:
        return None
    n = len(per_frame) + 1  # gồm cả khung khóa
    active = 1 + sum(1 for s, _ in per_frame if s.active)
    visible = 1 + sum(1 for s, _ in per_frame if s.active and s.track is not None)
    return dict(start=start, frames=n, active=active, visible=visible,
                drops=sum("TU BO KHOA" in e for e in ev), reacq=sum("GAN LAI" in e for e in ev),
                per_frame=per_frame, events=ev)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", nargs="+", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--max-width", type=int, default=960)
    ap.add_argument("--weights", default=DEFAULT_WEIGHTS)
    ap.add_argument("--gate", type=float, default=1.5)
    ap.add_argument("--gate-per-s", type=float, default=2.0)
    ap.add_argument("--size-min", type=float, default=0.5)
    ap.add_argument("--size-max", type=float, default=2.0)
    ap.add_argument("--save-frames", default=None, help="thư mục lưu 3 khung kết quả (logic mới)")
    ap.add_argument("--frames-of", nargs="*", default=[], help="tên video cần lưu khung")
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    old_p = ReacquireParams(enabled=False)
    new_p = ReacquireParams(True, a.gate, a.gate_per_s, a.size_min, a.size_max)
    print("video | khung | ID khac nhau | CU: con khoa% / thay% / bo / gan | MOI: con khoa% / thay% / bo / gan")
    tot = dict(o=[0, 0, 0, 0, 0], n=[0, 0, 0, 0, 0])
    for v in a.videos:
        name = Path(v).stem
        cf = Path(a.cache) / f"{name}.json"
        if cf.exists():
            d = json.loads(cf.read_text())
            fps, frames = d["fps"], d["frames"]
        else:
            fps, frames = detect(v, a.threads, a.max_width, a.weights)
            cf.write_text(json.dumps({"fps": fps, "frames": frames}))
        ids = {r[0] for fr in frames for r in fr}
        o, n = replay(frames, fps, old_p), replay(frames, fps, new_p)
        if o is None:
            print(f"{name} | {len(frames)} | {len(ids)} | khong co phat hien nao")
            continue
        for k, r in (("o", o), ("n", n)):
            for j, key in enumerate(("frames", "active", "visible", "drops", "reacq")):
                tot[k][j] += r[key]
        f = lambda r: f"{100 * r['active'] / r['frames']:.0f}% / {100 * r['visible'] / r['frames']:.0f}% / {r['drops']} / {r['reacq']}"
        print(f"{name} | {len(frames)} | {len(ids)} | {f(o)} | {f(n)}")
        for e in n["events"]:
            if "GAN LAI" in e:
                print("    ", e)
        if a.save_frames and name in a.frames_of:
            save(v, n, a.save_frames, name, a.max_width)
    for k, lab in (("o", "CU"), ("n", "MOI")):
        T = tot[k]
        print(f"TONG {lab}: con khoa {100 * T[1] / T[0]:.1f}% khung, thay {100 * T[2] / T[0]:.1f}%, bo khoa {T[3]}, gan lai {T[4]}")
    return 0


def save(path, res, outdir, name, max_width):
    os.makedirs(outdir, exist_ok=True)
    pf, start = res["per_frame"], res["start"]
    idx = [i for i, (s, _) in enumerate(pf) if s.state == "reacquired" and s.track is not None]
    firsts = [i for k, i in enumerate(idx) if k == 0 or idx[k - 1] != i - 1]  # đầu mỗi đoạn "vừa gán lại"
    pick = firsts[:3] if firsts else []
    for extra in (len(pf) // 2, len(pf) - 1, 0):
        if len(pick) < 3 and extra not in pick:
            pick.append(extra)
    cap = cv2.VideoCapture(path)
    for i in sorted(pick):
        fi = start + 1 + i
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, img = cap.read()
        if not ok:
            continue
        if max_width and img.shape[1] > max_width:
            s = max_width / img.shape[1]
            img = cv2.resize(img, (max_width, int(round(img.shape[0] * s))), interpolation=cv2.INTER_AREA)
        st, tracks = pf[i]
        overlay.draw(img, tracks, st.track_id if st.active else None, img.shape[1] / 2, img.shape[0] / 2, st)
        cv2.imwrite(os.path.join(outdir, f"{name}_f{fi:04d}.png"), img)
    cap.release()


if __name__ == "__main__":
    raise SystemExit(main())
