"""Ho so cau hinh co ten (config.PROFILES) va bang kha thi theo toc do (simtools/feasibility_table.py)."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from dtrack.config import AppConfig, load_profile, profile_dict  # noqa: E402
from simtools import feasibility_table as ft  # noqa: E402


def test_profile_accept_values_and_defaults_untouched():
    c = load_profile("accept_gimbal_r25")
    assert c.guidance.range_set_m == 25.0
    assert c.camera.gimbal_enabled is True
    assert c.guidance.elev_accel_comp == 0.0          # khop gat -> khong bu pitch hai lan
    base = AppConfig()                                 # mac dinh cu giu nguyen
    assert base.guidance.range_set_m == 15.0 and base.camera.gimbal_enabled is False
    assert base.guidance.elev_accel_comp == 1.0
    assert c.guidance.a_max_mps2 == base.guidance.a_max_mps2


def test_profile_dict_is_copy_and_unknown_rejected():
    d = profile_dict("accept_gimbal_r25")
    d["guidance"]["range_set_m"] = 1.0
    assert profile_dict("accept_gimbal_r25")["guidance"]["range_set_m"] == 25.0
    with pytest.raises(ValueError):
        profile_dict("khong_co")


def test_feasibility_by_hand_10ms_a8_no_sigma():
    # 10*0.35 + 100/(2*4.1) - 100/(2*8) + 8 = 3.5 + 12.1951 - 6.25 + 8 = 17.4451
    assert ft.d_safe(10, 8.0, 0.0, ft.f_px(6)) == pytest.approx(17.445, abs=1e-3)
    # muc tieu dung tuc thi: 3.5 + 12.1951 + 8 = 23.6951
    assert ft.d_safe(10, None, 0.0, ft.f_px(6)) == pytest.approx(23.695, abs=1e-3)


def test_feasibility_sigma_fixed_point_and_pixels():
    f = ft.f_px(6)
    d = ft.d_safe(10, 8.0, 0.39, f)
    assert d == pytest.approx(ft.a_term(10, 8.0) + 2 * ft.sigma_r(d, 0.39, f), abs=1e-6)   # nghiem dung phuong trinh
    assert f == pytest.approx(1739.13, abs=0.01)
    assert ft.width_px(25.0, f) == pytest.approx(20.87, abs=0.01)                          # 1739.13*0.3/25
    assert ft.reach_m(6) == pytest.approx(26.09, abs=0.01)
    h, v = ft.fov_deg(6)
    # atan(1456*3.45e-3/2/6)=atan(0.41860)=22.7 do -> 45.4 ; atan(1088*3.45e-3/2/6)=atan(0.31280)=17.4 do -> 34.8
    assert h == pytest.approx(45.4, abs=0.2) and v == pytest.approx(34.8, abs=0.2)
    assert ft.d_safe(111, 8.0, 1.0, f) is None                                             # vo nghiem o 6 mm, sigma 1 px


def test_vmax_consistent_with_reach():
    vm = ft.vmax_for_lens(6, 8.0, 0.39)
    assert ft.d_safe(vm, 8.0, 0.39, ft.f_px(6)) == pytest.approx(ft.reach_m(6), abs=0.05)
    assert math.isfinite(vm) and vm > 10
