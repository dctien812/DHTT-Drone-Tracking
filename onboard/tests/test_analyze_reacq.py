"""Bo do tim lai muc tieu: reacq_metrics trong simtools/analyze_closed_loop.py (.office/design-search.md muc (g) + S-2).
PHA DO TDD. Du lieu TONG HOP dung tay: truth.csv, app_log.csv, search.csv, events.json, app_cfg.json (nhu
test_analyze_gimbal.py, tai dung make_run cua test_analyze_closed_loop).

Giao dien test khoa (kiem qua main(), vi chi dinh thiet ke khong neu kieu tra ve cua reacq_metrics):
  - app_cfg.json co search.enabled = true va (tuy chon) search.climb_m; scenario "blackout" + events.json blackout_start/end.
  - search.csv (cot SEARCH_COLUMNS): hang ngoai dot co ep_s rong; trong dot ep_s = t - t_ep0 (t_ep0 = t - ep_s);
    hang dong dot: closed = 1, run_s = do dai chuoi TRACK (>= 1.0) => dau chuoi = t - run_s; reacq_s = dau chuoi - t_ep0.
  - Dong in: "TIM LAI: dot=%d bat dau t=%.2f | <bat lai sau %.2f s | RTL sau %.2f s | chua ket thuc> |
    d3 min luc mu=%.2f m | do cao tang max=%.2f m | pha max=%d".
  - Tieu chi: "RTL o 20 +- 0.5 s" (khi co RTL; doi chieu events.json blackout_start + tre ~0.3 s tracker, S-2),
    "d3 luc mu >= 8 m", "do cao tang <= climb_m + 1" (chi khi climb_m > 0).
  - Thieu search.csv khi search.enabled -> tieu chi FAIL kem "khong do duoc", ma thoat 1.
Dai do: d3 min luc mu tinh trong [t_ep0, bat lai | RTL] (diem chim truoc/sau dot bi loai); do cao tang = max ch_alt trong dot - ch_alt luc dau dot.
Dung sai thoi gian 0.1 s (moi chu ky 0.05 s). Hand values nam trong docstring tung ca.
"""
import csv
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, ".."), HERE):
    sys.path.insert(0, p)

from test_analyze_closed_loop import COLS, T0, T_END, make_run, run  # noqa: E402

SEARCH_COLUMNS = ["t", "ep_id", "ep_s", "phase", "run_s", "closed", "climb_m", "scan_delta_deg", "yaw_cmd_deg", "r_hat"]
BS, EP0 = 1030.0, 1030.3          # blackout_start (events.json, doc lap) va dau dot theo tracker (tre 0.3 s)
STEP = 0.05


def grid(t_last):
    return [round(T0 + i * STEP, 4) for i in range(int(round((t_last - T0) / STEP)) + 1)]


def dip_fn(dips, base=25.0):
    return lambda t: next((v for a, b, v in dips if a - 1e-9 <= t <= b + 1e-9), base)


def write_search_multi(d, eps, t_last=1062.0, climb_m=0.0):
    """search.csv KIEU THAT (dtrack/search.py + app.py): ep_id = so dot da mo (0 truoc dot dau, GIU NGUYEN sau khi dong),
    ngoai dot ep_s/phase/run_s rong. eps = [(ep0, chain_start | None), ...]; dong dot (closed = 1, mot hang) o chain_start + 1.0."""
    rows = []
    for t in grid(t_last):
        row = ["%.4f" % t, 0, "", "", "", 0, 0.0, "", "", ""]
        for i, (ep0, chain_start) in enumerate(eps, start=1):
            close_t = None if chain_start is None else chain_start + 1.0
            if t < ep0 - 1e-9:
                break
            row[1] = i                                         # da mo dot i
            if close_t is not None and t > close_t + 1e-9:
                continue                                       # dot i da dong: ep_id giu nguyen, ep_s rong
            ep_s = t - ep0
            phase = 0 if ep_s <= 4.0 else (2 if (climb_m > 0 and ep_s >= 10.0) else 1)
            run_s = (t - chain_start) if (chain_start is not None and t >= chain_start - 1e-9) else 0.0
            closed = 1 if (close_t is not None and abs(t - close_t) < 1e-6) else 0
            row = ["%.4f" % t, i, "%.4f" % ep_s, phase, "%.4f" % run_s, closed, climb_m if phase == 2 else 0.0,
                   "60.0000", "0.0000", "12.0000"]
            break
        rows.append(row)
    with open(os.path.join(d, "search.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(SEARCH_COLUMNS)
        w.writerows(rows)


def write_search_csv(d, ep0=EP0, t_last=1062.0, chain_start=None, climb_m=0.0):
    write_search_multi(d, [(ep0, chain_start)], t_last, climb_m)


def write_app_log(d, ep0=EP0, chain_start=None, rtl_t=None):
    with open(os.path.join(d, "app_log.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "loop_dt", "trk_status", "range", "range_valid", "sent", "mode", "state", "rtl"])
        fired = False
        for t in grid(T_END):
            lost = t >= ep0 - 1e-9 and (chain_start is None or t < chain_start - 1e-9)
            rtl = 0
            if rtl_t is not None and not fired and t >= rtl_t - 1e-9:
                rtl, fired = 1, True
            w.writerow(["%.4f" % t, "0.05", "search" if lost else "track", "25.0", "1", "1", "GUIDED",
                        "lost" if lost else "track", rtl])


def rewrite_alt(d, alt_fn):
    p = os.path.join(d, "truth.csv")
    with open(p, newline="") as f:
        rows = list(csv.reader(f))
    i_t, i_a = rows[0].index("t"), rows[0].index("ch_alt")
    for r in rows[1:]:
        r[i_a] = "%.4f" % alt_fn(float(r[i_t]))
    with open(p, "w", newline="") as f:
        csv.writer(f).writerows(rows)


def write_cfg(d, raw):
    with open(os.path.join(d, "app_cfg.json"), "w") as f:
        json.dump(raw, f)


def truncate(d, t_last):
    """Cat truth.csv va app_log.csv o t_last (log ket thuc cung luc voi search.csv)."""
    for name in ("truth.csv", "app_log.csv"):
        p = os.path.join(d, name)
        with open(p, newline="") as f:
            rows = list(csv.reader(f))
        keep = [rows[0]] + [r for r in rows[1:] if float(r[0]) <= t_last + 1e-6]
        with open(p, "w", newline="") as f:
            csv.writer(f).writerows(keep)


def rewrite_target_speed(d, speed_fn):
    """tgt_vn = speed_fn(t), tgt_ve = 0 (de dung muc ham dat duoc trong truth)."""
    p = os.path.join(d, "truth.csv")
    with open(p, newline="") as f:
        rows = list(csv.reader(f))
    i_t, i_n, i_e = rows[0].index("t"), rows[0].index("tgt_vn"), rows[0].index("tgt_ve")
    for r in rows[1:]:
        r[i_n], r[i_e] = "%.4f" % speed_fn(float(r[i_t])), "0.0000"
    with open(p, "w", newline="") as f:
        csv.writer(f).writerows(rows)


def build(tmp, dips=(), alt_fn=lambda t: 60.0, bs=BS, be=BS + 8.0, ep0=EP0, t_last=1062.0, chain_start=None,
          rtl_t=None, climb_m=0.0, cfg="auto", with_search_csv=True, eps=None, trunc=False, ev_extra=None):
    ev_set = {"scenario": "blackout", "blackout_start": bs, "blackout_end": be, "straight": True}
    ev_set.update(ev_extra or {})
    d = make_run(tmp, d_fn=dip_fn(dips), dive=False, ev_set=ev_set)
    rewrite_alt(d, alt_fn)
    write_app_log(d, ep0, chain_start, rtl_t)
    if with_search_csv:
        if eps is None:
            write_search_csv(d, ep0, t_last, chain_start, climb_m)
        else:
            write_search_multi(d, eps, t_last, climb_m)
    if trunc:
        truncate(d, t_last)
    if cfg == "auto":
        cfg = {"search": {"enabled": True, "climb_m": climb_m}}
    if cfg is not None:
        write_cfg(d, cfg)
    return d


def crit_line(out, label):
    ls = [ln for ln in out.splitlines() if ln.startswith(("[PASS]", "[FAIL]")) and label in ln]
    assert len(ls) <= 1, ls
    return ls[0] if ls else None


def verdict_of(out, label):
    ln = crit_line(out, label)
    return None if ln is None else ln[1:5]


def tim_lai(out):
    ls = [ln for ln in out.splitlines() if ln.startswith("TIM LAI:")]
    assert len(ls) == 1, ("khong co dong 'TIM LAI:'", out)
    return ls[0]


def num(line, pat):
    m = re.search(pat, line)
    assert m, (pat, line)
    return float(m.group(1))


# ca hand: bat lai. ep0 = 1030.3, chuoi TRACK bat dau 1038.0, dong dot (closed) 1039.0 (run_s 1.0)
# d3: 4.0 truoc dot (1019.5-1020.5) va 3.0 sau bat lai (1040-1041) deu BI LOAI; trong dot min 9.0 (1035.0-1035.2)
REACQ_DIPS = ((1019.5, 1020.5, 4.0), (1035.0, 1035.2, 9.0), (1040.0, 1041.0, 3.0))


def alt_rise(rise):
    """60 m den 1031, tang deu den 60 + rise tai 1036, giu nguyen; dau dot (1030.3) = 60 -> climb_max = rise."""
    return lambda t: 60.0 + rise * min(1.0, max(0.0, (t - 1031.0) / 5.0))


def test_reacq_metrics_function_exists():
    from simtools import analyze_closed_loop as acl
    assert callable(getattr(acl, "reacq_metrics", None))


def test_reacquired_case_hand_values(tmp_path, capsys):
    """reacq_s = 1038.0 - 1030.3 = 7.7; d3_blind_min = 9.0; climb_max = 63.5 - 60.0 = 3.5 (climb_m = 3 -> gioi han 4)."""
    d = build(tmp_path, REACQ_DIPS, alt_rise(3.5), chain_start=1038.0, climb_m=3.0)
    rc, out = run(d, capsys)
    ln = tim_lai(out)
    assert num(ln, r"dot=(\d+)") == 1
    assert num(ln, r"bat dau t=([\d.]+)") == pytest.approx(1030.3, abs=0.1)
    assert num(ln, r"bat lai sau ([\d.]+) s") == pytest.approx(7.7, abs=0.1), ln
    assert "RTL sau" not in ln and "chua ket thuc" not in ln, ln
    assert num(ln, r"d3 min luc mu=([\d.]+) m") == pytest.approx(9.0, abs=0.01), ln
    assert num(ln, r"do cao tang max=([\d.]+) m") == pytest.approx(3.5, abs=0.01), ln
    assert verdict_of(out, "d3 luc mu >= 8 m") == "PASS", out
    assert verdict_of(out, "do cao tang <= climb_m + 1") == "PASS", out


# ca hand: RTL. dot mo 1030.3; RTL (rtl=1 dau tien) tai 1050.3 => rtl_s = 20.0; rtl - blackout_start = 20.3
RTL_DIPS = ((1019.5, 1020.5, 4.0), (1040.0, 1040.2, 11.0), (1051.0, 1052.0, 3.0))


def _rtl_run(tmp_path, capsys, rtl_t=1050.3, bs=BS, ep0=EP0, t_last=1052.0):
    d = build(tmp_path, RTL_DIPS, bs=bs, be=bs + 25.0, ep0=ep0, t_last=t_last, rtl_t=rtl_t)
    return run(d, capsys)


def test_rtl_case_hand_values(tmp_path, capsys):
    """rtl_s = 1050.3 - 1030.3 = 20.0; d3_blind_min = 11.0 (3.0 sau RTL bi loai); khong bat lai; climb_max = 0."""
    rc, out = _rtl_run(tmp_path, capsys)
    ln = tim_lai(out)
    assert num(ln, r"RTL sau ([\d.]+) s") == pytest.approx(20.0, abs=0.1), ln
    assert "bat lai sau" not in ln, ln
    assert num(ln, r"d3 min luc mu=([\d.]+) m") == pytest.approx(11.0, abs=0.01), ln
    assert num(ln, r"do cao tang max=([\d.]+) m") == pytest.approx(0.0, abs=0.01), ln
    assert verdict_of(out, "RTL o 20 +- 0.5 s") == "PASS", out
    assert verdict_of(out, "d3 luc mu >= 8 m") == "PASS", out


def test_rtl_too_late_by_search_clock_fails(tmp_path, capsys):
    """RTL tai 1051.3 -> rtl_s = 21.0 (lech 1.0 s > 0.5): FAIL."""
    rc, out = _rtl_run(tmp_path, capsys, rtl_t=1051.3, t_last=1053.0)
    assert num(tim_lai(out), r"RTL sau ([\d.]+) s") == pytest.approx(21.0, abs=0.1)
    assert verdict_of(out, "RTL o 20 +- 0.5 s") == "FAIL", out
    assert rc == 1


def test_rtl_checked_against_independent_blackout_start_not_only_search_clock(tmp_path, capsys):
    """S-2: dong ho search.csv tu nhat quan (rtl_s = 20.0) nhung events.json blackout_start = 1025.0 (doc lap): RTL
    tai 1050.3 la 25.3 s sau mat hinh that -> FAIL du rtl_s tu dong ho cua ma = 20.0."""
    rc, out = _rtl_run(tmp_path, capsys, bs=1025.0)
    assert num(tim_lai(out), r"RTL sau ([\d.]+) s") == pytest.approx(20.0, abs=0.1)
    assert verdict_of(out, "RTL o 20 +- 0.5 s") == "FAIL", out
    assert rc == 1


# ca hand: chua ket thuc. dot mo 1030.3, search.csv dung o 1045.0, khong RTL, khong bat lai.
def test_unfinished_case_hand_values(tmp_path, capsys):
    """d3_blind_min = 8.7 (1035.0-1035.2; tai 8.7 >= 8: PASS); climb_max = 0."""
    d = build(tmp_path, ((1035.0, 1035.2, 8.7),), t_last=1045.0)
    rc, out = run(d, capsys)
    ln = tim_lai(out)
    assert "chua ket thuc" in ln, ln
    assert "bat lai sau" not in ln and "RTL sau" not in ln, ln
    assert num(ln, r"d3 min luc mu=([\d.]+) m") == pytest.approx(8.7, abs=0.01), ln
    assert num(ln, r"do cao tang max=([\d.]+) m") == pytest.approx(0.0, abs=0.01), ln
    assert verdict_of(out, "d3 luc mu >= 8 m") == "PASS", out


# ---------------------------------------------------------------- tieu chi d3 luc mu >= 8 m
@pytest.mark.parametrize("dmin,ok", [(7.5, False), (8.0, True), (9.0, True)])
def test_d3_blind_criterion_threshold(tmp_path, capsys, dmin, ok):
    d = build(tmp_path, ((1035.0, 1035.2, dmin),), chain_start=1038.0)
    rc, out = run(d, capsys)
    assert verdict_of(out, "d3 luc mu >= 8 m") == ("PASS" if ok else "FAIL"), out
    if not ok:
        assert rc == 1


def test_d3_dip_outside_episode_is_ignored(tmp_path, capsys):
    """d3 = 2.0 CHI truoc dot (1020) va sau bat lai (1045): d3 luc mu = 25 -> tieu chi PASS."""
    d = build(tmp_path, ((1020.0, 1020.2, 2.0), (1045.0, 1045.2, 2.0)), chain_start=1038.0)
    rc, out = run(d, capsys)
    assert num(tim_lai(out), r"d3 min luc mu=([\d.]+) m") == pytest.approx(25.0, abs=0.01)
    assert verdict_of(out, "d3 luc mu >= 8 m") == "PASS", out


# ---------------------------------------------------------------- tieu chi do cao tang (chi khi climb_m > 0)
@pytest.mark.parametrize("rise,ok", [(3.5, True), (4.0, True), (5.5, False)])
def test_climb_criterion_limit_is_climb_m_plus_one(tmp_path, capsys, rise, ok):
    """climb_m = 3 -> gioi han 4.0 m."""
    d = build(tmp_path, alt_fn=alt_rise(rise), chain_start=1038.0, climb_m=3.0)
    rc, out = run(d, capsys)
    assert num(tim_lai(out), r"do cao tang max=([\d.]+) m") == pytest.approx(rise, abs=0.01)
    assert verdict_of(out, "do cao tang <= climb_m + 1") == ("PASS" if ok else "FAIL"), out


def test_climb_criterion_absent_when_climb_m_zero(tmp_path, capsys):
    d = build(tmp_path, alt_fn=alt_rise(5.5), chain_start=1038.0, climb_m=0.0)
    rc, out = run(d, capsys)
    assert num(tim_lai(out), r"do cao tang max=([\d.]+) m") == pytest.approx(5.5, abs=0.01)     # van do, khong cham
    assert crit_line(out, "do cao tang <=") is None, out


# ---------------------------------------------------------------- thieu search.csv
def test_missing_search_csv_when_enabled_fails_with_khong_do_duoc(tmp_path, capsys):
    d = build(tmp_path, chain_start=1038.0, with_search_csv=False)
    rc, out = run(d, capsys)
    fails = [ln for ln in out.splitlines() if ln.startswith("[FAIL]") and "khong do duoc" in ln]
    assert fails, out
    assert "KET QUA: FAIL" in out and rc == 1, out


# ---------------------------------------------------------------- ca bao ve: search tat -> dau ra cu
def _plain_blackout(tmp_path, cfg, stray_search_csv):
    d = build(tmp_path, chain_start=1038.0, cfg=cfg, with_search_csv=stray_search_csv, be=BS + 3.0)     # mat hinh 3 s: kich ban cu
    return d


@pytest.mark.parametrize("cfg", [None, {"search": {"enabled": False}}, {"guidance": {"range_set_m": 25.0}}])
def test_search_disabled_output_has_no_reacq_lines_and_ignores_search_csv(tmp_path, capsys, cfg):
    d1 = _plain_blackout(tmp_path / "a", cfg, stray_search_csv=False)
    rc1, out1 = run(d1, capsys)
    d2 = _plain_blackout(tmp_path / "b", cfg, stray_search_csv=True)          # search.csv lac: phai bi bo qua
    rc2, out2 = run(d2, capsys)
    assert out1 == out2 and rc1 == rc2
    for banned in ("TIM LAI", "d3 luc mu", "RTL o 20", "do cao tang <=", "THAM SO KICH BAN", "CANH BAO: kich ban mat hinh dai",
                   "ham dat"):
        assert banned not in out1, banned
    assert "mat hinh 1030.0-1033.0:" in out1                                   # dong cu cua nhanh blackout van co


# ======================================================================================================
# VONG SUA LUOT 1 (08 + truong phong Q1-Q7): xem cac quyet dinh o tung ca.
# Dong in va nhan CHOT (05 phai theo dung chuoi):
#   "THAM SO KICH BAN: event_at=%g blackout_s=%g post_s=%g blind_d3_min=%g measure_only=%d [blackout_brake=%g] [blackout_dive=1]"
#       dong DAU TIEN cua dau ra, chi khi scenario = blackout va (search.enabled hoac co co kich ban moi: blackout_dive /
#       blackout_brake / blackout_end - blackout_start > 3); khong co o ca cu. event_at/blackout_s/post_s lay tu events.json
#       (khoa cung ten; thieu thi suy: event_at = blackout_start - t_ws, blackout_s = end - start, post_s = 15).
#   "ham dat duoc = %.2f m/s2 (yeu cau %.2f)"  (khi events.json co blackout_brake; tinh tu truth: (v(t0) - v(t0+1 s)) / 1 s, t0 = t_brake_cmd,
#       v = hypot(tgt_vn, tgt_ve)); tieu chi "ham dat >= 80% yeu cau" (tru --measure-only)
#   "CANH BAO: kich ban mat hinh dai nhung search tat: khong cham tim lai"  (khong FAIL) + dong
#   "d3 min luc mu = %.2f m (search tat; [blackout_start, blackout_end + post_s])" (post_s = events.json post_s, mac dinh 15)
#   --measure-only: tieu chi khoang cach (d3 luc mu, khong bao gio < ..., ham dat) chi in "[do] <ten>: <chi tiet>", khong doi ma thoat.
# ======================================================================================================
def run_ok(d, capsys, *extra):
    try:
        return run(d, capsys, *extra)
    except SystemExit as e:
        pytest.fail("analyze_closed_loop thoat %s (co/tham so chua duoc ho tro?)" % (e.code,))


def lines_of(out, prefix):
    return [ln for ln in out.splitlines() if ln.startswith(prefix)]


# ---------------------------------------------------------------- Q1: bat lai chi tinh khi co dong closed=1 truoc/bang RTL
def test_q1_closing_row_after_rtl_counts_as_rtl_even_if_track_chain_started_before(tmp_path, capsys):
    """Dau chuoi TRACK 1050.0 < RTL 1050.3 nhung dong dong dot (1051.0) SAU RTL -> RTL (rtl_s = 20.00), tieu chi RTL duoc cham."""
    d = build(tmp_path, RTL_DIPS, be=BS + 25.0, t_last=1052.0, chain_start=1050.0, rtl_t=1050.3)
    rc, out = run_ok(d, capsys)
    ln = tim_lai(out)
    assert num(ln, r"RTL sau ([\d.]+) s") == pytest.approx(20.0, abs=0.1), ln
    assert "bat lai sau" not in ln, ln
    assert verdict_of(out, "RTL o 20 +- 0.5 s") == "PASS", out


def test_q1_closing_row_before_rtl_is_reacquired_and_time_is_chain_start(tmp_path, capsys):
    """Chuoi 1048.0, dong dot 1049.0 <= RTL 1050.3 -> bat lai, bao theo dau chuoi: 1048.0 - 1030.3 = 17.70 s."""
    d = build(tmp_path, RTL_DIPS, be=BS + 25.0, t_last=1052.0, chain_start=1048.0, rtl_t=1050.3)
    rc, out = run_ok(d, capsys)
    ln = tim_lai(out)
    assert num(ln, r"bat lai sau ([\d.]+) s") == pytest.approx(17.7, abs=0.1), ln
    assert "RTL sau" not in ln, ln


# ---------------------------------------------------------------- RTL bien (19.5 / 20.5 +- 0.05 cho an toan so thuc)
@pytest.mark.parametrize("rtl_t,ok", [(1049.7, False), (1049.85, True), (1050.75, True), (1050.9, False)])
def test_rtl_window_edges(tmp_path, capsys, rtl_t, ok):
    """rtl_s = 19.4 / 19.55 / 20.45 / 20.6 (ep0 = 1030.3; blackout_start = 1030.0 nen rtl - bs = rtl_s + 0.3)."""
    d = build(tmp_path, RTL_DIPS, be=BS + 25.0, t_last=rtl_t + 1.0, rtl_t=rtl_t)
    rc, out = run_ok(d, capsys)
    assert verdict_of(out, "RTL o 20 +- 0.5 s") == ("PASS" if ok else "FAIL"), out


# ---------------------------------------------------------------- Q2: dot con mo khi het log
def test_q2_episode_open_longer_than_20_5_s_without_rtl_or_close_fails_rtl_criterion(tmp_path, capsys):
    """Dot mo 29.2 s (log het o 1059.5), khong RTL, khong dong: FAIL 'RTL o 20 +- 0.5 s' + ma thoat 1."""
    d = build(tmp_path, t_last=1059.5, trunc=True)
    rc, out = run_ok(d, capsys)
    assert "chua ket thuc" in tim_lai(out)
    assert verdict_of(out, "RTL o 20 +- 0.5 s") == "FAIL", out
    assert rc == 1


def test_q2_episode_open_but_log_short_is_unmeasurable_fail(tmp_path, capsys):
    """Dot mo 14.7 s (log het o 1045.0): 'chua ket thuc' + FAIL 'khong do duoc'; KHONG FAIL tieu chi RTL (chua toi 20 s)."""
    d = build(tmp_path, t_last=1045.0, trunc=True)
    rc, out = run_ok(d, capsys)
    assert "chua ket thuc" in tim_lai(out)
    assert [ln for ln in out.splitlines() if ln.startswith("[FAIL]") and "khong do duoc" in ln], out
    assert verdict_of(out, "RTL o 20 +- 0.5 s") != "FAIL", out
    assert rc == 1


@pytest.mark.parametrize("t_last,rtl_fail", [(1050.75, False), (1050.85, True)])      # dot mo 20.45 s / 20.55 s (nguong 20.5)
def test_q2_threshold_20_5(tmp_path, capsys, t_last, rtl_fail):
    d = build(tmp_path, t_last=t_last, trunc=True)
    rc, out = run_ok(d, capsys)
    assert (verdict_of(out, "RTL o 20 +- 0.5 s") == "FAIL") == rtl_fail, out
    assert rc == 1


# ---------------------------------------------------------------- Q6: chon dot + search.csv kieu that (ep_id > 0, ep_s rong ngoai dot)
def test_q6_episode_already_open_at_blackout_start_is_selected(tmp_path, capsys):
    """Dot mo 1027.0 (truoc blackout_start 1030.0 hon 1 s) van dang mo luc 1030 -> chon: bat dau 1027.00, bat lai 1038.0 - 1027.0 = 11.00 s."""
    d = build(tmp_path, ((1035.0, 1035.2, 9.0),), eps=[(1027.0, 1038.0)], ep0=1027.0)
    rc, out = run_ok(d, capsys)
    ln = tim_lai(out)
    assert num(ln, r"dot=(\d+)") == 1
    assert num(ln, r"bat dau t=([\d.]+)") == pytest.approx(1027.0, abs=0.1), ln
    assert num(ln, r"bat lai sau ([\d.]+) s") == pytest.approx(11.0, abs=0.1), ln


def test_q6_episode_closed_before_blackout_start_is_skipped_real_style_csv(tmp_path, capsys):
    """Dot 1 mo 1010.0 dong 1012.0 (truoc blackout_start): bo. Dot 2 mo 1033.0 (dau tien sau do), chuoi 1040.0 -> 'dot=2',
    bat lai sau 7.00 s, d3 min = 9.0 (diem 3.0 o 1011.2 thuoc dot 1 nen bi loai). ep_id giu = 1 voi ep_s rong giua hai dot."""
    d = build(tmp_path, ((1011.2, 1011.4, 3.0), (1036.0, 1036.2, 9.0)), eps=[(1010.0, 1011.0), (1033.0, 1040.0)], ep0=1033.0)
    rc, out = run_ok(d, capsys)
    ln = tim_lai(out)
    assert num(ln, r"dot=(\d+)") == 2, ln
    assert num(ln, r"bat dau t=([\d.]+)") == pytest.approx(1033.0, abs=0.1), ln
    assert num(ln, r"bat lai sau ([\d.]+) s") == pytest.approx(7.0, abs=0.1), ln
    assert num(ln, r"d3 min luc mu=([\d.]+) m") == pytest.approx(9.0, abs=0.01), ln


def test_q6_second_episode_after_reacquire_is_not_scored(tmp_path, capsys):
    """Hai dot trong mot chuyen: dot 1 (1030.3, bat lai 1038.0) cham; dot 2 mo 1045.0 bo qua (d3 = 2.0 o 1047 khong tinh)."""
    d = build(tmp_path, ((1034.0, 1034.2, 10.0), (1047.0, 1047.2, 2.0)), eps=[(1030.3, 1038.0), (1045.0, None)])
    rc, out = run_ok(d, capsys)
    ln = tim_lai(out)
    assert num(ln, r"dot=(\d+)") == 1, ln
    assert num(ln, r"bat lai sau ([\d.]+) s") == pytest.approx(7.7, abs=0.1), ln
    assert num(ln, r"d3 min luc mu=([\d.]+) m") == pytest.approx(10.0, abs=0.01), ln
    assert verdict_of(out, "d3 luc mu >= 8 m") == "PASS", out


# ---------------------------------------------------------------- --blind-d3-min
def test_blind_d3_min_option_changes_label_and_threshold(tmp_path, capsys):
    """d3 min luc mu = 6.5: nguong mac dinh 8 -> FAIL; --blind-d3-min 6 -> nhan 'd3 luc mu >= 6 m' PASS."""
    d = build(tmp_path, ((1035.0, 1035.2, 6.5),), chain_start=1038.0)
    _, out8 = run_ok(d, capsys)
    assert verdict_of(out8, "d3 luc mu >= 8 m") == "FAIL", out8
    _, out6 = run_ok(d, capsys, "--blind-d3-min", "6")
    assert verdict_of(out6, "d3 luc mu >= 6 m") == "PASS", out6
    assert crit_line(out6, "d3 luc mu >= 8 m") is None


# ---------------------------------------------------------------- Q3: muc ham dat duoc
def brake_build(tmp_path, req, ach, **kw):
    d = build(tmp_path, chain_start=1038.0, ev_extra={"blackout_brake": req, "t_brake_cmd": 1030.0}, **kw)
    rewrite_target_speed(d, lambda t: 10.0 if t < 1030.0 else max(0.0, 10.0 - ach * (t - 1030.0)))
    return d


def achieved(out):
    ls = [ln for ln in out.splitlines() if "ham dat duoc" in ln]
    assert len(ls) == 1, ("khong co dong 'ham dat duoc'", out)
    m = re.search(r"ham dat duoc = ([\d.]+) m/s2 \(yeu cau ([\d.]+)\)", ls[0])
    assert m, ls[0]
    return float(m.group(1)), float(m.group(2))


@pytest.mark.parametrize("req,ach,ok", [(3.0, 3.0, True), (3.0, 2.5, True), (3.0, 2.3, False), (3.0, 1.5, False)])
def test_q3_achieved_decel_reported_and_scored_at_80_percent(tmp_path, capsys, req, ach, ok):
    """Giam toc TB 1 s sau t_brake_cmd = ach (tinh tay: (10 - (10 - ach)) / 1 s); nguong 0.8 * req = 2.4."""
    rc, out = run_ok(brake_build(tmp_path, req, ach), capsys)
    x, y = achieved(out)
    assert x == pytest.approx(ach, abs=0.02) and y == pytest.approx(req, abs=1e-6)
    assert verdict_of(out, "ham dat >= 80% yeu cau") == ("PASS" if ok else "FAIL"), out
    if not ok:
        assert rc == 1


@pytest.mark.parametrize("req,ach", [(3.0, 1.5), (8.0, 4.0)])
def test_q3_measure_only_prints_decel_but_does_not_fail(tmp_path, capsys, req, ach):
    rc, out = run_ok(brake_build(tmp_path, req, ach), capsys, "--measure-only")
    x, _ = achieved(out)
    assert x == pytest.approx(ach, abs=0.02)
    assert not [ln for ln in out.splitlines() if ln.startswith("[FAIL]") and "ham dat" in ln], out


def test_blackout_brake_and_dive_skip_old_dive_and_final_scoring(tmp_path, capsys):
    d = brake_build(tmp_path / "brake", 3.0, 3.0)
    _, out = run_ok(d, capsys, "--score-final")
    assert "giam toc cuoi: d3 min" not in out and "pha cam: d3 min" not in out, out
    dv = build(tmp_path / "dive", chain_start=1038.0,
               ev_extra={"blackout_dive": True, "t_dive_cmd": 1030.0, "dive_deg": 25.0, "dive_drop_m": 40.0})
    _, out2 = run_ok(dv, capsys)
    assert "pha cam: d3 min" not in out2, out2
    ctl = make_run(tmp_path / "ctl")                                       # doi chung: ca cam xuong kieu cu van cham pha cam
    _, out3 = run_ok(ctl, capsys)
    assert "pha cam: d3 min" in out3, out3


# ---------------------------------------------------------------- Q4: --measure-only cho khoang cach
def test_q4_measure_only_turns_distance_criteria_into_do_lines(tmp_path, capsys):
    """d3 = 5.0 luc mu (< 8): khong co co -> FAIL 'd3 luc mu' va 'khong bao gio <' + ma thoat 1;
    co --measure-only: hai dong '[do]' chi in so, khong [FAIL], ma thoat 0."""
    d = build(tmp_path, ((1035.0, 1035.2, 5.0),), chain_start=1038.0)
    rc0, out0 = run_ok(d, capsys)
    assert verdict_of(out0, "d3 luc mu >= 8 m") == "FAIL" and verdict_of(out0, "khong bao gio <") == "FAIL", out0
    assert rc0 == 1
    rc, out = run_ok(d, capsys, "--measure-only")
    do_lines = lines_of(out, "[do]")
    assert any("d3 luc mu" in ln and "5.00" in ln for ln in do_lines), out
    assert any("khong bao gio <" in ln for ln in do_lines), out
    assert not lines_of(out, "[FAIL]"), out
    assert rc == 0 and "KET QUA: PASS" in out, out


def test_q4_measure_only_still_scores_infrastructure_criteria(tmp_path, capsys):
    d = build(tmp_path, chain_start=1038.0)
    rc, out = run_ok(d, capsys, "--measure-only", "--helper-rc", "3")
    assert verdict_of(out, "helper thoat code 0") == "FAIL", out
    assert rc == 1


# ---------------------------------------------------------------- Q5: search tat + co kich ban moi
WARN = "CANH BAO: kich ban mat hinh dai nhung search tat: khong cham tim lai"
BLIND_DIPS = ((1020.0, 1020.2, 3.0), (1048.0, 1048.2, 4.0), (1058.0, 1058.2, 2.0))   # truoc bs (loai), trong bs..be+15 (4.0), sau (loai)


@pytest.mark.parametrize("ev_extra", [
    {"post_s": 15.0},                                                                       # chi do blackout_end - blackout_start = 8 > 3
    {"post_s": 15.0, "blackout_brake": 3.0, "t_brake_cmd": 1030.0},
    {"post_s": 15.0, "blackout_dive": True, "t_dive_cmd": 1030.0, "dive_deg": 25.0, "dive_drop_m": 40.0},
], ids=["blackout_8s", "brake", "dive"])
def test_q5_search_off_with_new_scenario_warns_and_still_prints_blind_distance(tmp_path, capsys, ev_extra):
    d = build(tmp_path, BLIND_DIPS, cfg=None, with_search_csv=False, ev_extra=ev_extra)
    rc, out = run_ok(d, capsys)
    assert WARN in out.splitlines(), out
    assert not [ln for ln in out.splitlines() if ln.startswith("[FAIL]") and ("tim lai" in ln.lower() or "CANH BAO" in ln)], out
    ls = [ln for ln in out.splitlines() if "d3 min luc mu =" in ln]
    assert len(ls) == 1, out
    assert num(ls[0], r"d3 min luc mu = ([\d.]+) m") == pytest.approx(4.0, abs=0.01), ls[0]
    assert "TIM LAI" not in out


def test_q5_plain_3s_blackout_with_search_off_has_no_warning(tmp_path, capsys):
    d = build(tmp_path, cfg=None, with_search_csv=False, be=BS + 3.0)
    _, out = run_ok(d, capsys)
    assert WARN not in out and "d3 min luc mu =" not in out, out


# ---------------------------------------------------------------- Q7: dong tham so kich ban o dau ket qua
def _params(line):
    assert line.startswith("THAM SO KICH BAN:"), line
    return dict(tok.split("=", 1) for tok in line.split(":", 1)[1].split())


def test_q7_scenario_parameter_line_first_with_values(tmp_path, capsys):
    ev = {"event_at": 25.0, "blackout_s": 8.0, "post_s": 15.0, "blackout_brake": 3.0, "t_brake_cmd": 1030.0}
    d = build(tmp_path, chain_start=1038.0, ev_extra=ev)
    rewrite_target_speed(d, lambda t: 10.0 if t < 1030.0 else max(0.0, 10.0 - 3.0 * (t - 1030.0)))
    _, out = run_ok(d, capsys, "--blind-d3-min", "6", "--measure-only")
    first = out.splitlines()[0]
    assert first.startswith("THAM SO KICH BAN:"), first
    p = _params(first)
    assert {k: float(v) for k, v in p.items()} == {"event_at": 25.0, "blackout_s": 8.0, "post_s": 15.0, "blind_d3_min": 6.0,
                                                   "measure_only": 1.0, "blackout_brake": 3.0}, first


def test_q7_defaults_and_dive_flag(tmp_path, capsys):
    ev = {"event_at": 25.0, "blackout_s": 8.0, "post_s": 15.0, "blackout_dive": True, "t_dive_cmd": 1030.0, "dive_deg": 25.0,
          "dive_drop_m": 40.0}
    d = build(tmp_path, chain_start=1038.0, ev_extra=ev)
    _, out = run_ok(d, capsys)
    p = _params(out.splitlines()[0])
    assert float(p["blind_d3_min"]) == 8.0 and float(p["measure_only"]) == 0.0 and float(p["blackout_dive"]) == 1.0, p
    assert "blackout_brake" not in p, p


def test_q7_no_parameter_line_for_plain_old_blackout(tmp_path, capsys):
    d = build(tmp_path, cfg=None, with_search_csv=False, be=BS + 3.0)
    _, out = run_ok(d, capsys)
    assert "THAM SO KICH BAN" not in out, out

def test_rtl_search_clock_checked_independently_of_blackout_anchor(tmp_path, capsys):
    """blackout_start = 1029.4 (rtl - bs = 20.3: moc doc lap dung) nhung dong ho search.csv: rtl_s = 19.4 -> van FAIL."""
    d = build(tmp_path, RTL_DIPS, bs=1029.4, be=1029.4 + 25.0, t_last=1050.7, rtl_t=1049.7)
    rc, out = run_ok(d, capsys)
    assert num(tim_lai(out), r"RTL sau ([\d.]+) s") == pytest.approx(19.4, abs=0.1)
    assert verdict_of(out, "RTL o 20 +- 0.5 s") == "FAIL", out

# ---------------------------------------------------------------- Q3 vong 2: ham dat duoc = MAX do doc TB 1 s truot trong [t0, t0 + 2.5 s]
T0B = 1030.0


def v_delayed(a, delay=0.3, ramp=0.2, v0=10.0):
    """v0 den T0B + delay; roi gia toc tang tuyen tinh 0 -> a trong `ramp` s; roi hang a toi khi dung."""
    def f(t):
        tau = t - T0B - delay
        if tau <= 0:
            return v0
        d = a * tau * tau / (2.0 * ramp) if tau <= ramp else a * ramp / 2.0 + a * (tau - ramp)
        return max(0.0, v0 - d)
    return f


def delayed_build(tmp_path, req, fn, drop=None):
    d = build(tmp_path, chain_start=1038.0, ev_extra={"blackout_brake": req, "t_brake_cmd": T0B})
    rewrite_target_speed(d, fn)
    if drop:
        p = os.path.join(d, "truth.csv")
        with open(p, newline="") as f:
            rows = list(csv.reader(f))
        keep = [rows[0]] + [r for r in rows[1:] if not (drop[0] < float(r[0]) < drop[1])]
        with open(p, "w", newline="") as f:
            csv.writer(f).writerows(keep)
    return d


def test_q3r2_delayed_ramped_brake_3_is_measured_as_3(tmp_path, capsys):
    """tre 0.3 s + tang dan 0.2 s roi 3.0 m/s^2: cua so 1 s truot tot nhat = 3.00 (cua so co dinh 1 s dau chi ~1.9)."""
    rc, out = run_ok(delayed_build(tmp_path, 3.0, v_delayed(3.0)), capsys)
    x, _ = achieved(out)
    assert 2.9 <= x <= 3.05, x
    assert verdict_of(out, "ham dat >= 80% yeu cau") == "PASS", out


def test_q3r2_delayed_real_decel_1_5_for_request_3_still_fails(tmp_path, capsys):
    rc, out = run_ok(delayed_build(tmp_path, 3.0, v_delayed(1.5)), capsys)
    x, _ = achieved(out)
    assert 1.4 <= x <= 1.55, x
    assert verdict_of(out, "ham dat >= 80% yeu cau") == "FAIL", out
    assert rc == 1


def test_q3r2_hard_brake_8_stopping_after_1_25_s_with_delay(tmp_path, capsys):
    rc, out = run_ok(delayed_build(tmp_path, 8.0, v_delayed(8.0, ramp=1e-6)), capsys, "--measure-only")
    x, _ = achieved(out)
    assert x >= 7.2, x


def test_q3r2_no_braking_measures_zero_and_fails_unless_measure_only(tmp_path, capsys):
    d = delayed_build(tmp_path, 3.0, lambda t: 10.0)
    rc, out = run_ok(d, capsys)
    x, _ = achieved(out)
    assert x == pytest.approx(0.0, abs=0.05), x
    assert verdict_of(out, "ham dat >= 80% yeu cau") == "FAIL" and rc == 1, out
    _, out2 = run_ok(d, capsys, "--measure-only")
    assert not [ln for ln in out2.splitlines() if ln.startswith("[FAIL]") and "ham dat" in ln], out2


def test_q3r2_gap_in_truth_inside_window_still_gives_a_number(tmp_path, capsys):
    """Thieu mau truth trong (t0 + 0.8, t0 + 1.3): khong loi, van in so hop ly (2.8-3.1)."""
    rc, out = run_ok(delayed_build(tmp_path, 3.0, v_delayed(3.0), drop=(T0B + 0.8, T0B + 1.3)), capsys)
    x, _ = achieved(out)
    assert 2.8 <= x <= 3.1, x