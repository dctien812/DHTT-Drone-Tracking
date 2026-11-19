"""Ham thuan dieu phoi thoi gian cua simtools/sim_helper.py: resolve_post_s, event_due, blackout_over, run_ended, va to hop tham
so dong lenh sai. TAT CA cac ca duoi day GHIM HANH VI HIEN CO (ham da ton tai; ky vong xanh ngay tren ma hien tai); co chung minh
bat loi bang ban sao lam hong (xem bao cao). Khong ket noi SITL: ca dong lenh chi cham loi cua argparse (thoat 2 truoc khi noi mang).
"""
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

HELPER = os.path.join(HERE, "..", "simtools", "sim_helper.py")


def fns():
    from simtools.sim_helper import blackout_over, event_due, resolve_post_s, run_ended
    return resolve_post_s, event_due, blackout_over, run_ended


# ---------------------------------------------------------------- resolve_post_s(post_s, blackout_dive, blackout_brake)
@pytest.mark.parametrize("args,expect", [
    ((None, False, None), None),          # ca cu: ket thuc kieu cu
    ((None, True, None), 15.0),           # cam xuong dung luc mat hinh: mac dinh 15 s
    ((None, False, 0.0), 15.0),           # brake = 0.0 la gia tri hop le (KHONG phai None)
    ((None, False, 3.0), 15.0),
    ((7.0, False, None), 7.0),            # nguoi dung dat thi dung
    ((7.0, True, 3.0), 7.0),
    ((0.0, True, None), 0.0),             # post_s = 0 la gia tri nguoi dung, khong bi thay bang 15
])
def test_resolve_post_s(args, expect):
    resolve_post_s = fns()[0]
    assert resolve_post_s(*args) == expect


# ---------------------------------------------------------------- event_due(now, t_ws, event_at): now - t_ws >= event_at
@pytest.mark.parametrize("now,due", [(1044.999, False), (1045.0, True), (1045.001, True), (1005.0, False)])
def test_event_due_boundary_is_inclusive(now, due):
    event_due = fns()[1]
    assert event_due(now, 1005.0, 40.0) is due


# ---------------------------------------------------------------- blackout_over(now, blackout_on, blackout_s): now - on >= s
@pytest.mark.parametrize("now,over", [(102.999, False), (103.0, True), (103.5, True), (100.0, False)])
def test_blackout_over_boundary_is_inclusive(now, over):
    blackout_over = fns()[2]
    assert blackout_over(now, 100.0, 3.0) is over


# ---------------------------------------------------------------- run_ended(now, t_ws, window, post_s, blackout_end)
@pytest.mark.parametrize("now,ended", [(1000.0 + 20.0 + 4.99, False), (1000.0 + 20.0 + 5.0, True), (1000.0 + 20.0 + 6.0, True)])
def test_run_ended_old_style_window_plus_5s(now, ended):
    run_ended = fns()[3]
    assert run_ended(now, 1000.0, 20.0, None, None) is ended
    assert run_ended(now, 1000.0, 20.0, None, 1010.0) is ended         # blackout_end khong anh huong khi post_s None


def test_run_ended_with_post_s_not_ended_while_blackout_end_unknown():
    run_ended = fns()[3]
    assert run_ended(10_000.0, 1000.0, 20.0, 15.0, None) is False


@pytest.mark.parametrize("now,ended", [(1052.999, False), (1053.0, True), (1060.0, True)])
def test_run_ended_with_post_s_is_blackout_end_plus_post(now, ended):
    run_ended = fns()[3]
    assert run_ended(now, 1000.0, 20.0, 15.0, 1038.0) is ended


def test_run_ended_with_post_s_ignores_old_window_rule():
    """Co post_s thi KHONG dung 'window + 5 s': now = t_ws + window + 5 van chua ket thuc neu chua den blackout_end + post_s."""
    run_ended = fns()[3]
    assert run_ended(1025.0, 1000.0, 20.0, 15.0, 1038.0) is False


# ---------------------------------------------------------------- to hop tham so dong lenh sai -> argparse thoat 2
def cli(*args):
    return subprocess.run([sys.executable, HELPER, "--out", os.path.join(HERE, "_khong_dung"), "--speed", "10", *args],
                          capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("args,msg", [
    (["--blackout-dive"], "--blackout-dive/--blackout-brake can --scenario blackout"),
    (["--blackout-brake", "3"], "--blackout-dive/--blackout-brake can --scenario blackout"),
    (["--post-s", "5"], "--post-s can --scenario blackout"),
    (["--scenario", "blackout", "--blackout-dive"], "--blackout-dive can --dive-deg > 0"),
    (["--scenario", "blackout", "--blackout-dive", "--dive-deg", "25", "--blackout-brake", "3"], "khong di voi --blackout-brake"),
    (["--scenario", "disengage", "--post-s", "5"], "--post-s can --scenario blackout"),
])
def test_invalid_cli_combinations_exit_2_with_message(args, msg):
    r = cli(*args)
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert msg in r.stderr, r.stderr
