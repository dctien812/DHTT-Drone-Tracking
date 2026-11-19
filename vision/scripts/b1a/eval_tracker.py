"""A4: ty le thoi gian o TRACK cua bo bam du an (onboard/dtrack/tracker.py) tren chuoi phat hien.

Gia dinh: camera dung yen, drone dung yen (OwnState quaternion (1,0,0,0): than trung he NED,
camera nhin theo mui = huong Bac). Moi khung: own.t = t_capture = t_now = t.
Dinh dang phat hien o day la (cx, cy, w, h, conf); eval_metrics dung (x1, y1, x2, y2, conf):
doi bang eval_metrics.xyxy_to_cxcywh.
Khung thieu trong danh sach (khong co muc trong frames) KHONG tinh vao mau so.
Han che da biet cua bo bam: khi nhieu phat hien cung conf, ket qua phu thuoc thu tu dau vao
(mode "all" sap on dinh theo conf giam dan, conf bang nhau giu thu tu dau vao).
"""
import os
import sys

_ONBOARD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "onboard"))
if _ONBOARD not in sys.path:
    sys.path.insert(0, _ONBOARD)

from dtrack.tracker import SingleTargetTracker, TrackerConfig  # noqa: E402
from dtrack.types import CameraModel, Detection, OwnState  # noqa: E402


def track_time_fraction(frames, camera=None, mode="all", return_counts=False):
    if mode not in ("all", "top1"):
        raise ValueError("mode phai la 'all' hoac 'top1': %r" % (mode,))
    if not frames:
        raise ValueError("frames rong")
    ts = [float(f["t"]) for f in frames]
    if any(b <= a for a, b in zip(ts, ts[1:])):
        raise ValueError("t phai tang nghiem ngat")
    camera = camera or CameraModel(width=2304, height=1296, fx=933.0, fy=933.0, cx=1152.0, cy=648.0)
    tracker = SingleTargetTracker(camera, TrackerConfig())
    statuses = []
    for f in frames:
        t = float(f["t"])
        dets = [Detection(t_capture=t, cx=d[0], cy=d[1], w=d[2], h=d[3], conf=d[4]) for d in f["dets"]]
        if mode == "top1" and dets:
            dets = [max(dets, key=lambda d: d.conf)]
        else:
            dets.sort(key=lambda d: -d.conf)   # on dinh: conf bang nhau giu thu tu dau vao
        own = OwnState(t=t, pos_ned=(0.0, 0.0, 0.0), vel_ned=(0.0, 0.0, 0.0),
                       q_world_body=(1.0, 0.0, 0.0, 0.0))
        statuses.append(tracker.update(dets, own, t).status.value)
    n_track = statuses.count("track")
    n = len(statuses)
    if return_counts:
        return n_track, n
    return {"track_fraction": n_track / n, "n_frames": n, "n_track": n_track,
            "statuses": statuses}
