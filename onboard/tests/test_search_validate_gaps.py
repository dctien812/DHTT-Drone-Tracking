"""PHA DO: lo hong validate() cua khoi tim lai (T-cfg), kiem bang nap JSON qua load_config.

Tu choi (ValueError):
- guidance.blind_floor_m >= guidance.range_set_m;
(luat "search.enabled True thi blind_floor_m > 0" da BI BO theo quyet dinh chu du an)
- search.enabled True ma guidance.blind_mem_max_s < supervisor.coast_follow_s;
- guidance.blind_back_margin_m > guidance.range_set_m (gioi han tren DE XUAT, xem bao cao);
- khoa bat/tat khong phai bool that (chuoi "false", so 1, null...) cho search.enabled, gimbal.enabled,
  synthetic.realdet_enabled khi nap tu JSON.
Ca bao ve: moi ho so co ten va moi simtools/configs/*.json van nap duoc; gia tri hop le o bien van nhan.
"""
import copy
import glob
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "simtools", "configs")


def base(name="search_plane_r15"):
    from dtrack.config import profile_dict
    return profile_dict(name)


def with_(d, section, key, value):
    d = copy.deepcopy(d)
    d.setdefault(section, {})[key] = value
    return d


def load(tmp_path, d):
    from dtrack.config import load_config
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    return load_config(str(p))


# ---------------- ca bao ve ----------------
def test_guard_base_search_profile_loads(tmp_path):
    cfg = load(tmp_path, base())
    assert cfg.search.enabled is True and cfg.guidance.blind_floor_m == 0.0 and cfg.guidance.blind_v_cap_mps == 0.0


def test_guard_all_named_profiles_load():
    from dtrack.config import PROFILES, load_profile
    for name in PROFILES:
        load_profile(name)


@pytest.mark.parametrize("path", sorted(glob.glob(os.path.join(CONFIG_DIR, "*.json"))), ids=os.path.basename)
def test_guard_simtools_config_files_load(path):
    from dtrack.config import load_config
    load_config(path)


def test_guard_blind_floor_just_below_range_set_loads(tmp_path):
    load(tmp_path, with_(base(), "guidance", "blind_floor_m", 14.0))


def test_guard_mem_equal_coast_follow_loads(tmp_path):
    load(tmp_path, with_(base(), "guidance", "blind_mem_max_s", 4.0))


def test_guard_search_disabled_allows_floor_zero_and_short_memory(tmp_path):
    d = base()
    d["search"] = {"enabled": False}
    d["guidance"].update({"blind_floor_m": 0.0, "blind_mem_max_s": 0.5})
    load(tmp_path, d)


def test_guard_margin_equal_range_set_loads(tmp_path):
    load(tmp_path, with_(base(), "guidance", "blind_back_margin_m", 15.0))


# ---------------- blind_floor_m ----------------
@pytest.mark.parametrize("floor", [20.0, 15.0])
def test_floor_not_below_range_set_rejected_search_on(tmp_path, floor):
    with pytest.raises(ValueError):
        load(tmp_path, with_(base(), "guidance", "blind_floor_m", floor))


def test_floor_above_range_set_rejected_search_off(tmp_path):
    d = base("accept_plane_r15")
    with pytest.raises(ValueError):
        load(tmp_path, with_(d, "guidance", "blind_floor_m", 20.0))


def test_search_enabled_with_floor_zero_is_valid(tmp_path):
    # chu du an bo luat "bat tim lai thi blind_floor_m > 0"
    cfg = load(tmp_path, with_(base(), "guidance", "blind_floor_m", 0.0))
    assert cfg.search.enabled is True and cfg.guidance.blind_floor_m == 0.0


# ---------------- blind_mem_max_s ----------------
def test_search_enabled_with_memory_shorter_than_coast_follow_rejected(tmp_path):
    with pytest.raises(ValueError):
        load(tmp_path, with_(base(), "guidance", "blind_mem_max_s", 0.5))


# ---------------- blind_back_margin_m ----------------
@pytest.mark.parametrize("margin", [100.0, 15.5])
def test_margin_above_range_set_rejected(tmp_path, margin):
    with pytest.raises(ValueError):
        load(tmp_path, with_(base(), "guidance", "blind_back_margin_m", margin))


# ---------------- khoa bool ----------------
BAD_BOOLS = ["false", "true", "", 1, 0, None, 0.0]


@pytest.mark.parametrize("v", BAD_BOOLS, ids=repr)
def test_search_enabled_non_bool_rejected(tmp_path, v):
    with pytest.raises(ValueError):
        load(tmp_path, with_(base(), "search", "enabled", v))


@pytest.mark.parametrize("v", BAD_BOOLS, ids=repr)
def test_gimbal_enabled_non_bool_rejected(tmp_path, v):
    # nen khong bat search: neu gia tri bi ep thanh False thi khong co loi 'search can gimbal' lam lac ly do
    with pytest.raises(ValueError):
        load(tmp_path, {"gimbal": {"enabled": v}})


@pytest.mark.parametrize("v", BAD_BOOLS, ids=repr)
def test_realdet_enabled_non_bool_rejected(tmp_path, v):
    with pytest.raises(ValueError):
        load(tmp_path, with_(base("realdet"), "synthetic", "realdet_enabled", v))


@pytest.mark.parametrize("section,key,name", [("gimbal", "enabled", None), ("synthetic", "realdet_enabled", "realdet")])
def test_guard_real_bools_still_accepted(tmp_path, section, key, name):
    for v in (True, False):
        d = {} if name is None else base(name)
        cfg = load(tmp_path, with_(d, section, key, v))
        assert getattr(getattr(cfg, section), key) is v


def test_guard_search_enabled_real_false_accepted(tmp_path):
    assert load(tmp_path, with_(base(), "search", "enabled", False)).search.enabled is False
