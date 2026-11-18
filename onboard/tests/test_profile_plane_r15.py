"""Ho so accept_plane_r15 (giu 15 m) - TEST VIET TRUOC (pha do). Doi ten bo duoi .wip khi ky su bat dau viet ma.

Giao dien ma cac test nay khoa:
  a) dtrack.config.PROFILES["accept_plane_r15"] = accept_plane_r25 tru guidance {range_set_m 15, range_back_m 10, range_min_m 8}
     va them khoa "acceptance": {"hard_floor_m": 6.0, "dive_range_min_m": 6.0}.
  b) dtrack.config.AcceptanceConfig(hard_floor_m=8.0, dive_range_min_m=12.5); AppConfig.acceptance (phan cua ho so, ghi vao
     app_cfg.json qua profile_dict). Ho so cu KHONG co khoa acceptance. validate(): moi gia tri phai math.isfinite(v) and v > 0
     (tu choi 0, am, NaN, inf) va hard_floor_m <= dive_range_min_m. KHONG dong validate dive_range_min_m <= range_min_m.
  c) simtools/analyze_closed_loop.py chi doc JSON THUA app_cfg.json["acceptance"], tung khoa rieng:
       hard_floor_m    -> tieu chi "khong bao gio < X m" (thay literal 8.0 va nhan); thieu khoa -> 8.0
       dive_range_min_m-> can duoi pha cam VA pha giam toc cuoi ("giam toc cuoi: d3 min") = bien rmin; thieu khoa ->
                          guidance.range_min_m cua app_cfg.json, khong co nua -> 12.5 (duong cu, cfg_guidance)
     --range-min tren dong lenh thang acceptance.dive_range_min_m. Can tren 40 m (--dmax) giu nguyen.
"""
import dataclasses
import json
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, ".."), os.getcwd(), os.path.join(os.getcwd(), "tests"), HERE):
    sys.path.insert(0, p)

import dtrack.config as C  # noqa: E402
from dtrack.config import AppConfig, load_config, load_profile  # noqa: E402
from simtools import analyze_closed_loop as acl  # noqa: E402
from test_analyze_closed_loop import make_run, run, tri, verdict  # noqa: E402

NEW = "accept_plane_r15"
OLD = ("accept_plane_r25", "accept_gimbal_r25")
R15_GUIDANCE = {"range_set_m": 15.0, "range_back_m": 10.0, "range_min_m": 8.0}


# ---------- cau hinh ----------

def test_r15_profile_exists_with_new_guidance():
    cfg = load_profile(NEW)
    assert cfg.guidance.range_set_m == pytest.approx(15.0)
    assert cfg.guidance.range_back_m == pytest.approx(10.0)
    assert cfg.guidance.range_min_m == pytest.approx(8.0)


def test_r15_equals_r25_except_guidance_ranges_and_acceptance():
    a, b = dataclasses.asdict(load_profile(NEW)), dataclasses.asdict(load_profile("accept_plane_r25"))
    for key in R15_GUIDANCE:
        a["guidance"].pop(key)
        b["guidance"].pop(key)
    a.pop("acceptance", None)
    b.pop("acceptance", None)
    assert a == b
    cfg = load_profile(NEW)
    assert (cfg.target_shape.span_m, cfg.target_shape.length_m, cfg.target_shape.height_m) == (2.16, 1.50, 0.65)
    assert cfg.camera.gimbal_enabled is True


def test_r15_acceptance_thresholds_are_part_of_profile():
    cfg = load_profile(NEW)
    assert cfg.acceptance.hard_floor_m == pytest.approx(6.0)
    assert cfg.acceptance.dive_range_min_m == pytest.approx(6.0)
    assert C.profile_dict(NEW)["acceptance"] == {"hard_floor_m": 6.0, "dive_range_min_m": 6.0}


def test_r15_json_roundtrip_through_load_config(tmp_path):
    p = tmp_path / "app_cfg.json"
    p.write_text(json.dumps(C.profile_dict(NEW)))
    assert dataclasses.asdict(load_config(str(p))) == dataclasses.asdict(load_profile(NEW))


def _load_r25_with_acceptance(tmp_path, acc):
    d = C.profile_dict("accept_plane_r25")          # nen la ho so co san: loi chi co the do khoa/gia tri acceptance
    d["acceptance"] = acc
    p = tmp_path / "c.json"
    p.write_text(json.dumps(d))
    return load_config(str(p))


def test_validate_accepts_distinct_valid_acceptance(tmp_path):
    cfg = _load_r25_with_acceptance(tmp_path, {"hard_floor_m": 5.0, "dive_range_min_m": 7.5})
    assert (cfg.acceptance.hard_floor_m, cfg.acceptance.dive_range_min_m) == (5.0, 7.5)


@pytest.mark.parametrize("key", ["hard_floor_m", "dive_range_min_m"])
@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_validate_rejects_non_finite_or_non_positive_acceptance(tmp_path, key, bad):
    with pytest.raises(ValueError) as ei:
        _load_r25_with_acceptance(tmp_path, {key: bad})
    assert "khoa la" not in str(ei.value), "khoa acceptance chua duoc khai bao: %s" % ei.value


def test_validate_rejects_floor_above_dive_min(tmp_path):
    with pytest.raises(ValueError) as ei:
        _load_r25_with_acceptance(tmp_path, {"hard_floor_m": 7.0, "dive_range_min_m": 6.0})
    assert "khoa la" not in str(ei.value), "khoa acceptance chua duoc khai bao: %s" % ei.value


# ---------- ho so cu khong doi (xanh ngay) ----------

def test_old_profiles_dicts_unchanged():
    assert C.profile_dict("accept_gimbal_r25") == {
        "guidance": {"range_set_m": 25.0, "range_back_m": 15.0}, "camera": {"gimbal_enabled": True}}
    assert C.profile_dict("accept_plane_r25") == {
        "guidance": {"range_set_m": 25.0, "range_back_m": 15.0}, "camera": {"gimbal_enabled": True},
        "target_shape": {"span_m": 2.16, "length_m": 1.50, "height_m": 0.65}}


@pytest.mark.parametrize("name", OLD)
def test_old_profiles_keep_range_min_12_5(name):
    assert load_profile(name).guidance.range_min_m == pytest.approx(12.5)
    assert AppConfig().guidance.range_min_m == pytest.approx(12.5)


@pytest.mark.parametrize("name", OLD)
def test_old_profiles_keep_acceptance_defaults(name):
    cfg = load_profile(name)
    assert cfg.acceptance.hard_floor_m == pytest.approx(8.0)
    assert cfg.acceptance.dive_range_min_m == pytest.approx(12.5)
    assert "acceptance" not in C.profile_dict(name)


# ---------- bo cham ----------

def dip(depth_to):
    """d3 25 m, tut xuong depth_to tai t=1039 (trong pha cam 1035..1050)."""
    return lambda t: 25.0 - (25.0 - depth_to) * tri(t, 1036.0, 1039.0, 1042.0)


def dip_final(depth_to):
    """d3 25 m, tut xuong depth_to tai t=1054 (trong pha giam toc cuoi 1050..1062, ngoai pha cam)."""
    return lambda t: 25.0 - (25.0 - depth_to) * tri(t, 1052.0, 1054.0, 1057.0)


def write_cfg(tmp_path, profile=None, raw=None):
    """profile: ghi profile_dict; raw: ghi dict tho (JSON thua); ca hai None: khong co app_cfg.json."""
    if profile is not None:
        raw = C.profile_dict(profile)
    if raw is not None:
        (tmp_path / "app_cfg.json").write_text(json.dumps(raw))


def floor_verdict(out):
    return verdict(out, "khong bao gio <")


def dive_verdict(out):
    return verdict(out, "pha cam: d3 min")


def final_verdict(out):
    return verdict(out, "giam toc cuoi: d3 min")


def test_r15_dip_to_7_m_passes_floor_and_dive(tmp_path, capsys):
    write_cfg(tmp_path, NEW)
    rc, out = run(make_run(tmp_path, d_fn=dip(7.0)), capsys)
    assert floor_verdict(out) == "PASS", out
    assert dive_verdict(out) == "PASS", out
    assert rc == 0, out


@pytest.mark.parametrize("depth,want", [(5.8, "FAIL"), (6.2, "PASS")])
def test_r15_boundary_around_6_m(tmp_path, capsys, depth, want):
    write_cfg(tmp_path, NEW)
    rc, out = run(make_run(tmp_path, d_fn=dip(depth)), capsys)
    assert floor_verdict(out) == want, out
    assert dive_verdict(out) == want, out
    assert rc == (1 if want == "FAIL" else 0), out


def test_r15_floor_label_states_6_m(tmp_path, capsys):
    write_cfg(tmp_path, NEW)
    _, out = run(make_run(tmp_path), capsys)
    assert "khong bao gio < 6 m" in out, out


def test_r15_dive_upper_bound_still_40(tmp_path, capsys):
    write_cfg(tmp_path, NEW)
    rc, out = run(make_run(tmp_path, d_fn=lambda t: 25.0 + 27.0 * tri(t, 1044.0, 1046.0, 1049.0)), capsys)
    assert verdict(out, "trong va sau cu cam") == "FAIL", out
    assert rc == 1


def test_r15_final_deceleration_phase_uses_dive_range_min(tmp_path, capsys):
    write_cfg(tmp_path, NEW)
    rc, out = run(make_run(tmp_path, d_fn=dip_final(7.0)), capsys)
    assert final_verdict(out) == "PASS", out
    assert floor_verdict(out) == "PASS", out
    assert rc == 0, out


@pytest.mark.parametrize("prof", [None, "accept_plane_r25", "accept_gimbal_r25"])
def test_old_final_deceleration_dip_to_7_m_fails(tmp_path, capsys, prof):
    write_cfg(tmp_path, prof)
    rc, out = run(make_run(tmp_path, d_fn=dip_final(7.0)), capsys)
    assert final_verdict(out) == "FAIL", out
    assert rc == 1


def test_floor_and_dive_keys_are_not_swapped(tmp_path, capsys):
    write_cfg(tmp_path, raw={"acceptance": {"hard_floor_m": 5.0, "dive_range_min_m": 7.5}})
    rc, out = run(make_run(tmp_path, d_fn=dip(6.0)), capsys)
    assert floor_verdict(out) == "PASS", out         # 6.0 >= 5.0
    assert dive_verdict(out) == "FAIL", out          # 6.0 < 7.5
    assert "khong bao gio < 5 m" in out, out
    assert rc == 1


def test_range_min_flag_overrides_acceptance(tmp_path, capsys):
    write_cfg(tmp_path, NEW)
    rc, out = run(make_run(tmp_path, d_fn=dip(7.0)), capsys, "--range-min", "9")
    assert dive_verdict(out) == "FAIL", out
    assert floor_verdict(out) == "PASS", out
    assert "9.0" in next(ln for ln in out.splitlines() if "pha cam: d3 min" in ln)
    assert rc == 1


def test_only_dive_key_present_floor_falls_back_to_8(tmp_path, capsys):
    write_cfg(tmp_path, raw={"acceptance": {"dive_range_min_m": 9.0}})
    _, out = run(make_run(tmp_path, d_fn=dip(8.5)), capsys)
    assert floor_verdict(out) == "PASS", out         # san roi ve 8.0 (duong cu): 8.5 >= 8.0
    assert "khong bao gio < 8 m" in out, out
    assert dive_verdict(out) == "FAIL", out          # 8.5 < 9.0


def test_only_floor_key_present_dive_falls_back_to_guidance_range_min(tmp_path, capsys):
    write_cfg(tmp_path, raw={"acceptance": {"hard_floor_m": 5.0}, "guidance": {"range_min_m": 9.0}})
    _, out = run(make_run(tmp_path, d_fn=dip(8.5)), capsys)
    assert floor_verdict(out) == "PASS", out         # 8.5 >= 5.0
    assert dive_verdict(out) == "FAIL", out          # 8.5 < guidance.range_min_m 9.0
    assert "9.0" in next(ln for ln in out.splitlines() if "pha cam: d3 min" in ln)


def test_only_floor_key_present_and_no_guidance_dive_falls_back_to_12_5(tmp_path, capsys):
    write_cfg(tmp_path, raw={"acceptance": {"hard_floor_m": 5.0}})
    _, out = run(make_run(tmp_path, d_fn=dip(10.0)), capsys)
    assert floor_verdict(out) == "PASS", out
    assert dive_verdict(out) == "FAIL", out
    assert "12.5" in next(ln for ln in out.splitlines() if "pha cam: d3 min" in ln)


@pytest.mark.parametrize("prof", [None, "accept_plane_r25", "accept_gimbal_r25"])
def test_old_dip_to_7_m_fails_floor_8_and_dive_12_5(tmp_path, capsys, prof):
    write_cfg(tmp_path, prof)           # None = khong co app_cfg.json (thieu khoa -> gia tri cu)
    rc, out = run(make_run(tmp_path, d_fn=dip(7.0)), capsys)
    assert floor_verdict(out) == "FAIL", out
    assert dive_verdict(out) == "FAIL", out
    assert rc == 1


@pytest.mark.parametrize("prof", [None, "accept_plane_r25"])
def test_old_dip_to_10_m_passes_floor_but_fails_dive_12_5(tmp_path, capsys, prof):
    write_cfg(tmp_path, prof)
    _, out = run(make_run(tmp_path, d_fn=dip(10.0)), capsys)
    assert floor_verdict(out) == "PASS", out
    assert dive_verdict(out) == "FAIL", out
    assert "12.5" in next(ln for ln in out.splitlines() if "pha cam: d3 min" in ln)


def test_old_label_still_states_8_m(tmp_path, capsys):
    _, out = run(make_run(tmp_path), capsys)
    assert "khong bao gio < 8 m" in out
