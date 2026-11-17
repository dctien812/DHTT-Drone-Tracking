#!/usr/bin/env python3
"""Ham dung chung cho target.py va chaser.py (pymavlink). Khong chay truc tiep."""
import math
import sys
import time

from pymavlink import mavutil

# Hang so ArduPilot: LOCATION_SCALING_FACTOR (m tren do) = 0.011131884502145034 * 1e7
M_PER_DEG = 111318.84502145034
# Goc nha cua target (CMAC); chaser xuat phat cach 15 m ve phia nam (xem run_chase.sh)
TARGET_HOME = (-35.363261, 149.165230, 584.0, 0.0)
CHASER_HOME = (-35.3633957, 149.165230, 584.0, 0.0)
GUIDED = 4  # ArduCopter custom_mode cua GUIDED
# SET_POSITION_TARGET_LOCAL_NED: chi dung van toc (bo qua vi tri, gia toc, yaw, yaw_rate)
VEL_ONLY_MASK = 0b110111000111  # = 3527


def log(tag, msg):
    print("[%s] %s" % (tag, msg), flush=True)


class Pos:
    """Vi tri/van toc NED (m, m/s) so voi goc toa do chung, kem thoi gian sim (s)."""

    def __init__(self, t, n, e, alt, vn, ve, vd):
        self.t, self.n, self.e, self.alt = t, n, e, alt
        self.vn, self.ve, self.vd = vn, ve, vd

    @property
    def hspeed(self):
        return math.hypot(self.vn, self.ve)


class Vehicle:
    def __init__(self, url, tag, origin, connect_timeout=180):
        self.tag = tag
        self.lat0, self.lon0 = origin[0], origin[1]
        self.pos = None
        self.armed = False
        self.mode = None
        self.last_ack = None
        t0 = time.time()
        while True:
            try:
                self.mav = mavutil.mavlink_connection(
                    url, source_system=255, source_component=190)
                if self.mav.wait_heartbeat(timeout=10):
                    break
            except OSError as exc:
                log(tag, "chua noi duoc %s: %s" % (url, exc))
            if time.time() - t0 > connect_timeout:
                raise RuntimeError("khong noi duoc %s sau %d s" % (url, connect_timeout))
            time.sleep(2)
        log(tag, "da noi %s (sysid %d)" % (url, self.mav.target_system))

    def cmd(self, command, *params):
        p = list(params) + [0] * (7 - len(params))
        self.mav.mav.command_long_send(
            self.mav.target_system, self.mav.target_component, command, 0, *p)

    def request_gpi(self, hz):
        # MAV_CMD_SET_MESSAGE_INTERVAL (511), message 33 = GLOBAL_POSITION_INT
        self.cmd(511, 33, int(1e6 / hz))

    def pump(self, timeout=0.0):
        """Doc 1 ban tin; tra ve ten loai ban tin hoac None neu khong co."""
        m = self.mav.recv_match(blocking=timeout > 0, timeout=timeout if timeout > 0 else None)
        if m is None:
            return None
        typ = m.get_type()
        if typ == "GLOBAL_POSITION_INT":
            self.pos = Pos(
                m.time_boot_ms / 1000.0,
                (m.lat / 1e7 - self.lat0) * M_PER_DEG,
                (m.lon / 1e7 - self.lon0) * M_PER_DEG * math.cos(math.radians(self.lat0)),
                m.relative_alt / 1000.0,
                m.vx / 100.0, m.vy / 100.0, m.vz / 100.0)
        elif typ == "HEARTBEAT" and m.get_srcSystem() == self.mav.target_system \
                and m.type != mavutil.mavlink.MAV_TYPE_GCS:
            self.armed = bool(m.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            self.mode = m.custom_mode
        elif typ == "COMMAND_ACK":
            self.last_ack = (m.command, m.result)
        elif typ == "STATUSTEXT":
            log(self.tag, "FC: %s" % m.text)
        return typ

    def drain(self):
        while self.pump(0.0) is not None:
            pass

    def send_vel(self, vn, ve, vd):
        self.mav.mav.set_position_target_local_ned_send(
            0, self.mav.target_system, self.mav.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED, VEL_ONLY_MASK,
            0, 0, 0, vn, ve, vd, 0, 0, 0, 0, 0)

    def arm_and_takeoff(self, alt, timeout=400):
        """GUIDED, arm (thu lai cho toi khi EKF san sang), cat canh den alt (m)."""
        t0 = time.time()
        last = 0.0
        while not self.armed or self.mode != GUIDED:
            self.pump(0.5)
            if time.time() - last > 3.0:
                last = time.time()
                self.cmd(176, 1, GUIDED)   # MAV_CMD_DO_SET_MODE
                self.cmd(400, 1)           # MAV_CMD_COMPONENT_ARM_DISARM
            if time.time() - t0 > timeout:
                raise RuntimeError("khong arm duoc sau %d s" % timeout)
        log(self.tag, "da arm, mode GUIDED")
        last = 0.0
        while self.pos is None or self.pos.alt < 0.95 * alt:
            self.pump(0.5)
            if time.time() - last > 3.0 and (self.pos is None or self.pos.alt < 1.0):
                last = time.time()
                self.cmd(22, 0, 0, 0, 0, 0, 0, alt)  # MAV_CMD_NAV_TAKEOFF
            if time.time() - t0 > timeout:
                raise RuntimeError("khong cat canh duoc")
        log(self.tag, "da dat do cao %.1f m" % self.pos.alt)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))
