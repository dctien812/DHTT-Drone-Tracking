"""Ghi khung hinh GOC kem thoi gian ra dia (du lieu huan luyen), khong thu nho.

    python tools/record_frames.py --source picamera2 --out ~/data --tag san1 --every 3 --max-seconds 600

Moi phien: <out>/<YYYYmmdd_HHMMSS>[_tag]/frames/000000.jpg ..., frames.csv (flush tung anh), session.json (luon ghi luc ket thuc).
CHI ghi ra dia: khong mo cong mang, khong gui gi ra ngoai, khong gui lenh toi thiet bi nao.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import shutil
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # chay thang `python tools/record_frames.py`
from labview.sources import make_source  # noqa: E402

HEADER = ["saved_idx", "src_idx", "file", "t_mono", "t_wall_iso", "width", "height"]
DISK_CHECK_EVERY = 30   # so anh da luu giua hai lan kiem tra o dia


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _free_mb(path) -> float:
    return shutil.disk_usage(path).free / 1048576


def record(source, out_root, *, tag="", every=1, max_frames=None, max_seconds=None, min_free_mb=500, fmt="jpg",
           jpeg_quality=95, clock=time.monotonic, wall_clock=_utcnow, free_mb=_free_mb, stop_event=None,
           progress=None) -> dict:
    """Ghi khung tu `source` (chua mo) vao thu muc phien moi duoi out_root; tra ve dict cung noi dung session.json.
    progress(saved, free_mb): goi sau moi lan kiem tra o dia (tuy chon, de CLI in tien do)."""
    if not re.fullmatch(r"[A-Za-z0-9_-]*", tag):
        raise ValueError("--tag chi gom chu, so, '-' va '_'")
    if every < 1:
        raise ValueError("--every phai >= 1")
    if max_frames is not None and max_frames < 1:
        raise ValueError("--max-frames phai >= 1")
    if not 1 <= jpeg_quality <= 100:
        raise ValueError("--jpeg-quality phai trong 1-100")
    if fmt not in ("jpg", "png"):
        raise ValueError("--format phai la jpg hoac png")

    started = wall_clock()
    sdir = Path(out_root) / (started.strftime("%Y%m%d_%H%M%S") + (f"_{tag}" if tag else ""))
    sdir.parent.mkdir(parents=True, exist_ok=True)
    sdir.mkdir()                      # FileExistsError neu da co: khong ghi de
    (sdir / "frames").mkdir()
    params = {"tag": tag, "every": every, "max_frames": max_frames, "max_seconds": max_seconds,
              "min_free_mb": min_free_mb, "fmt": fmt, "jpeg_quality": jpeg_quality,
              "source": getattr(source, "name", "")}
    imwrite_args = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality] if fmt == "jpg" else []
    read = saved = gaps = 0
    last_idx = None
    reason, err = None, None
    csv_f = open(sdir / "frames.csv", "w", newline="", encoding="utf-8")
    try:
        w = csv.writer(csv_f)
        w.writerow(HEADER)
        csv_f.flush()
        try:
            t0 = clock()
            if free_mb(sdir) < min_free_mb:
                reason = "disk_low"
            else:
                source.open()
            while reason is None:
                if stop_event is not None and stop_event.is_set():
                    reason = "stopped"
                    break
                if max_seconds is not None and clock() - t0 >= max_seconds:
                    reason = "max_seconds"
                    break
                fr = source.read()
                if fr is None:
                    reason = "source_ended"
                    break
                read += 1
                if last_idx is not None and fr.index > last_idx + 1:
                    gaps += fr.index - last_idx - 1
                last_idx = fr.index
                if (read - 1) % every:
                    continue
                name = f"frames/{saved:06d}.{fmt}"
                if not cv2.imwrite(str(sdir / name), fr.image, imwrite_args):
                    raise OSError(f"cv2.imwrite that bai: {name}")
                h, wd = fr.image.shape[:2]
                w.writerow([saved, fr.index, name, f"{fr.ts:.6f}", wall_clock().isoformat(), wd, h])
                csv_f.flush()
                saved += 1
                if max_frames is not None and saved >= max_frames:
                    reason = "max_frames"
                elif saved % DISK_CHECK_EVERY == 0:
                    free = free_mb(sdir)
                    if progress:
                        progress(saved, free)
                    if free < min_free_mb:
                        reason = "disk_low"
        except KeyboardInterrupt:
            reason = "stopped"
        except Exception as e:   # ghi nhan loi, van dong nguon va ghi session.json
            reason, err = "error", f"{type(e).__name__}: {e}"
        finally:
            try:
                source.close()
            except Exception as e:
                if err is None:
                    reason, err = "error", f"close: {type(e).__name__}: {e}"
    finally:
        try:
            csv_f.close()
        except OSError as e:
            if err is None:
                reason, err = "error", f"csv: {type(e).__name__}: {e}"
    res = {"params": params, "session_dir": str(sdir), "started_at": started.isoformat(),
           "ended_at": wall_clock().isoformat(), "frames_read": read, "frames_saved": saved,
           "src_gaps": gaps, "stop_reason": reason}
    if err is not None:
        res["error"] = err
    try:
        (sdir / "session.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    except OSError as e:   # khong ghi duoc session.json: bao loi trong ket qua tra ve, giu ly do dung cu
        res["error"] = f"session.json: {type(e).__name__}: {e}" + (f" (truoc do: {err or reason})" if reason != "error" or err else "")
        res["stop_reason"] = "error"
    return res


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--source", required=True, help="file:<video> | camera:<chi_so|/dev/videoN> | picamera2")
    p.add_argument("--out", required=True, help="thu muc goc; moi lan chay tao mot thu muc phien con")
    p.add_argument("--tag", default="", help="nhan them vao ten thu muc phien (chu, so, - _)")
    p.add_argument("--every", type=int, default=1, help="luu 1 khung trong moi N khung doc duoc")
    p.add_argument("--max-frames", type=int, default=None, help="dung khi da luu du so anh nay")
    p.add_argument("--max-seconds", type=float, default=None)
    p.add_argument("--min-free-mb", type=float, default=500, help="dung khi o dia trong it hon (MB)")
    p.add_argument("--format", choices=("jpg", "png"), default="jpg", dest="fmt")
    p.add_argument("--jpeg-quality", type=int, default=95)
    # cac co camera: cung ten/mac dinh voi labview (labview.__main__); do phan giai goc cam bien chua xac dinh duoc tu ma
    p.add_argument("--cam-width", type=int, default=1280)
    p.add_argument("--cam-height", type=int, default=720)
    p.add_argument("--cam-fps", type=int, default=30)
    p.add_argument("--focus", choices=("infinity", "continuous", "manual"), default="infinity", dest="cam_focus")
    p.add_argument("--lens-position", type=float, default=None, dest="cam_lens_position")
    p.add_argument("--cam-buffers", type=int, default=4, dest="cam_buffers")
    a = p.parse_args(argv)
    try:
        source = make_source(a.source, pace=False, width=a.cam_width, height=a.cam_height, fps=a.cam_fps,
                             focus=a.cam_focus, lens_position=a.cam_lens_position, buffers=a.cam_buffers)
    except (ValueError, NotImplementedError) as e:
        print(f"LOI: {e}", file=sys.stderr)
        return 2
    stop = threading.Event()
    old = {}
    for s in (signal.SIGINT, signal.SIGTERM):
        old[s] = signal.signal(s, lambda *_: stop.set())
    try:
        res = record(source, a.out, tag=a.tag, every=a.every, max_frames=a.max_frames, max_seconds=a.max_seconds,
                     min_free_mb=a.min_free_mb, fmt=a.fmt, jpeg_quality=a.jpeg_quality, stop_event=stop,
                     progress=lambda n, mb: print(f"da luu {n} anh, con trong {mb:.0f} MB", flush=True))
    except (ValueError, OSError) as e:   # tham so sai, thu muc phien da co, khong tao duoc thu muc
        print(f"LOI: {e}", file=sys.stderr)
        return 2
    finally:
        for s, h in old.items():
            signal.signal(s, h)
    print(f"Xong ({res['stop_reason']}): {res['frames_saved']} anh / {res['frames_read']} khung doc, "
          f"{res['src_gaps']} khung nguon bi bo")
    print(f"Thu muc phien: {res['session_dir']}")
    if res.get("error"):
        print(f"LOI: {res['error']}", file=sys.stderr)
    return 1 if res["stop_reason"] in ("error", "disk_low") else 0


if __name__ == "__main__":
    sys.exit(main())
