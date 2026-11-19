"""Test PHA DO cho cau hinh khoi tim lai muc tieu (.office/design-search.md muc (b) + S-1, S-5).

SearchConfig (AppConfig.search), cac khoa GuidanceConfig moi, ho so search_plane_r15.
Quy uoc tu chot: moi rang buoc cua SearchConfig duoc thu khi search.enabled=True va gimbal.enabled=True
(chua quy dinh co kiem khi enabled=False hay khong: khong test).
Import ben TRONG ham.
"""
import dataclasses
import json
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

OLD_PROFILES = ["accept_gimbal_r25", "accept_plane_r25", "accept_plane_r15", "realdet"]


def app(search_kw=None, gimbal_kw=None, enabled=True, gimbal_enabled=True):
    from dtrack.config import AppConfig
    cfg = AppConfig()
    cfg.gimbal.enabled = gimbal_enabled
    for k, v in (gimbal_kw or {}).items():
        setattr(cfg.gimbal, k, v)
    for k, v in (search_kw or {}).items():
        setattr(cfg.search, k, v)
    cfg.search.enabled = enabled
    cfg.guidance.blind_floor_m = 8.0    # bat tim lai bat buoc blind_floor_m > 0
    return cfg


# ---------------- mac dinh SearchConfig ----------------
def test_search_config_defaults_match_table_b():
    from dtrack.config import SearchConfig
    c = SearchConfig()
    assert c.enabled is False
    assert c.total_s == 20.0
    assert c.reacquire_hold_s == 1.0
    assert c.climb_m == 0.0
    assert c.climb_start_s == 10.0
    assert c.climb_rate_mps == 2.0
    assert c.scan_rate_dps == 60.0
    assert c.scan_lo_deg == 10.0 and c.scan_hi_deg == 110.0
    assert c.climb_scan_lo_deg == 70.0
    assert c.yaw_amp_deg == 45.0
    assert c.yaw_rate_dps == 20.0


def test_app_config_has_search_section_default_disabled():
    from dtrack.config import AppConfig, SearchConfig
    cfg = AppConfig()
    assert isinstance(cfg.search, SearchConfig)
    assert cfg.search.enabled is False


def test_default_app_config_still_validates():
    from dtrack.config import AppConfig, validate
    validate(AppConfig())


def test_default_enabled_config_with_gimbal_validates():
    from dtrack.config import validate
    validate(app())


# ---------------- validate SearchConfig ----------------
def test_enabled_requires_gimbal_enabled():
    from dtrack.config import validate
    with pytest.raises(ValueError):
        validate(app(gimbal_enabled=False))


@pytest.mark.parametrize("skw,gkw", [
    ({"total_s": 4.5, "climb_start_s": 4.25}, None),
    ({"total_s": 300.0}, None),
    ({"reacquire_hold_s": 0.2}, None),
    ({"reacquire_hold_s": 10.0}, None),
    ({"climb_m": 5.0}, None),
    ({"climb_start_s": 4.5}, None),
    ({"climb_start_s": 19.5}, None),
    ({"climb_rate_mps": 4.0}, None),              # = guidance.climb_max_mps
    ({"scan_rate_dps": 150.0}, None),             # = 0,5 * 300 / 1
    ({"scan_rate_dps": 75.0}, {"slow_factor": 2.0}),   # = 0,5 * 300 / 2
    ({"scan_lo_deg": 10.0, "scan_hi_deg": 30.0, "climb_scan_lo_deg": 20.0}, None),   # hi - lo = 20
    ({"climb_scan_lo_deg": 10.0}, None),          # = scan_lo
    ({"climb_scan_lo_deg": 109.0}, None),
    ({"yaw_amp_deg": 0.0}, None),
    ({"yaw_amp_deg": 90.0}, None),
    ({"yaw_rate_dps": 90.0}, None),               # = guidance.yaw_rate_max_dps
])
def test_search_validate_accepts_boundary_values(skw, gkw):
    from dtrack.config import validate
    validate(app(skw, gkw))


@pytest.mark.parametrize("skw,gkw", [
    ({"total_s": 4.0}, None),                     # phai > coast_follow_s
    ({"total_s": 3.0}, None),
    ({"total_s": 300.5}, None),
    ({"total_s": float("nan")}, None),
    ({"reacquire_hold_s": 0.1}, None),
    ({"reacquire_hold_s": 10.5}, None),
    ({"reacquire_hold_s": float("nan")}, None),
    ({"climb_m": -1.0}, None),
    ({"climb_m": float("inf")}, None),
    ({"climb_m": float("nan")}, None),
    ({"climb_start_s": 4.0}, None),               # phai > coast_follow_s
    ({"climb_start_s": 20.0}, None),              # phai < total_s
    ({"climb_start_s": 25.0}, None),
    ({"climb_rate_mps": 0.0}, None),
    ({"climb_rate_mps": -1.0}, None),
    ({"climb_rate_mps": 4.5}, None),              # > guidance.climb_max_mps
    ({"scan_rate_dps": 0.0}, None),
    ({"scan_rate_dps": 150.5}, None),             # > 0,5 * rate_dps / slow_factor
    ({"scan_rate_dps": 80.0}, {"slow_factor": 2.0}),   # gioi han 75
    ({"scan_lo_deg": 5.0}, None),                 # < gimbal.delta_min
    ({"scan_hi_deg": 115.0}, None),               # > gimbal.delta_max
    ({"scan_lo_deg": 10.0, "scan_hi_deg": 29.0, "climb_scan_lo_deg": 20.0}, None),   # hi - lo < 20
    ({"climb_scan_lo_deg": 9.0}, None),           # < scan_lo
    ({"climb_scan_lo_deg": 110.0}, None),         # phai < scan_hi
    ({"climb_scan_lo_deg": 120.0}, None),
    ({"yaw_amp_deg": -1.0}, None),
    ({"yaw_amp_deg": 91.0}, None),
    ({"yaw_rate_dps": 0.0}, None),
    ({"yaw_rate_dps": 91.0}, None),               # > guidance.yaw_rate_max_dps
])
def test_search_validate_rejects(skw, gkw):
    from dtrack.config import validate
    with pytest.raises(ValueError):
        validate(app(skw, gkw))


def test_total_s_constraint_follows_supervisor_coast_follow_s():
    from dtrack.config import validate
    cfg = app({"total_s": 8.0, "climb_start_s": 7.0})
    cfg.supervisor.coast_follow_s = 8.0
    with pytest.raises(ValueError):
        validate(cfg)


# ---------------- GuidanceConfig: khoa moi ----------------
def test_guidance_blind_defaults():
    from dtrack.config import GuidanceConfig
    g = GuidanceConfig()
    assert g.blind_floor_m == 0.0
    assert g.blind_back_margin_m == 2.0
    assert g.blind_target_decel_mps2 == 3.0       # nguoi dung doi tieu chi C6 ngay 2026-11-19 (ham nhe toi 3 m/s2)
    assert g.blind_v_cap_mps == 0.0


def test_guidance_blind_valid_values_accepted():
    from dtrack.config import AppConfig, GuidanceConfig, validate
    names = {f.name for f in dataclasses.fields(GuidanceConfig)}
    assert {"blind_floor_m", "blind_back_margin_m", "blind_target_decel_mps2", "blind_v_cap_mps"} <= names
    cfg = AppConfig()
    cfg.guidance.blind_floor_m = 8.0
    cfg.guidance.blind_back_margin_m = 0.0
    cfg.guidance.blind_target_decel_mps2 = 1.5
    cfg.guidance.blind_v_cap_mps = 30.0           # = v_max_mps
    validate(cfg)


@pytest.mark.parametrize("name,val", [
    ("blind_floor_m", -0.1),
    ("blind_back_margin_m", -0.1),
    ("blind_target_decel_mps2", 0.0),
    ("blind_target_decel_mps2", -3.0),
    ("blind_v_cap_mps", 30.5),                    # phai 0 hoac <= v_max_mps
])
def test_guidance_blind_invalid_values_rejected(name, val):
    from dtrack.config import AppConfig, validate
    cfg = AppConfig()
    setattr(cfg.guidance, name, val)
    with pytest.raises(ValueError):
        validate(cfg)


# ---------------- ho so search_plane_r15 ----------------
def test_profile_search_plane_r15_exists_and_loads():
    from dtrack.config import PROFILES, load_profile
    assert "search_plane_r15" in PROFILES
    cfg = load_profile("search_plane_r15")
    assert cfg.search.enabled is True


def test_profile_uses_new_style_gimbal_not_camera_gimbal():
    from dtrack.config import profile_dict, load_profile
    d = profile_dict("search_plane_r15")
    assert d["gimbal"]["enabled"] is True
    assert "gimbal_enabled" not in d.get("camera", {})
    cfg = load_profile("search_plane_r15")
    assert cfg.gimbal.enabled is True and cfg.camera.gimbal_enabled is False


def test_profile_has_explicit_wide_camera():
    from dtrack.config import load_profile
    cam = load_profile("search_plane_r15").camera
    assert cam.fx == 933.0 and cam.fy == 933.0
    assert cam.width == 2304 and cam.height == 1296


def test_profile_blind_and_range_settings():
    from dtrack.config import load_profile
    g = load_profile("search_plane_r15").guidance
    assert g.blind_floor_m == 0.0       # chu du an chot: tat "gia dinh muc tieu ham" trong ho so tim lai
    assert g.blind_v_cap_mps == 0.0
    assert g.range_set_m == 15.0


def test_profile_keeps_plane_target_shape_of_accept_plane_r15():
    from dtrack.config import load_profile
    ts = load_profile("search_plane_r15").target_shape
    assert (ts.span_m, ts.length_m, ts.height_m) == (2.16, 1.50, 0.65)


def test_profile_round_trips_through_json_and_load_config(tmp_path):
    from dtrack.config import load_config, load_profile, profile_dict
    p = tmp_path / "search_plane_r15.json"
    p.write_text(json.dumps(profile_dict("search_plane_r15")), encoding="utf-8")
    a = load_config(str(p))
    b = load_profile("search_plane_r15")
    assert dataclasses.asdict(a) == dataclasses.asdict(b)
    assert a.search.enabled is True


def test_load_config_json_fills_search_section(tmp_path):
    from dtrack.config import load_config
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"gimbal": {"enabled": True}, "guidance": {"blind_floor_m": 8.0},
                             "search": {"enabled": True, "climb_m": 6.0, "total_s": 25.0}}), encoding="utf-8")
    cfg = load_config(str(p))
    assert cfg.search.enabled is True and cfg.search.climb_m == 6.0 and cfg.search.total_s == 25.0


@pytest.mark.parametrize("name", OLD_PROFILES)
def test_old_profiles_keep_search_disabled(name):
    from dtrack.config import load_profile
    assert load_profile(name).search.enabled is False


def test_old_profiles_still_exist():
    from dtrack.config import PROFILES
    for n in OLD_PROFILES:
        assert n in PROFILES


# ---------------- camera mac dinh chung khong doi (ca bao ve) ----------------
def test_default_camera_unchanged():
    from dtrack.config import CameraConfig, AppConfig
    c = CameraConfig()
    assert (c.fx, c.fy, c.width, c.height) == (1739.0, 1739.0, 1456, 1088)
    a = AppConfig().camera
    assert (a.fx, a.fy, a.width, a.height) == (1739.0, 1739.0, 1456, 1088)
    assert not math.isnan(a.tilt_up_deg)
