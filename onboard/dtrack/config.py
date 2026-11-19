"""Cau hinh khoi DIEU KHIEN / giam sat. Don vi ghi ro o moi truong (hau to _m, _mps, _s, _deg...).

Nap tu file TOML hoac JSON tuy chon: moi muc (guidance, supervisor, mavlink, camera, app)
la mot bang/doi tuong con, chi can ghi cac khoa muon doi; khoa la se bi tu choi (tranh go sai ten).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Dict, Optional

from .synthetic import SyntheticConfig
from .types import CameraModel


@dataclass
class GuidanceConfig:
    # --- khoang cach ---
    range_set_m: float = 15.0          # m, khoang cach dat
    range_tau_s: float = 0.0           # s, r_dat = max(range_set_m, tau * |v ban than|); 0 = co dinh
    range_min_m: float = 12.5          # m, nguong lui khan (> 8 m an toan cung: FC tre ~1 s, muc tieu cat canh dung ~8 m/s^2): duoi nguong -> lui theo duong ngam
    range_back_m: float = 12.5         # m, vao che do lui khi r < range_back_m (>= range_min_m; mac dinh = range_min_m: khong lui som)
    range_min_hyst_m: float = 1.0      # m, thoat che do lui khi r > range_back + hyst
    back_speed_mps: float = 8.0        # m/s, toc do lui (tuong doi so voi muc tieu) khi duoi khoang cach toi thieu
    kp_range: float = 0.3              # 1/s, he so ti le (r - r_dat) -> van toc doc duong ngam
    close_speed_max_mps: float = 3.0   # m/s, gioi han thanh phan P tien lai gan (so voi van toc muc tieu uoc luong)
    open_speed_max_mps: float = 3.0    # m/s, gioi han thanh phan P lui ra
    # --- khop van toc muc tieu ---
    range_rate_max_mps: float = 60.0   # m/s, |r_dot| duoc dung toi da (cat)
    los_rate_max_rad_s: float = 1.5    # rad/s, |los_rate| duoc dung toi da (cat)
    invalid_decel_mps2: float = 2.0    # m/s^2, khi range_valid=False: giam thanh phan tien lai gan tu lenh truoc
    # --- giu muc tieu o giua anh (phuong dung) ---
    kp_vert_center: float = 0.5        # (m/s)/m, do lech dung (m = r*tan(goc lech)) -> van toc dung
    vert_center_max_mps: float = 2.5   # m/s, gioi han thanh phan dung do giu giua anh
    target_elev_ref_deg: float = 4.0   # do, goc nang MONG MUON cua muc tieu so voi mat phang ngang cua drone khi khong tang/giam toc
    elev_accel_comp: float = 1.0       # he so bu nghieng mui theo gia toc lenh; = 0 khi camera tu on dinh pitch (khop gat), dat tu dong trong AppConfig
    elev_ref_max_deg: float = 8.0      # do, goc nang mong muon bi cat trong +-gia tri nay (bu truoc mui chui khi tang toc theo GIA TOC LENH, khong theo tu the do)
    elev_ramp_enabled: bool = False    # bat/tat doc chuyen tiep goc nang tham chieu sau khi khoa muc tieu
    elev_ramp_dps: float = 2.0         # do/s, toc do doc chuyen tiep (diem cuoi = target_elev_ref_deg)
    # --- gioi han ---
    v_max_mps: float = 30.0            # m/s, toc do ngang toi da cua lenh
    climb_max_mps: float = 4.0         # m/s, toc do len toi da
    descend_max_mps: float = 4.8       # m/s, toc do xuong toi da
    a_max_mps2: float = 3.5            # m/s^2, gia toc ngang toi da cua lenh (muc tieu cat canh tang toc ~4.5 m/s^2; nghieng mui chui duoc bu bang do cao muc tieu mong muon, xem target_elev_ref_deg)
    a_lat_mps2: float = 7.0            # m/s^2, gia toc ngang toi da VUONG GOC huong bay (re): muc tieu 20 m/s re 15 do/s can ~5.2 m/s^2 huong tam
    a_decel_mps2: float = 3.0          # m/s^2, gia toc ngang toi da khi GIAM toc do (cung dung de gioi han toc do tien lai gan theo quang phanh: v_close <= sqrt(2*a_decel*(r - range_min)))
    a_back_mps2: float = 12.0           # m/s^2, gia toc ngang toi da khi dang lui do duoi khoang cach toi thieu (uu tien cao hon a_max)
    a_max_z_mps2: float = 1.5          # m/s^2, gia toc dung toi da
    jerk_max_mps3: float = 10.0        # m/s^3, toc do doi gia toc lenh toi da
    jerk_back_mps3: float = 80.0       # m/s^3, nhu tren nhung khi dang lui khan duoi range_min
    # --- mat muc tieu (COAST / mat han): bay tiep theo van toc muc tieu uoc luong cuoi ---
    v_t_mem_tau_s: float = 0.5         # s, hang so loc (EMA) cua van toc muc tieu nho duoc luc con TRACK hop le
    blind_grace_s: float = 1.0         # s, sau chung nay ke tu lan TRACK hop le cuoi moi bat dau giam toc do bay tiep
    blind_decel_mps2: float = 1.0      # m/s^2, toc do ngang bay tiep giam dan (phong muc tieu dung/phanh luc mat hinh)
    blind_mem_max_s: float = 8.0       # s, bo nho muc tieu cu hon chung nay thi bo (khong dung de bay tiep)
    # --- an toan luc mu (design-search.md muc (e), S-10, S-13); mac dinh = hanh vi cu ---
    blind_floor_m: float = 0.0         # m, san khoang cach luc mu (lui khan khi r_hat < san + bien + quang dung); 0 = tat
    blind_back_margin_m: float = 2.0   # m, bien cong them tren san de bat dau lui/phanh
    blind_target_decel_mps2: float = 3.0   # m/s^2, mo hinh muc tieu ham ngay luc mat hinh (dung cho r_hat)
    blind_v_cap_mps: float = 0.0       # m/s, tran toc do ngang luc mu; 0 = khong gioi han
    blind_grace_model_s: float = 1.5   # s, trong chung nay ke tu luc mat chi dung mo hinh giu nguyen van toc cho r_hat; 0 = luon lay min hai mo hinh
    blind_react_s: float = 1.0        # s, tre phan ung cua FC dung trong quang dung d_dung = v_tien*react + v_tien^2/(2*a_back)
    dt_default_s: float = 1.0 / 30     # s, dt khi chua co lenh truoc
    dt_max_s: float = 0.2              # s, dt toi da dung de gioi han (lenh truoc cu hon -> coi nhu 0.2 s)
    yaw_lead_s: float = 0.5            # s, yaw lenh = huong ngam + toc do quay ngang cua duong ngam * yaw_lead_s (bu tre FC)
    yaw_rate_max_dps: float = 90.0     # do/s, toc do doi yaw lenh toi da
    min_alt_m: float = 10.0            # m, do cao toi thieu so voi diem home EKF: duoi nguong khong duoc xuong them
    # --- camera (de tinh do lech dung cua muc tieu trong anh) ---
    # Dung chung voi CameraConfig; guidance chi can R_body_cam.
    cam_tilt_up_deg: float = 15.0      # do, camera ngang len so voi truc mui


@dataclass
class SupervisorConfig:
    coast_follow_s: float = 4.0        # s, COAST (ke ca khi tracker da bao LOST): bay tiep theo van toc muc tieu cuoi toi da chung nay, het han moi phanh ve treo
    lost_rtl_s: float = 10.0           # s, khong co muc tieu qua chung nay -> yeu cau RTL
    rtl_on_lost: bool = True           # bat/tat yeu cau RTL
    heartbeat_timeout_s: float = 3.0   # s, mat HEARTBEAT cua FC -> ABORT (GUIDED tu dung sau 3 s khong lenh)
    pose_timeout_s: float = 0.5        # s, tuoi du lieu tu the (thoi diem nhan) -> ABORT
    loop_slow_s: float = 0.25          # s, chu ky vong lap cham hon nguong -> ABORT
    abort_recover_s: float = 1.0       # s, het loi roi giu ABORT them chung nay roi moi ve SEARCH
    engage_rc_channel: int = 8         # kenh RC (1-based) dung lam tin hieu engage khi bay that
    engage_rc_threshold_us: int = 1700  # us, kenh > nguong = engage
    require_pose_for_engage: bool = True


@dataclass
class MavlinkConfig:
    connect: str = "tcp:127.0.0.1:5770"   # tcp:host:port | udp:host:port | udpin:host:port | /dev/ttyXXX[,baud]
    baud: int = 115200                    # baud khi noi serial
    source_system: int = 1                # sysid cua may dong hanh (khong trung sysid FC)
    source_component: int = 191           # MAV_COMP_ID_ONBOARD_COMPUTER
    heartbeat_timeout_s: float = 10.0     # s, cho HEARTBEAT dau tien khi ket noi
    attitude_rate_hz: float = 50.0        # Hz, ATTITUDE_QUATERNION
    position_rate_hz: float = 50.0        # Hz, LOCAL_POSITION_NED
    global_rate_hz: float = 10.0          # Hz, GLOBAL_POSITION_INT
    heartbeat_rate_hz: float = 10.0       # Hz, yeu cau HEARTBEAT (de nhan ra doi che do nhanh; FC co the bo qua)
    rc_rate_hz: float = 10.0              # Hz, RC_CHANNELS
    resend_hz: float = 10.0               # Hz, toi thieu gui lai lenh (GUIDED dung sau 3 s khong co lenh)
    max_poll_s: float = 0.010             # s, thoi gian toi da cho moi lan doc ban tin


@dataclass
class CameraConfig:
    tilt_up_deg: float = 15.0   # do, camera ngang len so voi truc mui (quad nghieng mui xuong khi tang toc)
    fx: float = 1739.0          # px (lens 6 mm, ~45x35 do; lens 8 mm: 2319, chi ~35x26 do - qua hep cho camera co dinh)
    fy: float = 1739.0
    width: int = 1456
    height: int = 1088
    # khop gat mot truc on dinh pitch (CHI mo phong/do dac; mac dinh TAT = camera co dinh)
    gimbal_enabled: bool = False
    gimbal_travel_deg: float = 50.0    # do, hanh trinh +- quanh vi tri lap danh dinh
    gimbal_rate_dps: float = 300.0     # do/s, toc do quay toi da
    gimbal_lag_s: float = 0.05         # s, tre bac nhat cua servo

    def to_model(self) -> CameraModel:
        return make_camera(self.tilt_up_deg, self.fx, self.fy, self.width, self.height)


@dataclass
class GimbalConfig:
    """Khop gat chu dong mot truc (buoc 3 thiet ke). Bat bang enabled=True; hai co cung bat thi validate() tu choi."""
    enabled: bool = False
    delta_min_deg: float = 10.0
    delta_max_deg: float = 110.0
    delta_init_deg: float = 90.0
    hold_offset_deg: float = 0.0
    frozen: bool = False
    rate_dps: float = 300.0
    lag_s: float = 0.05
    dead_time_s: float = 0.02
    quant_deg: float = 0.1
    slow_factor: float = 1.0


@dataclass
class SearchConfig:
    """Khoi tim lai muc tieu khi mat (design-search.md muc (b), S-9). Mac dinh TAT = hanh vi cu (RTL o lost_rtl_s).
    Cac rang buoc chi duoc kiem khi enabled=True (va bat buoc gimbal.enabled)."""
    enabled: bool = False
    total_s: float = 20.0              # s, tim toi da tinh tu COAST dau cua dot mat; het han -> yeu cau RTL mot lan
    reacquire_hold_s: float = 1.0      # s, TRACK lien tuc toi thieu de coi la bat lai (dong dot)
    climb_m: float = 0.0               # m, do cao leo them o pha 2 (0 = khong co pha 2)
    climb_start_s: float = 10.0        # s, pha 2 bat dau o ep_s nay (neu climb_m > 0)
    climb_rate_mps: float = 2.0        # m/s, toc do leo toi da o pha 2
    scan_rate_dps: float = 60.0        # do/s, toc do quet khop
    scan_lo_deg: float = 10.0          # do, bien duoi dai quet khop
    scan_hi_deg: float = 110.0         # do, bien tren dai quet khop
    climb_scan_lo_deg: float = 70.0    # do, bien duoi dai quet o pha 2 (dai thap)
    yaw_amp_deg: float = 45.0          # do, bien do quet yaw quanh yaw luc bat dau pha 1 (0 = khong quet yaw)
    yaw_rate_dps: float = 20.0         # do/s, toc do quet yaw


@dataclass
class TargetShapeConfig:
    """Hop bao ba canh cua muc tieu that (mac dinh khoi 0.30 m = hanh vi cu). Bo uoc luong khoang cach dung span_m."""
    span_m: float = 0.30      # m, ngang vuong goc mui (sai canh)
    length_m: float = 0.30    # m, doc mui (than)
    height_m: float = 0.30    # m, theo phuong dung


@dataclass
class AcceptanceConfig:
    """Nguong cham nghiem thu mo phong (chi tai lieu: simtools/analyze_closed_loop.py doc JSON thua app_cfg.json)."""
    hard_floor_m: float = 8.0         # m, khoang cach that khong bao gio nho hon
    dive_range_min_m: float = 12.5    # m, can duoi d3 trong pha cam va pha giam toc cuoi


@dataclass
class AppConfig:
    loop_hz: float = 30.0
    brake_on_exit_s: float = 15.0   # s, toi da phanh tuong minh khi ket thuc truoc khi thoat
    brake_exit_speed_mps: float = 0.5  # m/s, coi la da dung
    log_dir: str = "logs"
    log_queue: int = 20000
    guidance: GuidanceConfig = field(default_factory=GuidanceConfig)
    supervisor: SupervisorConfig = field(default_factory=SupervisorConfig)
    mavlink: MavlinkConfig = field(default_factory=MavlinkConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    gimbal: GimbalConfig = field(default_factory=GimbalConfig)
    target_shape: TargetShapeConfig = field(default_factory=TargetShapeConfig)
    acceptance: AcceptanceConfig = field(default_factory=AcceptanceConfig)
    synthetic: SyntheticConfig = field(default_factory=SyntheticConfig)
    search: SearchConfig = field(default_factory=SearchConfig)

    def __post_init__(self) -> None:
        if self.gimbal.enabled:
            self.camera.tilt_up_deg = 0.0
        self.guidance.cam_tilt_up_deg = self.camera.tilt_up_deg
        if self.camera.gimbal_enabled or self.gimbal.enabled:
            self.guidance.elev_accel_comp = 0.0


def make_camera(tilt_up_deg: float = 0.0, fx: float = 2319.0, fy: Optional[float] = None,
                width: int = 1456, height: int = 1088) -> CameraModel:
    """CameraModel voi camera ngang len tilt_up_deg so voi truc mui (quanh truc y than).

    Truc quang z_cam = (cos t, 0, -sin t) trong he than FRD; x_cam = y_than; y_cam = (sin t, 0, cos t).
    R_body_cam co cot = cac truc do (t = 0 trung voi mac dinh cua types.CameraModel).
    """
    t = math.radians(tilt_up_deg)
    s, c = math.sin(t), math.cos(t)
    R = ((0.0, s, c), (1.0, 0.0, 0.0), (0.0, c, -s))
    return CameraModel(width=width, height=height, fx=fx, fy=fx if fy is None else fy,
                       cx=width / 2.0, cy=height / 2.0, R_body_cam=R)


def validate(cfg: AppConfig) -> None:
    g, s = cfg.guidance, cfg.supervisor
    if g.range_min_m <= 0 or g.range_set_m < g.range_min_m + g.range_min_hyst_m:
        raise ValueError("range_set_m phai >= range_min_m + range_min_hyst_m")
    if g.range_back_m < g.range_min_m:
        raise ValueError("range_back_m phai >= range_min_m")
    if g.range_set_m < g.range_back_m + g.range_min_hyst_m:
        raise ValueError("range_set_m phai >= range_back_m + range_min_hyst_m")
    for name in ("v_max_mps", "a_max_mps2", "a_max_z_mps2", "jerk_max_mps3", "climb_max_mps", "descend_max_mps"):
        v = getattr(g, name)
        if not (math.isfinite(v) and v > 0):
            raise ValueError("%s phai > 0" % name)
    for name, lo, hi in (("blind_floor_m", 0.0, math.inf), ("blind_back_margin_m", 0.0, math.inf),
                         ("blind_v_cap_mps", 0.0, g.v_max_mps), ("blind_react_s", 0.0, 5.0),
                         ("blind_grace_model_s", 0.0, 3.0)):
        v = getattr(g, name)
        if not (math.isfinite(v) and lo <= v <= hi):
            raise ValueError("guidance.%s phai trong [%g, %g]" % (name, lo, hi))
    if not (math.isfinite(g.blind_target_decel_mps2) and g.blind_target_decel_mps2 > 0):
        raise ValueError("guidance.blind_target_decel_mps2 phai > 0")
    if g.blind_floor_m >= g.range_set_m:
        raise ValueError("guidance.blind_floor_m phai < range_set_m")
    if g.blind_back_margin_m > g.range_set_m:
        raise ValueError("guidance.blind_back_margin_m phai <= range_set_m")
    for name in ("span_m", "length_m", "height_m"):
        v = getattr(cfg.target_shape, name)
        if not (math.isfinite(v) and v > 0):
            raise ValueError("target_shape.%s phai > 0" % name)
    for name in ("hard_floor_m", "dive_range_min_m"):
        v = getattr(cfg.acceptance, name)
        if not (math.isfinite(v) and v > 0):
            raise ValueError("acceptance.%s phai > 0" % name)
    if cfg.acceptance.hard_floor_m > cfg.acceptance.dive_range_min_m:
        raise ValueError("acceptance.hard_floor_m phai <= dive_range_min_m")
    if cfg.loop_hz <= 0 or s.loop_slow_s <= 0:
        raise ValueError("loop_hz / loop_slow_s phai > 0")
    if cfg.mavlink.resend_hz < 10.0:
        raise ValueError("resend_hz phai >= 10 (GUIDED dung sau 3 s khong co lenh)")
    # --- khop gat chu dong ---
    gm = cfg.gimbal
    if cfg.camera.gimbal_enabled and gm.enabled:
        raise ValueError("camera.gimbal_enabled va gimbal.enabled khong duoc cung bat")
    if not (0 < gm.delta_min_deg < gm.delta_max_deg <= 120):
        raise ValueError("gimbal: can 0 < delta_min_deg < delta_max_deg <= 120")
    if not (gm.delta_min_deg <= gm.delta_init_deg <= gm.delta_max_deg):
        raise ValueError("gimbal: can delta_min_deg <= delta_init_deg <= delta_max_deg")
    if not (math.isfinite(gm.rate_dps) and gm.rate_dps > 0):
        raise ValueError("gimbal.rate_dps phai > 0")
    if not (math.isfinite(gm.lag_s) and gm.lag_s >= 0):
        raise ValueError("gimbal.lag_s phai >= 0")
    if not (math.isfinite(gm.dead_time_s) and gm.dead_time_s >= 0):
        raise ValueError("gimbal.dead_time_s phai >= 0")
    if not (math.isfinite(gm.quant_deg) and gm.quant_deg >= 0):
        raise ValueError("gimbal.quant_deg phai >= 0")
    if not (math.isfinite(gm.slow_factor) and gm.slow_factor > 0):
        raise ValueError("gimbal.slow_factor phai > 0")
    if g.elev_ramp_enabled and not (math.isfinite(g.elev_ramp_dps) and g.elev_ramp_dps > 0):
        raise ValueError("guidance.elev_ramp_dps phai > 0 khi bat")
    # --- khoi tim lai muc tieu ---
    sr = cfg.search
    if sr.enabled:
        if not gm.enabled:
            raise ValueError("search.enabled can gimbal.enabled")
        cf = s.coast_follow_s
        if g.blind_mem_max_s < cf:
            raise ValueError("search.enabled can guidance.blind_mem_max_s >= supervisor.coast_follow_s")
        if not (math.isfinite(sr.total_s) and cf < sr.total_s <= 300.0):
            raise ValueError("search.total_s phai trong (supervisor.coast_follow_s, 300]")
        if not (0.2 <= sr.reacquire_hold_s <= 10.0):
            raise ValueError("search.reacquire_hold_s phai trong [0.2, 10]")
        if not (math.isfinite(sr.climb_m) and sr.climb_m >= 0.0):
            raise ValueError("search.climb_m phai huu han, >= 0")
        if not (cf < sr.climb_start_s < sr.total_s):
            raise ValueError("search.climb_start_s phai trong (supervisor.coast_follow_s, search.total_s)")
        if not (0.0 < sr.climb_rate_mps <= g.climb_max_mps):
            raise ValueError("search.climb_rate_mps phai trong (0, guidance.climb_max_mps]")
        if not (0.0 < sr.scan_rate_dps <= 0.5 * gm.rate_dps / gm.slow_factor):
            raise ValueError("search.scan_rate_dps phai trong (0, 0.5*gimbal.rate_dps/slow_factor]")
        if not (gm.delta_min_deg <= sr.scan_lo_deg and sr.scan_hi_deg <= gm.delta_max_deg
                and sr.scan_hi_deg - sr.scan_lo_deg >= 20.0):
            raise ValueError("search.scan_lo_deg/scan_hi_deg phai nam trong dai khop va cach nhau >= 20 do")
        if not (sr.scan_lo_deg <= sr.climb_scan_lo_deg < sr.scan_hi_deg):
            raise ValueError("search.climb_scan_lo_deg phai trong [scan_lo_deg, scan_hi_deg)")
        if not (0.0 <= sr.yaw_amp_deg <= 90.0):
            raise ValueError("search.yaw_amp_deg phai trong [0, 90]")
        if not (0.0 < sr.yaw_rate_dps <= g.yaw_rate_max_dps):
            raise ValueError("search.yaw_rate_dps phai trong (0, guidance.yaw_rate_max_dps]")
    # --- nguon phat hien mo phong 'realdet' ---
    sy = cfg.synthetic
    if not (0.0 <= sy.burst_start_p <= 1.0):           # NaN cung bi tu choi (so sanh sai)
        raise ValueError("synthetic.burst_start_p phai trong [0, 1]")
    if not (math.isfinite(sy.burst_len_mean_frames) and sy.burst_len_mean_frames > 0):
        raise ValueError("synthetic.burst_len_mean_frames phai > 0")
    if sy.realdet_enabled and len(sy.p_detect_px) == 0:
        raise ValueError("synthetic.p_detect_px khong duoc rong khi realdet_enabled")
    prev = None
    for row in sy.p_detect_px:
        if len(row) != 2:
            raise ValueError("synthetic.p_detect_px: moi dong la cap (px, p)")
        px, p = float(row[0]), float(row[1])
        if not math.isfinite(px) or not (0.0 <= p <= 1.0):
            raise ValueError("synthetic.p_detect_px: px huu han, p trong [0, 1]")
        if prev is not None and (px <= prev[0] or p < prev[1]):
            raise ValueError("synthetic.p_detect_px: px phai tang chat, p khong duoc giam theo co")
        prev = (px, p)


def _fill(obj: Any, data: Dict[str, Any], path: str) -> None:
    names = {f.name: f for f in fields(obj)}
    for k, v in data.items():
        if k not in names:
            raise ValueError("khoa la trong cau hinh: %s.%s" % (path, k))
        cur = getattr(obj, k)
        if is_dataclass(cur):
            if not isinstance(v, dict):
                raise ValueError("%s.%s phai la bang/doi tuong" % (path, k))
            _fill(cur, v, path + "." + k)
        else:
            if isinstance(cur, bool):
                if not isinstance(v, bool):
                    raise ValueError("%s.%s phai la true/false that, khong phai %r" % (path, k, v))
            elif isinstance(cur, int):
                v = int(v)
            elif isinstance(cur, float):
                v = float(v)
            setattr(obj, k, v)


# Ho so co ten (chi ghi cac khoa khac mac dinh; mac dinh cu GIU NGUYEN). Dung: profile_dict(ten) -> dict nhu file JSON.
PROFILES: Dict[str, Dict[str, Any]] = {
    # cau hinh NGHIEM THU B6b: khop gat mot truc on dinh pitch + giu 25 m (muc tieu bay thang 10 m/s roi phanh ~8 m/s^2)
    "accept_gimbal_r25": {
        "guidance": {"range_set_m": 25.0, "range_back_m": 15.0},
        "camera": {"gimbal_enabled": True},
    },
    # nhu accept_gimbal_r25, muc tieu la may bay trainer canh tren (so do nguoi dung: sai 2.16, than 1.50, cao ~0.65)
    "accept_plane_r25": {
        "guidance": {"range_set_m": 25.0, "range_back_m": 15.0},
        "camera": {"gimbal_enabled": True},
        "target_shape": {"span_m": 2.16, "length_m": 1.50, "height_m": 0.65},
    },
}
# giu 15 m (nguoi dung chot), nguong thap nhat 6-8 m: accept_plane_r25 + guidance moi + nguong cham theo ho so
PROFILES["accept_plane_r15"] = json.loads(json.dumps(PROFILES["accept_plane_r25"]))
PROFILES["accept_plane_r15"]["guidance"].update({"range_set_m": 15.0, "range_back_m": 10.0, "range_min_m": 8.0})
PROFILES["accept_plane_r15"]["acceptance"] = {"hard_floor_m": 6.0, "dive_range_min_m": 6.0}
# nguon phat hien mo phong 'realdet': accept_plane_r15 + camera Wide tuong minh + p_detect theo co px va mat theo cum.
# Cac so trong "synthetic" la GIA DINH (chua co duong recall that), de tao doan COAST that trong mo phong.
PROFILES["realdet"] = json.loads(json.dumps(PROFILES["accept_plane_r15"]))
PROFILES["realdet"]["camera"].update({"fx": 933.0, "fy": 933.0, "width": 2304, "height": 1296})
PROFILES["realdet"]["synthetic"] = {
    "realdet_enabled": True,
    "p_detect_px": [[6.0, 0.05], [12.0, 0.30], [20.0, 0.70], [40.0, 0.95]],
    "burst_start_p": 0.01,
    "burst_len_mean_frames": 15.0,
}
# tim lai muc tieu (design-search.md S-5): giu 15 m, khop kieu MOI gimbal.enabled (khong camera.gimbal_enabled), camera Wide
# tuong minh; dung tu simtools/configs/plane_r15_gimbal_e12_wide.json (them elev_ramp + goc nang -12) + search + san luc mu.
PROFILES["search_plane_r15"] = {
    "guidance": {"range_set_m": 15.0, "range_back_m": 10.0, "range_min_m": 8.0, "elev_ramp_enabled": True,
                 "target_elev_ref_deg": -12.0, "blind_floor_m": 0.0, "blind_v_cap_mps": 0.0},
    "target_shape": {"span_m": 2.16, "length_m": 1.5, "height_m": 0.65},
    "acceptance": {"hard_floor_m": 6.0, "dive_range_min_m": 6.0},
    "gimbal": {"enabled": True},
    "camera": {"fx": 933.0, "fy": 933.0, "width": 2304, "height": 1296},
    "search": {"enabled": True},
}


def profile_dict(name: str) -> Dict[str, Any]:
    """Ban sao dict cau hinh cua ho so co ten (hop le cho load_config qua file JSON)."""
    if name not in PROFILES:
        raise ValueError("ho so la: %s (co: %s)" % (name, ", ".join(sorted(PROFILES))))
    return json.loads(json.dumps(PROFILES[name]))


def load_profile(name: str) -> AppConfig:
    """AppConfig tu ho so co ten."""
    cfg = AppConfig()
    _fill(cfg, profile_dict(name), "config")
    cfg.__post_init__()
    validate(cfg)
    return cfg


def load_config(path: Optional[str] = None) -> AppConfig:
    """Nap AppConfig; path None -> mac dinh. Duoi .toml hoac .json."""
    cfg = AppConfig()
    if path:
        if path.lower().endswith(".json"):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            try:
                import tomllib  # Python >= 3.11
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("can Python >= 3.11 de doc TOML (hoac dung file .json)") from exc
            with open(path, "rb") as f:
                data = tomllib.load(f)
        _fill(cfg, data, "config")
    cfg.__post_init__()
    validate(cfg)
    return cfg
