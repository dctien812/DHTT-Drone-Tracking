"""Giam sat: may trang thai IDLE / SEARCH / TRACK / COAST / LOST / ABORT, dieu kien engage, watchdog.

Supervisor quyet dinh LENH CUOI CUNG gui cho FC. Quy tac:
- Chi gui lenh khi: FC da arm, dang o GUIDED, va co tin hieu engage. Het mot trong ba -> IDLE, ngung gui NGAY
  (khong tranh quyen voi phi cong). Supervisor khong bao gio yeu cau arm / cat canh / doi sang GUIDED.
- Watchdog: chu ky vong lap cham, mat HEARTBEAT, tuoi du lieu tu the qua nguong -> ABORT (phanh neu con link).
- Mat muc tieu: COAST theo du doan toi da coast_follow_s; sau do LOST: phanh ve van toc 0 giu vi tri;
  LOST (hoac chua tung thay muc tieu) qua lost_rtl_s -> yeu cau RTL mot lan (neu bat).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .config import GuidanceConfig, SupervisorConfig
from .guidance import Guidance
from .types import GuidanceCommand, OwnState, TrackState, TrackStatus

GUIDED_MODE = "GUIDED"


class SupState(Enum):
    IDLE = "idle"
    SEARCH = "search"
    TRACK = "track"
    COAST = "coast"
    LOST = "lost"
    ABORT = "abort"


@dataclass
class SupervisorInput:
    t: float                          # s, dong ho cuc bo
    track: TrackState
    own: Optional[OwnState]           # None = chua co tu the
    engage: bool                      # tin hieu engage (kenh RC hoac --auto-engage)
    heartbeat_age_s: float            # tuoi HEARTBEAT cuoi cua FC (inf = chua tung nhan)
    pose_age_s: float                 # tuoi du lieu tu the (inf = chua co)
    loop_dt_s: float = 0.0            # chu ky vong lap vua roi


@dataclass
class SupervisorOutput:
    state: SupState
    send: bool                        # co gui lenh khong
    cmd: Optional[GuidanceCommand]    # lenh de gui (None neu send False)
    request_rtl: bool = False
    reason: str = ""
    engaged: bool = False


def _cmd_ok(cmd: GuidanceCommand) -> bool:
    return (all(math.isfinite(c) for c in cmd.vel_ned)
            and (cmd.yaw_rad is None or math.isfinite(cmd.yaw_rad)))


class Supervisor:
    def __init__(self, cfg: Optional[SupervisorConfig] = None,
                 gcfg: Optional[GuidanceConfig] = None):
        self.cfg = cfg or SupervisorConfig()
        self.guidance = Guidance(gcfg or GuidanceConfig())
        self.state = SupState.IDLE
        self._reset_engaged()
        self.abort_reasons: List[str] = []

    def _reset_engaged(self) -> None:
        self._engage_t: Optional[float] = None
        self._had_target = False
        self._coast_t: Optional[float] = None
        self._lost_t: Optional[float] = None
        self._abort_clear_t: Optional[float] = None
        self._rtl_sent = False

    # ------------------------------------------------------------------
    def _faults(self, inp: SupervisorInput) -> List[str]:
        c = self.cfg
        f = []
        if not (inp.heartbeat_age_s <= c.heartbeat_timeout_s):
            f.append("heartbeat_lost(%.1fs)" % inp.heartbeat_age_s)
        if not (inp.pose_age_s <= c.pose_timeout_s):
            f.append("pose_stale(%.2fs)" % inp.pose_age_s)
        if not (inp.loop_dt_s <= c.loop_slow_s):
            f.append("loop_slow(%.3fs)" % inp.loop_dt_s)
        return f

    def step(self, inp: SupervisorInput) -> SupervisorOutput:
        c = self.cfg
        own = inp.own
        engaged = (own is not None and own.armed and own.mode == GUIDED_MODE and inp.engage
                   and (inp.pose_age_s < float("inf") or not c.require_pose_for_engage))
        if not engaged:
            if self.state != SupState.IDLE:
                self.guidance.reset()
            self.state = SupState.IDLE
            self._reset_engaged()
            why = "no_own" if own is None else (
                "disarmed" if not own.armed else
                "mode=%s" % own.mode if own.mode != GUIDED_MODE else "no_engage")
            return SupervisorOutput(SupState.IDLE, False, None, reason=why, engaged=False)
        if self._engage_t is None:
            self._engage_t = inp.t
            self._lost_t = inp.t        # "khong co muc tieu" tinh tu luc engage

        # ---- watchdog ----
        faults = self._faults(inp)
        if faults:
            self._abort_clear_t = None
            if self.state != SupState.ABORT:
                self.abort_reasons.append(";".join(faults))
            self.state = SupState.ABORT
            link_ok = inp.heartbeat_age_s <= c.heartbeat_timeout_s
            cmd = GuidanceCommand(t=inp.t, vel_ned=(0.0, 0.0, 0.0), yaw_rad=None, valid=True,
                                  reason="brake:abort:" + ";".join(faults))
            self.guidance.reset()
            return SupervisorOutput(SupState.ABORT, link_ok, cmd if link_ok else None,
                                    reason="abort:" + ";".join(faults), engaged=True)
        if self.state == SupState.ABORT:
            if self._abort_clear_t is None:
                self._abort_clear_t = inp.t
            if inp.t - self._abort_clear_t < c.abort_recover_s:
                cmd = GuidanceCommand(t=inp.t, vel_ned=(0.0, 0.0, 0.0), yaw_rad=None, valid=True,
                                      reason="brake:abort_recover")
                return SupervisorOutput(SupState.ABORT, True, cmd, reason="abort_recover", engaged=True)
            self.state = SupState.SEARCH
            self._lost_t = inp.t
            self._had_target = False
            self._coast_t = None

        # ---- trang thai theo muc tieu ----
        st = inp.track.status
        reason = ""
        if st == TrackStatus.TRACK:
            self.state = SupState.TRACK
            self._had_target = True
            self._coast_t = None
            self._lost_t = None
        elif st == TrackStatus.COAST and self._had_target:
            if self._coast_t is None:
                self._coast_t = inp.t
            if inp.t - self._coast_t <= c.coast_follow_s:
                self.state = SupState.COAST
            else:
                self.state = SupState.LOST
                reason = "coast_timeout"
                if self._lost_t is None:
                    self._lost_t = self._coast_t + c.coast_follow_s
        else:   # SEARCH / LOST cua tracker (hoac COAST khi chua tung co muc tieu)
            self._coast_t = None
            if self._had_target or self.state in (SupState.LOST, SupState.COAST, SupState.TRACK):
                self.state = SupState.LOST
                if self._lost_t is None:
                    self._lost_t = inp.t
            else:
                self.state = SupState.SEARCH
                if self._lost_t is None:
                    self._lost_t = inp.t

        # ---- lenh ----
        request_rtl = False
        if self.state in (SupState.TRACK, SupState.COAST):
            cmd = self.guidance.step(inp.track, own)
        else:
            cmd = self.guidance.step(inp.track, own)    # SEARCH/LOST -> guidance tra lenh phanh
            if not cmd.reason.startswith("brake"):
                cmd = GuidanceCommand(t=inp.t, vel_ned=(0.0, 0.0, 0.0), yaw_rad=None, valid=True,
                                      reason="brake:" + self.state.value)
        if not _cmd_ok(cmd) or not cmd.valid:
            cmd = GuidanceCommand(t=inp.t, vel_ned=(0.0, 0.0, 0.0), yaw_rad=None, valid=True,
                                  reason="brake:bad_cmd")
            reason = (reason + ";bad_cmd").strip(";")
        if (self.state in (SupState.LOST, SupState.SEARCH) and self._lost_t is not None
                and inp.t - self._lost_t > c.lost_rtl_s and c.rtl_on_lost and not self._rtl_sent):
            self._rtl_sent = True
            request_rtl = True
            reason = (reason + ";rtl_requested").strip(";")
        return SupervisorOutput(self.state, True, cmd, request_rtl=request_rtl,
                                reason=reason or cmd.reason, engaged=True)
