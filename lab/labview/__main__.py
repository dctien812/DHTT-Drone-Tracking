"""Điểm vào: python -m labview --source file:<video>  (xem README)."""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading

from .config import DEFAULT_WEIGHTS, Config, ConfigError, load_password, validate


def parse(argv=None) -> Config:
    p = argparse.ArgumentParser(prog="labview", description="Man hinh lab Drone Tracking (L0) - khong gui lenh toi thiet bi nao")
    p.add_argument("--source", required=True, help="file:<video> | camera:<chi_so|/dev/videoN>")
    p.add_argument("--weights", default=DEFAULT_WEIGHTS)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--threads", type=int, default=4, help="so luong torch (toi da 8)")
    p.add_argument("--max-width", type=int, default=960)
    p.add_argument("--hfov", type=float, default=66.0, dest="hfov_deg", help="FOV ngang (do)")
    for k in ("fx", "fy", "cx", "cy"):
        p.add_argument(f"--{k}", type=float, default=None)
    p.add_argument("--real-width", type=float, default=0.30, dest="real_width_m", help="be rong that gia dinh cua muc tieu (m)")
    p.add_argument("--lost-timeout", type=float, default=2.0, dest="lost_timeout_s")
    p.add_argument("--click-margin", type=float, default=12.0, dest="click_margin_px")
    p.add_argument("--no-loop", action="store_true", help="khong lap lai video")
    p.add_argument("--no-pace", action="store_true", help="doc video nhanh nhat co the (do hieu nang)")
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--allow-network", action="store_true", help="mo ra mang noi bo; BAT BUOC co mat khau")
    p.add_argument("--password-file", default=None, help=f"file chua mat khau (dat ngoai git); neu khong dung bien moi truong LABVIEW_PASSWORD")
    p.add_argument("--log-file", default=None)
    a = p.parse_args(argv)
    cfg = Config(source=a.source, weights=a.weights, imgsz=a.imgsz, conf=a.conf, threads=a.threads,
                 max_width=a.max_width, hfov_deg=a.hfov_deg, fx=a.fx, fy=a.fy, cx=a.cx, cy=a.cy,
                 real_width_m=a.real_width_m, lost_timeout_s=a.lost_timeout_s,
                 click_margin_px=a.click_margin_px, loop=not a.no_loop, pace=not a.no_pace,
                 host=a.host, port=a.port, allow_network=a.allow_network, log_file=a.log_file)
    cfg.password = load_password(a.password_file)
    return validate(cfg)


def main(argv=None) -> int:
    try:
        cfg = parse(argv)
    except ConfigError as e:
        print(f"LOI CAU HINH: {e}", file=sys.stderr)
        return 2
    handlers = [logging.StreamHandler()]
    if cfg.log_file:
        handlers.append(logging.FileHandler(cfg.log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z")
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    from werkzeug.serving import make_server
    from .detector import YoloTracker
    from .outputs import LogSink
    from .pipeline import Pipeline
    from .server import create_app
    from .sources import make_source

    try:
        source = make_source(cfg.source, pace=cfg.pace, width=cfg.cam_width, height=cfg.cam_height, fps=cfg.cam_fps)
    except (ValueError, NotImplementedError) as e:
        print(f"LOI: {e}", file=sys.stderr)
        return 2
    detector = YoloTracker(cfg.weights, cfg.imgsz, cfg.conf, cfg.tracker, "cpu", cfg.threads)
    pipe = Pipeline(source, detector, cfg, sinks=[LogSink()])
    try:
        pipe.start()
    except RuntimeError as e:
        print(f"LOI: {e}", file=sys.stderr)
        return 1
    server = make_server(cfg.host, cfg.port, create_app(pipe, cfg), threaded=True)
    done = threading.Event()
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, lambda *_: done.set())
    threading.Thread(target=server.serve_forever, name="labview-http", daemon=True).start()
    logging.getLogger("labview").info("PID %d - nghe tai http://%s:%d/ (%s)", os.getpid(), cfg.host, cfg.port,
                                      "mang noi bo, co mat khau" if cfg.allow_network else "chi localhost")
    try:
        done.wait()
    finally:
        pipe.stop()
        server.shutdown()
        logging.getLogger("labview").info("Da dung")
    return 0


if __name__ == "__main__":
    sys.exit(main())
