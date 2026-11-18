"""Ghi log CSV moi chu ky vong lap, khong chan: dong duoc dua vao hang doi, mot luong rieng ghi ra dia."""
from __future__ import annotations

import csv
import math
import os
import queue
import threading
import time
from typing import Optional

from .supervisor import SupervisorOutput
from .types import GuidanceCommand, OwnState, TrackState

COLUMNS = [
    "t", "wall", "loop_dt", "hb_age", "pose_age", "engage", "armed", "mode",
    "pos_n", "pos_e", "pos_d", "vel_n", "vel_e", "vel_d", "qw", "qx", "qy", "qz",
    "trk_status", "los_n", "los_e", "los_d", "rate_n", "rate_e", "rate_d",
    "range", "range_sigma", "range_rate", "range_valid", "age", "n_det",
    "cmd_vn", "cmd_ve", "cmd_vd", "cmd_yaw", "sent", "state", "reason", "rtl",
]


def _f(x) -> str:
    if x is None:
        return ""
    if isinstance(x, float):
        return "%.4f" % x if math.isfinite(x) else str(x)
    return str(x)


GIMBAL_COLUMNS = ["t", "mode", "delta_cmd_deg", "delta_act_deg", "delta_rate_dps", "elev_los_deg",
                  "elev_aim_deg", "elev_ref_deg", "sat", "theta_deg"]


class CycleLogger:
    columns = COLUMNS

    def __init__(self, path: str, max_queue: int = 20000):
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        self.path = path
        self.dropped = 0
        self._q: "queue.Queue" = queue.Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self._f = open(path, "w", newline="", encoding="utf-8")
        self._w = csv.writer(self._f)
        self._w.writerow(self.columns)
        self._th = threading.Thread(target=self._run, name="dtrack-log", daemon=True)
        self._th.start()

    def log(self, t: float, loop_dt: float, hb_age: float, pose_age: float, engage: bool,
            own: Optional[OwnState], track: TrackState, n_det: int, out: SupervisorOutput) -> None:
        o = own
        c: Optional[GuidanceCommand] = out.cmd
        row = [
            t, time.time(), loop_dt, hb_age, pose_age, int(engage),
            "" if o is None else int(o.armed), "" if o is None else o.mode,
            *(o.pos_ned if o else ("", "", "")), *(o.vel_ned if o else ("", "", "")),
            *(o.q_world_body if o else ("", "", "", "")),
            track.status.value, *(track.los_ned or ("", "", "")), *(track.los_rate_ned or ("", "", "")),
            track.range_m, track.range_sigma_m, track.range_rate_mps, int(track.range_valid), track.age_s, n_det,
            *(c.vel_ned if c else ("", "", "")), (c.yaw_rad if c else None), int(out.send),
            out.state.value, out.reason, int(out.request_rtl),
        ]
        try:
            self._q.put_nowait([_f(x) for x in row])
        except queue.Full:
            self.dropped += 1

    def _run(self) -> None:
        last_flush = time.monotonic()
        while not (self._stop.is_set() and self._q.empty()):
            try:
                row = self._q.get(timeout=0.2)
            except queue.Empty:
                row = None
            if row is not None:
                self._w.writerow(row)
            if time.monotonic() - last_flush > 1.0:
                self._f.flush()
                last_flush = time.monotonic()
        self._f.flush()

    def close(self) -> None:
        self._stop.set()
        self._th.join(timeout=5.0)
        self._f.close()


class GimbalLogger(CycleLogger):
    """gimbal.csv: mot dong moi chu ky co own (goc theo do)."""
    columns = GIMBAL_COLUMNS

    def log(self, t: float, mode: str, delta_cmd_deg: float, delta_act_deg: float, delta_rate_dps: float,
            elev_los_deg: Optional[float], elev_aim_deg: Optional[float], elev_ref_deg: Optional[float],
            sat: bool, theta_deg: float) -> None:
        row = [t, mode, delta_cmd_deg, delta_act_deg, delta_rate_dps, elev_los_deg, elev_aim_deg,
               elev_ref_deg, int(sat), theta_deg]
        try:
            self._q.put_nowait([_f(x) for x in row])
        except queue.Full:
            self.dropped += 1
