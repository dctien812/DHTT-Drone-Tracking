"""Giam sat: may trang thai IDLE / SEARCH / TRACK / COAST / LOST / ABORT, dieu kien engage, watchdog.

Supervisor quyet dinh LENH CUOI CUNG gui cho FC. Quy tac:
- Chi gui lenh khi: FC da arm, dang o GUIDED, va co tin hieu engage. Het mot trong ba -> IDLE, ngung gui NGAY
  (khong tranh quyen voi phi cong). Supervisor khong bao gio yeu cau arm / cat canh / doi sang GUIDED.
- Watchdog: chu ky vong lap cham, mat HEARTBEAT, tuoi du lieu tu the qua nguong -> ABORT (phanh neu con link).
- Mat muc tieu: COAST toi da coast_follow_s (ke ca khi tracker da bao LOST/SEARCH): bay tiep theo van toc muc tieu
  nho duoc, mui quay ve huong ngam cuoi; sau do LOST: phanh ve van toc 0 giu vi tri;
  LOST (hoac chua tung thay muc tieu) qua lost_rtl_s -> yeu cau RTL mot lan (neu bat).
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .config import GimbalConfig, GuidanceConfig, SearchConfig, SupervisorConfig
from .guidance import Guidance, yaw_from_quat
from .search import SearchEpisode, SearchInfo, SearchPlanner
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
    gimbal_delta_rad: Optional[float] = None   # goc khop THUC (chi dung khi bat khoi tim lai)


@dataclass
class SupervisorOutput:
    state: SupState
    send: bool                        # co gui lenh khong
    cmd: Optional[GuidanceCommand]    # lenh de gui (None neu send False)
    request_rtl: bool = False
    reason: str = ""
    engaged: bool = False
    search: Optional[SearchInfo] = None   # chi co khi search.enabled va dang engage


def _cmd_ok(cmd: GuidanceCommand) -> bool:
    return (all(math.isfinite(c) for c in cmd.vel_ned)
            and (cmd.yaw_rad is None or math.isfinite(cmd.yaw_rad)))


class Supervisor:
    def __init__(self, cfg: Optional[SupervisorConfig] = None,
                 gcfg: Optional[GuidanceConfig] = None,
                 scfg: Optional[SearchConfig] = None,
                 gimbal_cfg: Optional[GimbalConfig] = None):
        self.cfg = cfg or SupervisorConfig()
        self.guidance = Guidance(gcfg or GuidanceConfig())
        self.state = SupState.IDLE
        self._search_on = bool(scfg is not None and scfg.enabled)
        if self._search_on:
            gm = gimbal_cfg or GimbalConfig()
            self._episode = SearchEpisode(scfg, self.cfg.coast_follow_s)
            self._planner = SearchPlanner(scfg, math.radians(gm.delta_min_deg), math.radians(gm.delta_max_deg))
            self._delta_init = math.radians(gm.delta_init_deg)
        self._reset_engaged()
        self.abort_reasons: List[str] = []

    def _reset_search(self) -> None:
        """Dong dot mat (disengage, ABORT hoi phuc)."""
        self._episode.reset()
        self._searching = False                     # planner da begin trong dot hien tai
        self._search_yaw: Optional[float] = None    # yaw quet cuoi (giu khi TRACK chua du hold)
        self._last_yaw: Optional[float] = None      # yaw cua lenh cuoi (diem bat dau quet yaw)
        self._search_climb = 0.0
        self._last_vz: Optional[float] = None       # vz va t cua lenh cuoi (gioi han gia toc dung khi quet)
        self._last_t: Optional[float] = None

    def _reset_engaged(self) -> None:
        if self._search_on:
            self._reset_search()
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
            if self._search_on:
                self._reset_search()

        # ---- trang thai theo muc tieu ----
        st = inp.track.status
        reason = ""
        blind = False
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
        elif (st in (TrackStatus.LOST, TrackStatus.SEARCH) and self._had_target and self._coast_t is not None
              and inp.t - self._coast_t <= c.coast_follow_s):
            # tracker da bo muc tieu (reset sau coast_timeout) nhung con trong thoi han bay tiep: van COAST
            self.state = SupState.COAST
            blind = True
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

        # ---- khoi tim lai: dong ho dot mat (chi khi bat) ----
        tick = None
        sinfo_scan: Optional[float] = None
        sinfo_r: Optional[float] = None
        searching = False
        if self._search_on:
            tick = self._episode.update(inp.t, st == TrackStatus.TRACK, self._had_target)
            searching = tick.ep_s is not None and not tick.closed and tick.phase >= 1
            if tick.closed:
                self._searching = False

        # ---- lenh ----
        request_rtl = False
        if searching:
            cmd, reason, sinfo_scan = self._step_search(inp, tick, st == TrackStatus.TRACK)
            sinfo_r = self.guidance.last_r_hat
        elif blind:
            cmd = self.guidance.step_blind(inp.track, own)
            if self._search_on:
                sinfo_r = self.guidance.last_r_hat
        elif self.state in (SupState.TRACK, SupState.COAST):
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
        if self._search_on and self._had_target:
            # da tung thay muc tieu: RTL khi dot mat het han (bat ke trang thai tracker); chua tung thay: luat cu
            want_rtl = tick.expired
        else:
            want_rtl = (self.state in (SupState.LOST, SupState.SEARCH) and self._lost_t is not None
                        and inp.t - self._lost_t > c.lost_rtl_s)
        if want_rtl and c.rtl_on_lost and not self._rtl_sent:
            self._rtl_sent = True
            request_rtl = True
            reason = (reason + ";rtl_requested").strip(";")
        sinfo = None
        if self._search_on:
            if cmd.yaw_rad is not None:
                self._last_yaw = cmd.yaw_rad
            self._last_vz, self._last_t = cmd.vel_ned[2], inp.t
            sinfo = SearchInfo(tick.ep_id, tick.ep_s, tick.phase, tick.run_s, tick.closed,
                               self._search_climb if searching else 0.0, sinfo_scan, sinfo_r)
        return SupervisorOutput(self.state, True, cmd, request_rtl=request_rtl,
                                reason=reason or cmd.reason, engaged=True, search=sinfo)

    def _step_search(self, inp: SupervisorInput, tick, tracking: bool):
        """Pha >= 1 cua dot mat (khong phai tick dong dot): treo bang step_hover, quet khop + yaw (+ leo o pha 2).
        TRACK chua du hold (S-3): van treo, khop ngung quet, yaw giu. Tra (cmd, reason, scan_delta_rad|None)."""
        own = inp.own
        if not self._searching:
            yaw0 = self._last_yaw if self._last_yaw is not None else yaw_from_quat(own.q_world_body)
            delta0 = inp.gimbal_delta_rad
            if delta0 is None or not math.isfinite(delta0):
                delta0 = self._delta_init
            self._planner.begin(inp.t, own, yaw0, delta0, self.guidance.stopped_target_ned(inp.t, own))
            self._searching = True
            self._search_yaw = yaw0
            self._search_climb = 0.0
        # track thay bang LOST: step_hover khong duoc duoi muc tieu ke ca khi het bo nho (khi do chi phanh)
        hov = self.guidance.step_hover(TrackState(t=inp.track.t, status=TrackStatus.LOST), own)
        vx, vy, vz = hov.vel_ned
        if tracking:
            self.state = SupState.TRACK
            scan = None
            why = "search:hold"
        else:
            self.state = SupState.LOST
            so = self._planner.step(inp.t, own, tick.phase)
            if so.vel_ned[2] < 0.0:
                vz = so.vel_ned[2]
            if so.yaw_rad is not None:
                self._search_yaw = so.yaw_rad
            self._search_climb = so.climb_m
            scan = so.scan_delta_rad
            why = so.reason
        if self._last_vz is not None and self._last_t is not None:
            # vz khong nhay qua gioi han gia toc dung (nhu guidance)
            g = self.guidance.cfg
            lim = g.a_max_z_mps2 * min(max(inp.t - self._last_t, 1e-3), g.dt_max_s)
            vz = max(self._last_vz - lim, min(self._last_vz + lim, vz))
        cmd = GuidanceCommand(t=inp.t, vel_ned=(vx, vy, vz), yaw_rad=self._search_yaw, valid=True, reason=why)
        if self.guidance.prev is not None:
            # guidance.step tiep quan sau khi dong dot phai xuat phat tu yaw/vz quet, khong tu yaw/vz noi bo cua step_hover
            self.guidance.prev = dataclasses.replace(self.guidance.prev, vel_ned=cmd.vel_ned, yaw_rad=cmd.yaw_rad)
        return cmd, why, scan
