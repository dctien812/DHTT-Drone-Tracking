"""Vong lap chinh (mac dinh 30 Hz): nguon phat hien -> tracker -> guidance (trong supervisor) -> mavlink_io.

Chay (tu thu muc onboard/):  python -m dtrack.app --connect tcp:127.0.0.1:5770 --source sim --auto-engage ...
Bay that: --source camera (CHUA viet, nem NotImplementedError); engage bang kenh RC (config.supervisor).
Phan mem KHONG arm, KHONG cat canh, KHONG doi sang GUIDED.
"""
from __future__ import annotations

import argparse
import dataclasses
import math
import os
import signal
import sys
import time
from abc import ABC, abstractmethod
from typing import List, Optional

from .config import AppConfig, load_config
from .guidance import yaw_from_quat
from .gimbal import camera_attitude
from .gimbal_control import GimbalController
from .logger import CycleLogger, GimbalLogger, SearchLogger
from .mavlink_io import MavlinkLink
from .supervisor import SupervisorInput, Supervisor, SupState
from .range_estimator import RangeConfig
from .tracker import SingleTargetTracker, TrackerConfig
from .types import Detection, TrackState, TrackStatus


class DetectionSource(ABC):
    @abstractmethod
    def poll(self) -> List[Detection]:
        """Tra cac Detection moi (t_capture tren dong ho don dieu cuc bo, cung dong ho voi OwnState.t)."""

    def close(self) -> None:
        pass


class CameraHailoSource(DetectionSource):
    """Giu cho: camera that + Hailo. CHUA viet (khong co ma phan cung chua thu duoc)."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError("camera that + Hailo chua duoc cai dat")

    def poll(self) -> List[Detection]:  # pragma: no cover
        raise NotImplementedError


class App:
    def __init__(self, cfg: AppConfig, source: DetectionSource, link: MavlinkLink,
                 logger: Optional[CycleLogger] = None, auto_engage: bool = False,
                 stop_file: Optional[str] = None, clock=time.monotonic,
                 gimbal_port=None, gimbal_logger: Optional[GimbalLogger] = None,
                 search_logger: Optional[SearchLogger] = None):
        if cfg.gimbal.enabled and gimbal_port is None:
            raise ValueError("gimbal.enabled can gimbal_port")
        if cfg.gimbal.enabled and cfg.camera.gimbal_enabled:
            raise ValueError("gimbal.enabled va camera.gimbal_enabled khong duoc cung bat")
        self.cfg = cfg
        self.source = source
        self.link = link
        self.logger = logger
        self.auto_engage = auto_engage
        self.stop_file = stop_file
        self.clock = clock
        self.tracker = SingleTargetTracker(cfg.camera.to_model(),
                                           TrackerConfig(range=RangeConfig(target_size_m=cfg.target_shape.span_m)))
        self.gimbal = None
        if cfg.camera.gimbal_enabled:     # mo hinh khop gat (khop that: doc goc phan hoi servo thay cho mo hinh nay)
            from simtools.gimbal_model import GimbalModel
            c = cfg.camera
            self.gimbal = GimbalModel(c.gimbal_travel_deg, c.gimbal_rate_dps, c.gimbal_lag_s)
        self.sup = Supervisor(cfg.supervisor, cfg.guidance, cfg.search, cfg.gimbal)
        self.gimbal_port = gimbal_port if cfg.gimbal.enabled else None
        self.gimbal_logger = gimbal_logger
        self.search_logger = search_logger
        self.gimbal_ctrl = GimbalController(cfg.gimbal) if cfg.gimbal.enabled else None
        self._stop = False
        self.stats = {"ticks": 0, "sent": 0, "aborts": 0, "rtl_requests": 0}

    def request_stop(self, *_a) -> None:
        self._stop = True

    def _engage_signal(self) -> bool:
        if self.auto_engage:
            return True
        s = self.cfg.supervisor
        return self.link.rc_engaged(s.engage_rc_channel, s.engage_rc_threshold_us)

    def _stop_requested(self) -> bool:
        return self._stop or (self.stop_file is not None and os.path.exists(self.stop_file))

    def run(self) -> int:
        cfg = self.cfg
        period = 1.0 / cfg.loop_hz
        next_t = self.clock()
        last_start: Optional[float] = None
        while not self._stop_requested():
            now = self.clock()
            loop_dt = 0.0 if last_start is None else now - last_start
            last_start = now
            self.link.poll()
            own = self.link.own_state()
            dets = self.source.poll()
            own_cam = own            # tu the dung de chieu tia camera (tracker); guidance/supervisor dung tu the than
            delta_act = None
            if self.gimbal is not None and own is not None:
                own_cam = dataclasses.replace(own, q_world_body=self.gimbal.step(now, own.q_world_body)[0])
            if self.gimbal_port is not None and own is not None:
                delta_act = self.gimbal_port.angle(now)      # do o dau chu ky, truoc command
                own_cam = dataclasses.replace(own, q_world_body=tuple(
                    float(c) for c in camera_attitude(own.q_world_body, delta_act)))
            track = (self.tracker.update(dets, own_cam, now) if own is not None
                     else TrackState(t=now, status=TrackStatus.SEARCH))
            engage = self._engage_signal()
            hb, pa = self.link.heartbeat_age(now), self.link.pose_age(now)
            out = self.sup.step(SupervisorInput(t=now, track=track, own=own, engage=engage,
                                                heartbeat_age_s=hb, pose_age_s=pa, loop_dt_s=loop_dt,
                                                gimbal_delta_rad=delta_act))
            if out.send and out.cmd is not None:
                yaw = out.cmd.yaw_rad
                if yaw is None and own is not None:
                    yaw = yaw_from_quat(own.q_world_body)    # giu huong mui hien tai (khong de FC tu quay theo huong bay)
                self.link.send_velocity(out.cmd.vel_ned, yaw)
                self.stats["sent"] += 1
            if self.gimbal_port is not None and own is not None:
                gc = self.gimbal_ctrl.step(now, own.q_world_body, track, scan_delta_rad=(
                    None if out.search is None else out.search.scan_delta_rad))
                self.gimbal_port.command(now, gc.delta_cmd_rad)
                if self.gimbal_logger:
                    w, _x, y, z = own.q_world_body
                    theta = math.asin(max(-1.0, min(1.0, 2.0 * (_x * z - w * y))))
                    dg = math.degrees
                    self.gimbal_logger.log(
                        now, gc.mode, dg(gc.delta_cmd_rad), dg(delta_act), dg(self.gimbal_port.rate()),
                        None if gc.elev_los_rad is None else dg(gc.elev_los_rad),
                        None if gc.elev_aim_rad is None else dg(gc.elev_aim_rad),
                        self.sup.guidance.last_elev_ref_deg, gc.sat, dg(theta))
            if self.search_logger and out.search is not None:
                si = out.search
                yaw = None if out.cmd is None or out.cmd.yaw_rad is None else math.degrees(out.cmd.yaw_rad)
                self.search_logger.log(now, si.ep_id, si.ep_s, si.phase, si.run_s, si.closed, si.climb_m,
                                       None if si.scan_delta_rad is None else math.degrees(si.scan_delta_rad),
                                       yaw, si.r_hat)
            if out.request_rtl:
                self.link.request_rtl()
                self.stats["rtl_requests"] += 1
            self.stats["ticks"] += 1
            if self.logger:
                self.logger.log(now, loop_dt, hb, pa, engage, own, track, len(dets), out)
            next_t += period
            delay = next_t - self.clock()
            if delay > 0:
                time.sleep(delay)
            else:
                next_t = self.clock()     # cham: khong don lai
        self._graceful_brake()
        self.stats["aborts"] = len(self.sup.abort_reasons)
        return 0

    def _graceful_brake(self) -> None:
        """Ket thuc o GUIDED: phanh tuong minh (van toc 0) cho toi khi cham hoac het brake_on_exit_s."""
        cfg = self.cfg
        t_end = self.clock() + cfg.brake_on_exit_s
        slow_since: Optional[float] = None
        while self.clock() < t_end:
            self.link.poll()
            own = self.link.own_state()
            if own is None or not own.armed or own.mode != "GUIDED":
                return                      # phi cong da giu quyen / khong o GUIDED: khong gui gi
            self.link.send_velocity((0.0, 0.0, 0.0), yaw_from_quat(own.q_world_body))
            sp = math.sqrt(sum(c * c for c in own.vel_ned))
            now = self.clock()
            if sp < cfg.brake_exit_speed_mps:
                slow_since = slow_since or now
                if now - slow_since > 1.0:
                    return
            else:
                slow_since = None
            time.sleep(0.05)


def _make_gimbal(cfg: AppConfig):
    if not cfg.camera.gimbal_enabled:
        return None
    from simtools.gimbal_model import GimbalModel
    c = cfg.camera
    return GimbalModel(c.gimbal_travel_deg, c.gimbal_rate_dps, c.gimbal_lag_s)


def build_source(args, cfg: AppConfig, gimbal_port=None) -> DetectionSource:
    if args.source == "sim":
        from simtools.sim_truth_source import SimTruthSource
        return SimTruthSource(target_url=args.sim_target, chaser_url=args.sim_chaser, camera=cfg.camera.to_model(),
                              seed=args.sim_seed, blackout_file=args.sim_blackout_file,
                              gimbal=_make_gimbal(cfg), target_shape=cfg.target_shape, gimbal_port=gimbal_port,
                              synth=cfg.synthetic)
    if args.source == "camera":
        return CameraHailoSource()
    raise ValueError("nguon la: %s" % args.source)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", help="file TOML/JSON (tuy chon)")
    ap.add_argument("--connect", help="tcp:host:port | udp:host:port | /dev/ttyXXX[,baud] (ghi de config)")
    ap.add_argument("--source", choices=["sim", "camera"], default="camera")
    ap.add_argument("--auto-engage", action="store_true", help="CHI mo phong: coi nhu luon engage")
    ap.add_argument("--rate", type=float, help="Hz vong lap (ghi de config)")
    ap.add_argument("--log", help="duong dan file CSV log (mac dinh <log_dir>/dtrack_<gio>.csv)")
    ap.add_argument("--stop-file", help="khi file nay xuat hien: phanh tuong minh roi thoat 0")
    ap.add_argument("--sim-target", default="tcp:127.0.0.1:5762")
    ap.add_argument("--sim-chaser", default="tcp:127.0.0.1:5773")
    ap.add_argument("--sim-seed", type=int, default=12345)
    ap.add_argument("--sim-blackout-file", help="file ton tai = nguon phat hien khong tra gi")
    a = ap.parse_args(argv)
    if a.auto_engage and a.source != "sim":
        ap.error("--auto-engage chi duoc dung voi --source sim")
    cfg = load_config(a.config)
    if a.connect:
        cfg.mavlink.connect = a.connect
    if a.rate:
        cfg.loop_hz = a.rate
    log_path = a.log or os.path.join(cfg.log_dir, time.strftime("dtrack_%Y%m%d_%H%M%S.csv"))
    link = MavlinkLink(cfg.mavlink)
    gimbal_port = gimbal_logger = None
    if cfg.gimbal.enabled:
        from simtools.servo_model import ServoModel, SimGimbalPort
        gimbal_port = SimGimbalPort(ServoModel.from_config(cfg.gimbal))
        gimbal_logger = GimbalLogger(os.path.join(os.path.dirname(log_path), "gimbal.csv"))
    search_logger = None
    if cfg.search.enabled:
        search_logger = SearchLogger(os.path.join(os.path.dirname(log_path), "search.csv"))
    source = build_source(a, cfg, gimbal_port=gimbal_port)
    logger = CycleLogger(log_path, cfg.log_queue)
    app = App(cfg, source, link, logger, auto_engage=a.auto_engage, stop_file=a.stop_file,
              gimbal_port=gimbal_port, gimbal_logger=gimbal_logger, search_logger=search_logger)
    signal.signal(signal.SIGINT, app.request_stop)
    signal.signal(signal.SIGTERM, app.request_stop)
    rc = 2
    try:
        link.connect()
        print("[dtrack] da noi FC sysid %d, log: %s" % (link.target_system, log_path), flush=True)
        rc = app.run()
    finally:
        source.close()
        logger.close()
        if gimbal_logger:
            gimbal_logger.close()
        if search_logger:
            search_logger.close()
        link.close()
        print("[dtrack] ket thuc: %s, log roi %d dong" % (app.stats, logger.dropped), flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
