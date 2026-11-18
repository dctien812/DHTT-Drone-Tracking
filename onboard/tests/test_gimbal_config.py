"""Buoc 3 cua thiet ke khop gat: truong cau hinh moi trong dtrack/config.py - TEST VIET TRUOC (pha do).

San pham can lam: GimbalConfig + AppConfig.gimbal; GuidanceConfig.elev_ramp_enabled/elev_ramp_dps;
AppConfig.__post_init__ xu ly gimbal.enabled; validate() kiem tra cac rang buoc moi.

Khong gia dinh danh sach PROFILES hay tap truong cua AppConfig co dinh.
Cach hieu da chon: cac rang buoc gimbal/ramp cua validate() ap dung bat ke enabled; test dat enabled=True
(va elev_ramp_enabled=True) o cac ca sai de cach hieu nao cung cho cung ket qua.
"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import dtrack.config as C  # noqa: E402
from dtrack.config import AppConfig, load_config, load_profile, validate  # noqa: E402


def _write(tmp_path, data, name="c.json"):
    p = tmp_path / name
    p.write_text(json.dumps(data))
    return str(p)


def _enabled(**over):
    """AppConfig hop le voi khop chu dong bat, roi ghi de truong gimbal."""
    cfg = AppConfig()
    cfg.gimbal.enabled = True
    cfg.__post_init__()
    for k, v in over.items():
        setattr(cfg.gimbal, k, v)
    return cfg


# ---------------------------------------------------------------- mac dinh
def test_gimbal_config_defaults():
    g = AppConfig().gimbal
    assert isinstance(g, C.GimbalConfig)
    assert g.enabled is False and g.frozen is False
    # dac ta doi dai khop: gioi han tren 90 -> 110 do; init van 90 (cat canh camera nhin ngang)
    assert (g.delta_min_deg, g.delta_max_deg, g.delta_init_deg) == (10, 110, 90)
    assert g.hold_offset_deg == 0.0
    assert g.rate_dps == 300 and g.lag_s == 0.05 and g.dead_time_s == 0.02
    assert g.quant_deg == 0.1 and g.slow_factor == 1.0


def test_guidance_ramp_defaults():
    g = AppConfig().guidance
    assert g.elev_ramp_enabled is False
    assert g.elev_ramp_dps == 2.0


def test_default_behaviour_unchanged():
    cfg = AppConfig()
    assert cfg.camera.gimbal_enabled is False
    assert cfg.camera.tilt_up_deg == 15.0 and cfg.guidance.cam_tilt_up_deg == 15.0
    assert cfg.guidance.elev_accel_comp == 1.0
    assert cfg.guidance.target_elev_ref_deg == 4.0
    validate(cfg)                                   # mac dinh van hop le


def test_old_gimbal_path_still_works_and_new_flag_stays_off():
    cfg = AppConfig()
    cfg.camera.gimbal_enabled = True
    cfg.__post_init__()
    assert cfg.guidance.elev_accel_comp == 0.0
    assert cfg.camera.tilt_up_deg == 15.0           # khop cu khong dong den tilt_up
    assert cfg.gimbal.enabled is False
    validate(cfg)


def test_every_named_profile_loads_with_new_gimbal_off_unless_it_asks():
    for name in sorted(C.PROFILES):
        d = C.profile_dict(name)
        cfg = load_profile(name)
        if "gimbal" not in d or "enabled" not in d["gimbal"]:
            assert cfg.gimbal.enabled is False, name


# ---------------------------------------------------------------- __post_init__
def test_post_init_gimbal_enabled_forces_zero_tilt_and_syncs_guidance(tmp_path):
    cfg = load_config(_write(tmp_path, {"camera": {"tilt_up_deg": 20.0}, "gimbal": {"enabled": True}}))
    assert cfg.camera.tilt_up_deg == 0.0
    assert cfg.guidance.cam_tilt_up_deg == 0.0
    assert cfg.guidance.elev_accel_comp == 0.0


def test_post_init_direct_call():
    cfg = AppConfig()
    cfg.gimbal.enabled = True
    cfg.__post_init__()
    assert cfg.camera.tilt_up_deg == 0.0 and cfg.guidance.cam_tilt_up_deg == 0.0
    assert cfg.guidance.elev_accel_comp == 0.0


def test_post_init_gimbal_disabled_keeps_tilt_synced_to_camera(tmp_path):
    cfg = load_config(_write(tmp_path, {"camera": {"tilt_up_deg": 20.0}}))
    assert cfg.camera.tilt_up_deg == 20.0 and cfg.guidance.cam_tilt_up_deg == 20.0
    assert cfg.guidance.elev_accel_comp == 1.0


# ---------------------------------------------------------------- validate: cam hai co
def test_validate_rejects_both_gimbal_flags():
    cfg = _enabled()
    cfg.camera.gimbal_enabled = True
    cfg.__post_init__()
    with pytest.raises(ValueError):
        validate(cfg)


def test_load_config_rejects_both_gimbal_flags(tmp_path):
    p = _write(tmp_path, {"camera": {"gimbal_enabled": True}, "gimbal": {"enabled": True}})
    with pytest.raises(ValueError) as ei:
        load_config(p)
    assert "khoa la" not in str(ei.value)           # loi do xung dot hai co, khong phai do khoa la


def test_validate_accepts_gimbal_enabled_alone():
    validate(_enabled())


# ---------------------------------------------------------------- validate: gioi han khop
@pytest.mark.parametrize("over", [
    {"delta_min_deg": 0.0},                       # 0 < min
    {"delta_min_deg": -5.0},
    {"delta_min_deg": 110.0, "delta_init_deg": 110.0},   # min < max (max mac dinh 110; init = min de chi vi pham min < max)
    {"delta_min_deg": 95.0, "delta_max_deg": 90.0},
    {"delta_max_deg": 120.5},                     # max <= 120
    {"delta_max_deg": 135.0},
    {"delta_init_deg": 9.0},                      # min <= init
    {"delta_init_deg": 111.0},                    # init <= max (max mac dinh 110)
    {"delta_min_deg": 20.0, "delta_init_deg": 15.0},
    {"delta_max_deg": 60.0, "delta_init_deg": 80.0},
    {"rate_dps": 0.0},                            # rate > 0
    {"rate_dps": -10.0},
    {"lag_s": -0.01},                             # lag >= 0
    {"dead_time_s": -0.01},                       # dead >= 0
    {"quant_deg": -0.1},                          # quant >= 0
    {"slow_factor": 0.0},                         # slow > 0
    {"slow_factor": -1.0},
])
def test_validate_rejects_bad_gimbal_values(over):
    cfg = _enabled(**over)
    with pytest.raises(ValueError):
        validate(cfg)


@pytest.mark.parametrize("over", [
    {"lag_s": 0.0}, {"dead_time_s": 0.0}, {"quant_deg": 0.0},        # bien: deu >= 0 hop le
    {"delta_min_deg": 10.0, "delta_max_deg": 90.0, "delta_init_deg": 10.0},   # init = min
    {"delta_max_deg": 90.0, "delta_init_deg": 90.0},                          # init = max = 90
    {"delta_min_deg": 0.5, "delta_max_deg": 89.0, "delta_init_deg": 45.0},
    {"delta_max_deg": 110.0},                                                 # max = 110 (mac dinh moi), init 90
    {"delta_max_deg": 110.0, "delta_init_deg": 110.0},                        # init = max = 110
    {"delta_max_deg": 120.0},                                                 # max = 120 (bien tren cua validate)
    {"slow_factor": 3.0}, {"hold_offset_deg": -3.0}, {"hold_offset_deg": 3.0}, {"frozen": True},
])
def test_validate_accepts_boundary_gimbal_values(over):
    validate(_enabled(**over))


@pytest.mark.parametrize("v", [0.0, -1.0])
def test_validate_rejects_nonpositive_elev_ramp_dps(v):
    cfg = AppConfig()
    cfg.guidance.elev_ramp_enabled = True
    cfg.guidance.elev_ramp_dps = v
    with pytest.raises(ValueError):
        validate(cfg)


def test_validate_accepts_positive_elev_ramp(tmp_path):
    cfg = load_config(_write(tmp_path, {"guidance": {"elev_ramp_enabled": True, "elev_ramp_dps": 0.5}}))
    assert cfg.guidance.elev_ramp_dps == 0.5
    validate(cfg)


# ---------------------------------------------------------------- nap JSON / TOML
def test_json_loads_new_fields(tmp_path):
    p = _write(tmp_path, {
        "gimbal": {"enabled": True, "delta_min_deg": 20, "delta_max_deg": 85, "delta_init_deg": 60,
                   "hold_offset_deg": 2.5, "frozen": True, "rate_dps": 150, "lag_s": 0.1,
                   "dead_time_s": 0.03, "quant_deg": 0.2, "slow_factor": 2},
        "guidance": {"elev_ramp_enabled": True, "elev_ramp_dps": 1.5},
    })
    cfg = load_config(p)
    g = cfg.gimbal
    assert g.enabled is True and g.frozen is True
    assert (g.delta_min_deg, g.delta_max_deg, g.delta_init_deg) == (20.0, 85.0, 60.0)
    assert g.hold_offset_deg == 2.5 and g.rate_dps == 150.0 and g.lag_s == 0.1
    assert g.dead_time_s == 0.03 and g.quant_deg == 0.2 and g.slow_factor == 2.0
    assert isinstance(g.delta_min_deg, float) and isinstance(g.slow_factor, float)
    assert cfg.guidance.elev_ramp_enabled is True and cfg.guidance.elev_ramp_dps == 1.5


def test_json_partial_gimbal_keeps_other_defaults(tmp_path):
    cfg = load_config(_write(tmp_path, {"gimbal": {"rate_dps": 120}}))
    assert cfg.gimbal.rate_dps == 120.0
    assert cfg.gimbal.lag_s == 0.05 and cfg.gimbal.enabled is False


def test_json_unknown_gimbal_key_is_rejected(tmp_path):
    assert load_config(_write(tmp_path, {"gimbal": {"rate_dps": 100}})).gimbal.rate_dps == 100.0   # khoa dung duoc nhan
    with pytest.raises(ValueError, match="rate_dpss"):
        load_config(_write(tmp_path, {"gimbal": {"rate_dpss": 100}}, "bad.json"))


def test_json_gimbal_must_be_object(tmp_path):
    with pytest.raises(ValueError, match="bang/doi tuong"):
        load_config(_write(tmp_path, {"gimbal": 5}))


def test_toml_loads_gimbal_section(tmp_path):
    pytest.importorskip("tomllib")
    p = tmp_path / "c.toml"
    p.write_text("[gimbal]\nenabled = true\nrate_dps = 200\n[guidance]\nelev_ramp_enabled = true\n")
    cfg = load_config(str(p))
    assert cfg.gimbal.enabled is True and cfg.gimbal.rate_dps == 200.0
    assert cfg.guidance.elev_ramp_enabled is True
    assert cfg.camera.tilt_up_deg == 0.0
