"""Giao tiep MAVLink (pymavlink) voi FC ArduCopter: nhan tu the/vi tri, gui lenh van toc + yaw, doi mode RTL.

Hang so da doi chieu voi ma ArduPilot 4.7.2 (~/ardupilot):
- type_mask cua SET_POSITION_TARGET_LOCAL_NED: bit X/Y/Z=1/2/4, VX/VY/VZ=8/16/32, AX/AY/AZ=64/128/256,
  FORCE_SET=512, YAW=1024, YAW_RATE=2048 (build/sitl/libraries/GCS_MAVLink/include/mavlink/v2.0/common/common.h:1545-1556).
  ArduCopter/GCS_MAVLink_Copter.cpp:896-918 dinh nghia POS_IGNORE (X|Y|Z), VEL_IGNORE, ACC_IGNORE, YAW_IGNORE...;
  handler :998-1100 chi chap nhan khi dang o GUIDED, frame LOCAL_NED/LOCAL_OFFSET_NED/BODY_NED/BODY_OFFSET_NED;
  nhanh "pos_ignore && !vel_ignore" goi mode_guided.set_vel_accel_NED_m.
  => van toc + yaw (bo qua vi tri, gia toc, yaw_rate) = 7 | 448 | 2048 = 2503; khong yaw: them 1024 = 3527.
- GUIDED dung (van toc 0, bo yaw rate) neu qua GUID_TIMEOUT = 3 s khong co lenh (ArduCopter/Parameters.cpp:875,
  ModeGuided::get_timeout_ms mode_guided.cpp:1195) -> gui lai >= 10 Hz.
- Quaternion cua ATTITUDE_QUATERNION la than->NED, thu tu (w,x,y,z) (GCS_Common.cpp:6090 dung ahrs.get_quaternion).
"""
from __future__ import annotations

import math
import time
from typing import Callable, Dict, Optional, Tuple

from .config import MavlinkConfig
from .types import GuidanceCommand, OwnState

# --- hang so MAVLink / ArduCopter ---
MAV_FRAME_LOCAL_NED = 1
MAV_CMD_DO_SET_MODE = 176
MAV_CMD_SET_MESSAGE_INTERVAL = 511
MAV_MODE_FLAG_CUSTOM_MODE_ENABLED = 1
MAV_MODE_FLAG_SAFETY_ARMED = 128
MSG_HEARTBEAT, MSG_ATTITUDE_QUATERNION, MSG_LOCAL_POSITION_NED, MSG_GLOBAL_POSITION_INT, MSG_RC_CHANNELS = 0, 31, 32, 33, 65

TYPEMASK_POS_IGNORE = 1 | 2 | 4
TYPEMASK_VEL_IGNORE = 8 | 16 | 32
TYPEMASK_ACC_IGNORE = 64 | 128 | 256
TYPEMASK_YAW_IGNORE = 1024
TYPEMASK_YAW_RATE_IGNORE = 2048
MASK_VEL_YAW = TYPEMASK_POS_IGNORE | TYPEMASK_ACC_IGNORE | TYPEMASK_YAW_RATE_IGNORE         # 2503
MASK_VEL_ONLY = MASK_VEL_YAW | TYPEMASK_YAW_IGNORE                                          # 3527

# ArduCopter custom_mode (ArduCopter/mode.h:82-102)
COPTER_MODES: Dict[int, str] = {0: "STABILIZE", 1: "ACRO", 2: "ALT_HOLD", 3: "AUTO", 4: "GUIDED", 5: "LOITER",
                                6: "RTL", 7: "CIRCLE", 9: "LAND", 11: "DRIFT", 13: "SPORT", 14: "FLIP",
                                15: "AUTOTUNE", 16: "POSHOLD", 17: "BRAKE", 18: "THROW", 21: "SMART_RTL"}
MODE_RTL = 6
MODE_GUIDED = 4


# --------------------------------------------------------------------------
# Trac dia: lat/lon -> met NED theo bang bien WGS84 (khong dung mot hang so cho ca hai truc)
# --------------------------------------------------------------------------
_A = 6378137.0
_E2 = 6.69437999014e-3


def latlon_to_ned(lat0_deg: float, lon0_deg: float, lat_deg: float, lon_deg: float) -> Tuple[float, float]:
    """(bac, dong) met cua (lat, lon) so voi (lat0, lon0); ban kinh cong theo vi do trung binh (khoang cach ngan)."""
    phim = math.radians(0.5 * (lat0_deg + lat_deg))
    s2 = math.sin(phim) ** 2
    w = math.sqrt(1.0 - _E2 * s2)
    m_rad = _A * (1.0 - _E2) / (w ** 3)      # ban kinh kinh tuyen
    n_rad = _A / w                            # ban kinh vi tuyen thang
    dn = math.radians(lat_deg - lat0_deg) * m_rad
    de = math.radians(lon_deg - lon0_deg) * n_rad * math.cos(phim)
    return dn, de


# --------------------------------------------------------------------------
# Dong ho: time_boot_ms cua FC -> dong ho don dieu cuc bo
# --------------------------------------------------------------------------
class FcClock:
    """t_local = t_fc + offset, offset = min(t_nhan - t_fc) (bo tre truyen), tang cham de theo troi dong ho."""

    def __init__(self, drift_alpha: float = 0.002, reset_back_s: float = 1.0):
        self.alpha = drift_alpha
        self.reset_back_s = reset_back_s
        self.offset: Optional[float] = None
        self._last_fc: Optional[float] = None
        self.resets = 0

    def update(self, fc_ms: float, rx_local: float) -> float:
        fc = fc_ms / 1000.0
        off = rx_local - fc
        if self._last_fc is not None and fc < self._last_fc - self.reset_back_s:
            self.offset = None            # FC khoi dong lai
            self.resets += 1
            self._last_fc = fc
        else:
            self._last_fc = fc if self._last_fc is None else max(self._last_fc, fc)
        if self.offset is None or off < self.offset:
            self.offset = off
        else:
            self.offset += self.alpha * (off - self.offset)
        return fc + self.offset

    def to_local(self, fc_ms: float) -> Optional[float]:
        return None if self.offset is None else fc_ms / 1000.0 + self.offset


class MavlinkLink:
    def __init__(self, cfg: Optional[MavlinkConfig] = None,
                 clock: Callable[[], float] = time.monotonic, mav=None):
        """mav: doi tuong ket noi pymavlink co san (de thu); None = tu mo theo cfg.connect."""
        self.cfg = cfg or MavlinkConfig()
        self.clock = clock
        self.mav = mav
        self.fc_clock = FcClock()
        self.target_system = 0
        self.target_component = 0
        # trang thai moi nhat
        self._att: Optional[Tuple[float, Tuple[float, float, float, float], float]] = None  # (t_local, q, rx)
        self._pos: Optional[Tuple[float, Tuple[float, float, float], Tuple[float, float, float], float]] = None
        self.global_pos: Optional[Tuple[float, float, float]] = None   # lat, lon (do), alt MSL (m)
        self.armed = False
        self.mode = ""
        self.custom_mode = -1
        self._hb_rx: Optional[float] = None
        self.rc: Dict[int, int] = {}
        self._rc_rx: Optional[float] = None
        self.last_ack: Optional[Tuple[int, int]] = None
        self.statustext: list = []
        # gui
        self.last_send_t: Optional[float] = None
        self.n_sent = 0
        self._last_cmd: Optional[GuidanceCommand] = None

    # ---- ket noi ----
    def connect(self) -> None:
        from pymavlink import mavutil
        self._mu = mavutil
        if self.mav is None:
            dev = self.cfg.connect
            kwargs = dict(source_system=self.cfg.source_system, source_component=self.cfg.source_component)
            if not (dev.startswith(("tcp:", "udp:", "udpin:", "udpout:", "tcpin:"))):
                dev, _, baud = dev.partition(",")
                kwargs["baud"] = int(baud) if baud else self.cfg.baud
            self.mav = mavutil.mavlink_connection(dev, **kwargs)
        t0 = self.clock()
        while True:
            hb = self.mav.recv_match(type="HEARTBEAT", blocking=True, timeout=1.0)
            if hb is not None and self._is_fc_heartbeat(hb):
                self.target_system = hb.get_srcSystem()
                self.target_component = hb.get_srcComponent()
                self.mav.target_system, self.mav.target_component = self.target_system, self.target_component
                self._on_heartbeat(hb, self.clock())
                break
            if self.clock() - t0 > self.cfg.heartbeat_timeout_s:
                raise RuntimeError("khong nhan duoc HEARTBEAT cua FC tu %s" % self.cfg.connect)
        self.request_streams()

    def _is_fc_heartbeat(self, m) -> bool:
        mu = self._mu
        return m.type != mu.mavlink.MAV_TYPE_GCS and m.autopilot != mu.mavlink.MAV_AUTOPILOT_INVALID

    def _set_interval(self, msg_id: int, hz: float) -> None:
        self._command(MAV_CMD_SET_MESSAGE_INTERVAL, msg_id, int(1e6 / hz) if hz > 0 else -1)

    def request_streams(self) -> None:
        c = self.cfg
        self._set_interval(MSG_ATTITUDE_QUATERNION, c.attitude_rate_hz)
        self._set_interval(MSG_LOCAL_POSITION_NED, c.position_rate_hz)
        self._set_interval(MSG_GLOBAL_POSITION_INT, c.global_rate_hz)
        self._set_interval(MSG_HEARTBEAT, c.heartbeat_rate_hz)
        self._set_interval(MSG_RC_CHANNELS, c.rc_rate_hz)

    def _command(self, command: int, *params: float) -> None:
        p = list(params) + [0.0] * (7 - len(params))
        self.mav.mav.command_long_send(self.target_system, self.target_component, command, 0, *p)

    # ---- nhan ----
    def _on_heartbeat(self, m, now: float) -> None:
        if not self._is_fc_heartbeat(m) or m.get_srcSystem() != self.target_system:
            return
        self.armed = bool(m.base_mode & MAV_MODE_FLAG_SAFETY_ARMED)
        self.custom_mode = int(m.custom_mode)
        self.mode = COPTER_MODES.get(self.custom_mode, "MODE%d" % self.custom_mode)
        self._hb_rx = now

    def poll(self) -> int:
        """Doc het ban tin dang cho (khong chan, toi da cfg.max_poll_s). Tra so ban tin da xu ly."""
        n = 0
        t_end = self.clock() + self.cfg.max_poll_s
        while True:
            m = self.mav.recv_match(blocking=False)
            if m is None:
                break
            n += 1
            self._handle(m, self.clock())
            if self.clock() > t_end:
                break
        return n

    def _handle(self, m, now: float) -> None:
        typ = m.get_type()
        if typ == "BAD_DATA":
            return
        if m.get_srcSystem() != self.target_system and typ != "HEARTBEAT":
            return
        if typ == "HEARTBEAT":
            self._on_heartbeat(m, now)
        elif typ == "ATTITUDE_QUATERNION":
            t = self.fc_clock.update(m.time_boot_ms, now)
            q = (m.q1, m.q2, m.q3, m.q4)
            self._att = (t, q, now)
        elif typ == "LOCAL_POSITION_NED":
            t = self.fc_clock.update(m.time_boot_ms, now)
            self._pos = (t, (m.x, m.y, m.z), (m.vx, m.vy, m.vz), now)
        elif typ == "GLOBAL_POSITION_INT":
            self.global_pos = (m.lat / 1e7, m.lon / 1e7, m.alt / 1000.0)
        elif typ == "RC_CHANNELS":
            self.rc = {i: getattr(m, "chan%d_raw" % i) for i in range(1, 19)}
            self._rc_rx = now
        elif typ == "COMMAND_ACK":
            self.last_ack = (m.command, m.result)
        elif typ == "STATUSTEXT":
            self.statustext.append(m.text)
            del self.statustext[:-20]

    # ---- trang thai ----
    def own_state(self) -> Optional[OwnState]:
        """OwnState moi nhat (quaternion than->NED); vi tri noi suy tuyen tinh theo van toc toi thoi diem tu the."""
        if self._att is None or self._pos is None:
            return None
        t_att, q, _ = self._att
        t_pos, p, v, _ = self._pos
        dt = max(-0.5, min(0.5, t_att - t_pos))
        pos = (p[0] + v[0] * dt, p[1] + v[1] * dt, p[2] + v[2] * dt)
        return OwnState(t=t_att, pos_ned=pos, vel_ned=tuple(v), q_world_body=q,
                        armed=self.armed, mode=self.mode)

    def heartbeat_age(self, now: Optional[float] = None) -> float:
        now = self.clock() if now is None else now
        return float("inf") if self._hb_rx is None else now - self._hb_rx

    def pose_age(self, now: Optional[float] = None) -> float:
        """Tuoi (theo thoi diem NHAN) cua du lieu cu nhat trong hai luong tu the/vi tri."""
        now = self.clock() if now is None else now
        if self._att is None or self._pos is None:
            return float("inf")
        return now - min(self._att[2], self._pos[3])

    def rc_channel(self, ch: int) -> Optional[int]:
        return self.rc.get(ch)

    def rc_engaged(self, ch: int, threshold_us: int, max_age_s: float = 1.0) -> bool:
        v = self.rc.get(ch)
        if v is None or self._rc_rx is None or self.clock() - self._rc_rx > max_age_s:
            return False
        return v != 65535 and v > threshold_us

    # ---- gui ----
    def send_velocity(self, vel_ned, yaw_rad: Optional[float] = None) -> bool:
        """Gui van toc NED (m/s) + yaw tuyet doi (rad, so voi Bac) bang SET_POSITION_TARGET_LOCAL_NED.
        Gia tri khong huu han -> gui phanh (0,0,0, bo yaw). Tra True neu lenh goc hop le."""
        ok = all(math.isfinite(float(c)) for c in vel_ned) and (yaw_rad is None or math.isfinite(yaw_rad))
        if not ok:
            vel_ned, yaw_rad = (0.0, 0.0, 0.0), None
        mask = MASK_VEL_ONLY if yaw_rad is None else MASK_VEL_YAW
        self.mav.mav.set_position_target_local_ned_send(
            0, self.target_system, self.target_component, MAV_FRAME_LOCAL_NED, mask,
            0.0, 0.0, 0.0, float(vel_ned[0]), float(vel_ned[1]), float(vel_ned[2]),
            0.0, 0.0, 0.0, 0.0 if yaw_rad is None else float(yaw_rad), 0.0)
        self.last_send_t = self.clock()
        self.n_sent += 1
        self._last_cmd = GuidanceCommand(t=self.last_send_t, vel_ned=tuple(float(c) for c in vel_ned),
                                         yaw_rad=yaw_rad)
        return ok

    def send_brake(self) -> None:
        self.send_velocity((0.0, 0.0, 0.0), None)

    def resend_due(self, now: Optional[float] = None) -> bool:
        now = self.clock() if now is None else now
        return self._last_cmd is not None and (self.last_send_t is None or
                                               now - self.last_send_t >= 1.0 / self.cfg.resend_hz)

    def resend_last(self) -> None:
        if self._last_cmd is not None:
            self.send_velocity(self._last_cmd.vel_ned, self._last_cmd.yaw_rad)

    def request_rtl(self) -> None:
        """Yeu cau FC doi sang RTL (MAV_CMD_DO_SET_MODE, custom mode). Ket qua xem last_ack / mode."""
        self._command(MAV_CMD_DO_SET_MODE, MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, MODE_RTL)

    def close(self) -> None:
        if self.mav is not None:
            try:
                self.mav.close()
            except Exception:
                pass
