"""Nguon phat hien CHI DUNG TRONG MO PHONG: doc vi tri that cua muc tieu (va tu the/vi tri that cua chaser)
tu ban tin SIM_STATE cua hai SITL roi dua qua SyntheticDetector. Khong dung khi bay that.

Ket noi: target qua cong rieng (mac dinh SERIAL1 cua target, tcp:127.0.0.1:5762), chaser qua cong rieng
(SERIAL2 cua chaser, tcp:127.0.0.1:5773). Vector tuong doi that = target - chaser (cung truc dia WGS84),
OwnState dua cho SyntheticDetector la tu the THAT cua chaser (camera that nhin theo tu the that, khong theo uoc luong EKF).
"""
from __future__ import annotations

import math
import os
import time
from typing import List, Optional, Tuple

from dtrack.app import DetectionSource
from dtrack.geometry import quat_from_euler
from dtrack.mavlink_io import latlon_to_ned
from dtrack.synthetic import SyntheticConfig, SyntheticDetector
from dtrack.types import CameraModel, Detection, OwnState

MSG_SIM_STATE = 108


class SimStateReader:
    """Doc SIM_STATE tu mot SITL: (t_nhan, lat, lon, alt_msl, vn, ve, vd, roll, pitch, yaw)."""

    def __init__(self, url: str, rate_hz: float = 50.0, clock=time.monotonic, connect_timeout: float = 60.0):
        from pymavlink import mavutil
        self.clock = clock
        self.mav = mavutil.mavlink_connection(url, source_system=253, source_component=191)
        t0 = clock()
        while True:
            hb = self.mav.wait_heartbeat(timeout=5)
            if hb is not None:
                break
            if clock() - t0 > connect_timeout:
                raise RuntimeError("khong noi duoc %s" % url)
        self.mav.mav.command_long_send(self.mav.target_system, self.mav.target_component, 511, 0,
                                       MSG_SIM_STATE, int(1e6 / rate_hz), 0, 0, 0, 0, 0)
        self.last: Optional[Tuple[float, float, float, float, float, float, float, float, float, float]] = None

    def poll(self) -> None:
        while True:
            m = self.mav.recv_match(type="SIM_STATE", blocking=False)
            if m is None:
                return
            # firmware gui lat/lon (float32) = do*1e7 (mat do chinh xac); dung lat_int/lon_int (int32, do*1e7)
            lat = m.lat_int / 1e7
            lon = m.lon_int / 1e7
            self.last = (self.clock(), lat, lon, m.alt, m.vn, m.ve, m.vd, m.roll, m.pitch, m.yaw)

    def close(self) -> None:
        self.mav.close()


class SimTruthSource(DetectionSource):
    def __init__(self, target_url: str, chaser_url: str, camera: Optional[CameraModel] = None,
                 seed: int = 12345, blackout_file: Optional[str] = None, max_age_s: float = 0.2,
                 synth: Optional[SyntheticConfig] = None, clock=time.monotonic):
        self.clock = clock
        self.cam = camera or CameraModel()
        cfg = synth or SyntheticConfig(frame_rate_hz=30.0, latency_s=0.06, center_sigma_px=1.5, size_sigma_px=1.0,
                                       p_miss=0.20, p_false=0.05, clip_to_frame=True)
        cfg.seed = seed
        self.det = SyntheticDetector(self.cam, cfg)
        self.tgt = SimStateReader(target_url, clock=clock)
        self.chs = SimStateReader(chaser_url, clock=clock)
        self.blackout_file = blackout_file
        self.max_age_s = max_age_s
        self.stale_skips = 0
        self.blackout_polls = 0

    def poll(self) -> List[Detection]:
        self.tgt.poll()
        self.chs.poll()
        now = self.clock()
        tg, ch = self.tgt.last, self.chs.last
        if tg is None or ch is None:
            return []
        if now - tg[0] > self.max_age_s or now - ch[0] > self.max_age_s:
            self.stale_skips += 1        # du lieu vi tri muc tieu / chaser cu: khong sinh phat hien
            return []
        if self.blackout_file and os.path.exists(self.blackout_file):
            self.blackout_polls += 1
            self.det.process(now, (0.0, 0.0, 0.0), self._own(ch, now, 0.0))   # giu nhip khung, bo ket qua
            return []
        dtg, dch = now - tg[0], now - ch[0]
        # noi suy ve "bay gio" theo van toc, cung truc dia WGS84 quanh diem cua chaser
        n, e = latlon_to_ned(ch[1], ch[2], tg[1], tg[2])
        rel = (n + tg[4] * dtg - ch[4] * dch, e + tg[5] * dtg - ch[5] * dch,
               -(tg[3] - ch[3]) + tg[6] * dtg - ch[6] * dch)
        return self.det.process(now, rel, self._own(ch, now, dch))

    def _own(self, ch, now: float, dch: float) -> OwnState:
        q = tuple(float(c) for c in quat_from_euler(ch[7], ch[8], ch[9]))
        return OwnState(t=now, pos_ned=(0.0, 0.0, 0.0), vel_ned=(ch[4], ch[5], ch[6]), q_world_body=q,
                        armed=True, mode="GUIDED")

    def close(self) -> None:
        self.tgt.close()
        self.chs.close()
