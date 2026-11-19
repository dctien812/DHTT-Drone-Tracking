"""Pha DO (TDD): nguon phat hien mo phong 'realdet' - xac suat phat hien theo co muc tieu (px) + mat THEO CUM.

Giao dien da ghim (cac tham so la GIA DINH, chua co duong recall that):
  SyntheticConfig (dtrack/synthetic.py), them 4 khoa, mac dinh TAT:
    realdet_enabled: bool = False
    p_detect_px: tuple[(px, p), ...]   bang co bbox (px, canh w) -> xac suat phat hien, noi suy tuyen tinh,
                                       ngoai khoang thi giu gia tri bien (kieu numpy.interp)
    burst_start_p: float               xac suat moi khung (khi chua trong cum) bat dau mot cum mat, [0,1]
    burst_len_mean_frames: float       do dai cum trung binh (khung), phan phoi hinh hoc, > 0
  AppConfig.synthetic: SyntheticConfig (nhom moi trong config.py, validate() kiem nhom nay).
  Ho so PROFILES["realdet"]: dua tren accept_plane_r15 + synthetic.realdet_enabled=True + camera Wide tuong minh.

Kiem thong ke: seed co dinh => ket qua tat dinh; nguong chon theo ~5 sigma nen neu mo hinh dung thi
xac suat rot ngau nhien rat nho (xem bao cao).
"""
import copy
import dataclasses
import json
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import dtrack.config as C  # noqa: E402
from dtrack.config import AppConfig, load_config, load_profile, profile_dict, validate  # noqa: E402
from dtrack.synthetic import SyntheticConfig, SyntheticDetector  # noqa: E402
from dtrack.types import CameraModel, OwnState  # noqa: E402

OWN0 = OwnState(t=0.0, pos_ned=(0.0, 0.0, 0.0), vel_ned=(0.0, 0.0, 0.0), q_world_body=(1.0, 0.0, 0.0, 0.0))
CAM = CameraModel()
QUIET = dict(center_sigma_px=0.0, size_sigma_px=0.0, p_miss=0.0, p_false=0.0, latency_s=0.0, frame_rate_hz=30.0)
TABLE = ((10.0, 0.10), (30.0, 0.50), (60.0, 0.95))     # px -> p (gia dinh de thu)
FLAT1 = ((1.0, 1.0), (1000.0, 1.0))                    # luon phat hien: chi con mat do cum


def realdet_cfg(**kw):
    base = dict(QUIET, realdet_enabled=True, p_detect_px=TABLE, burst_start_p=0.0, burst_len_mean_frames=5.0, seed=7)
    base.update(kw)
    return SyntheticConfig(**base)


def hits(cfg, size_px=30.0, n=4000):
    """Chuoi bool 'khung i co phat hien that' khi muc tieu truoc mui, bbox rong dung size_px (khong nhieu)."""
    r = 0.5 * (CAM.fx + CAM.fy) * 0.30 / size_px
    det = SyntheticDetector(CAM, cfg)
    return [len(det.process(i / 30.0, (r, 0.0, 0.0), OWN0)) > 0 for i in range(n)]


def runs_of_false(seq):
    out, cur = [], 0
    for h in seq:
        if h:
            if cur:
                out.append(cur)
            cur = 0
        else:
            cur += 1
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------- (i) TAT = hanh vi cu
def test_disabled_by_default_stream_identical_to_old_rng_replay():
    """Ca bao ve (pass ngay). Tai lap tay thu tu rut cua _make_frame cu: moi khung 6 lan rut co dinh."""
    cfg = SyntheticConfig(seed=3, latency_s=0.0)
    det = SyntheticDetector(CAM, cfg)
    g = np.random.default_rng(3)
    n_det = 0
    for i in range(300):
        rel = (15.0 + 0.1 * i, 0.3 * math.sin(i / 7.0), 0.4 * math.cos(i / 5.0))
        got = det.process(i / 30.0, rel, OWN0)
        r_miss = g.random()
        noise = g.normal(size=4)
        conf = g.normal(cfg.true_conf_mean, cfg.true_conf_sigma)
        r_false = g.random()
        g.random(4)
        g.normal(cfg.false_conf_mean, cfg.false_conf_sigma)
        n_true = sum(1 for d in got if d.conf == pytest.approx(min(1.0, max(0.0, conf)), abs=1e-12))
        assert (n_true == 1) == (r_miss >= cfg.p_miss), "khung %d: mat/co khac chuoi RNG cu" % i
        if r_miss >= cfg.p_miss:
            size = 0.5 * (CAM.fx + CAM.fy) * 0.30 / math.sqrt(sum(c * c for c in rel))
            true_d = [d for d in got if d.conf == pytest.approx(min(1.0, max(0.0, conf)), abs=1e-12)][0]
            assert true_d.w == pytest.approx(max(1.0, size + cfg.size_sigma_px * noise[2]), rel=1e-9)
            n_det += 1
        assert (len(got) - n_true) == (1 if r_false < cfg.p_false else 0)
    assert 200 < n_det < 290


def test_realdet_flag_default_false_in_syntheticconfig():
    assert SyntheticConfig().realdet_enabled is False


def test_realdet_flag_default_false_in_appconfig():
    assert AppConfig().synthetic.realdet_enabled is False


def test_every_existing_profile_keeps_realdet_off():
    for name in C.PROFILES:
        if name == "realdet":
            continue
        assert load_profile(name).synthetic.realdet_enabled is False, name


# ---------------------------------------------------------------- (ii) xac suat theo co px
@pytest.mark.parametrize("size_px,p", [(10.0, 0.10), (20.0, 0.30), (30.0, 0.50), (45.0, 0.725), (60.0, 0.95)])
def test_detection_rate_matches_table_interpolation(size_px, p):
    n = 4000
    rate = sum(hits(realdet_cfg(), size_px, n)) / n
    tol = 5.0 * math.sqrt(p * (1.0 - p) / n)             # 5 sigma nhi thuc
    assert abs(rate - p) < tol, "co %.0f px: ti le %.4f, ky vong %.3f +- %.4f" % (size_px, rate, p, tol)


@pytest.mark.parametrize("size_px,p", [(5.0, 0.10), (100.0, 0.95)])
def test_detection_rate_clamps_outside_table(size_px, p):
    n = 4000
    rate = sum(hits(realdet_cfg(), size_px, n)) / n
    assert abs(rate - p) < 5.0 * math.sqrt(p * (1.0 - p) / n)


def test_large_target_detected_more_often_than_small():
    n = 3000
    small = sum(hits(realdet_cfg(), 12.0, n)) / n
    large = sum(hits(realdet_cfg(), 55.0, n)) / n
    assert large > small + 0.5


# ---------------------------------------------------------------- (iii) mat theo cum
L_MEAN, START_P, N_BURST = 10.0, 0.02, 40000


def burst_seq():
    return hits(realdet_cfg(p_detect_px=FLAT1, burst_start_p=START_P, burst_len_mean_frames=L_MEAN, seed=11), 30.0, N_BURST)


def test_misses_come_in_bursts_with_mean_length_matching_parameter():
    seq = burst_seq()
    runs = runs_of_false(seq)
    assert len(runs) > 300, "qua it cum mat: %d" % len(runs)      # ky vong ~ 650
    mean_len = sum(runs) / len(runs)
    # sai so chuan cua trung binh ~0.4; cong lech nho do cum lien ke dinh nhau (~+0.2)
    assert abs(mean_len - L_MEAN) < 1.5, "do dai cum trung binh %.2f, tham so %.1f" % (mean_len, L_MEAN)


def test_burst_model_has_much_longer_runs_than_independent_with_same_loss_rate():
    seq = burst_seq()
    q = 1.0 - sum(seq) / len(seq)
    assert 0.05 < q < 0.35
    indep = np.random.default_rng(5).random(len(seq)) >= q       # mo hinh doc lap cung ti le mat
    max_burst = max(runs_of_false(seq))
    max_indep = max(runs_of_false([bool(x) for x in indep]))
    assert max_burst >= 25, max_burst
    assert max_burst > 2 * max_indep, (max_burst, max_indep)


def test_miss_is_strongly_correlated_with_previous_miss():
    seq = burst_seq()
    after_miss = [not seq[i] for i in range(1, len(seq)) if not seq[i - 1]]
    q = 1.0 - sum(seq) / len(seq)
    p_cond = sum(after_miss) / len(after_miss)
    assert p_cond > 0.8 and p_cond > q + 0.5, (p_cond, q)      # cum dai 10 => ~0.9; doc lap => ~q (0.17)


def test_no_bursts_when_burst_start_p_zero():
    seq = hits(realdet_cfg(p_detect_px=FLAT1, burst_start_p=0.0), 30.0, 3000)
    assert all(seq)


# ---------------------------------------------------------------- (iv) tat dinh
def test_same_seed_same_stream_and_different_seed_differs():
    kw = dict(burst_start_p=0.05, burst_len_mean_frames=4.0)
    a = hits(realdet_cfg(seed=21, **kw), 30.0, 1500)
    b = hits(realdet_cfg(seed=21, **kw), 30.0, 1500)
    c = hits(realdet_cfg(seed=22, **kw), 30.0, 1500)
    assert a == b
    assert a != c


def test_same_seed_same_full_detections_with_noise():
    def run():
        det = SyntheticDetector(CAM, SyntheticConfig(realdet_enabled=True, p_detect_px=TABLE, burst_start_p=0.05,
                                                     burst_len_mean_frames=4.0, seed=9, latency_s=0.0))
        return [det.process(i / 30.0, (60.0, 1.0, 0.5), OWN0) for i in range(600)]
    assert run() == run()


# ---------------------------------------------------------------- (v) validate()
def _cfg_with(**kw):
    cfg = AppConfig()
    cfg.synthetic.realdet_enabled = True
    cfg.synthetic.p_detect_px = TABLE
    cfg.synthetic.burst_start_p = 0.02
    cfg.synthetic.burst_len_mean_frames = 10.0
    for k, v in kw.items():
        assert hasattr(cfg.synthetic, k), "thieu khoa synthetic.%s" % k
        setattr(cfg.synthetic, k, v)
    return cfg


def test_validate_accepts_sane_realdet_config():
    validate(_cfg_with())


@pytest.mark.parametrize("bad", [-0.1, 1.1, float("nan")])
def test_validate_rejects_burst_start_p_outside_unit_interval(bad):
    with pytest.raises(ValueError):
        validate(_cfg_with(burst_start_p=bad))


@pytest.mark.parametrize("bad", [0.0, -3.0, float("nan")])
def test_validate_rejects_nonpositive_burst_len(bad):
    with pytest.raises(ValueError):
        validate(_cfg_with(burst_len_mean_frames=bad))


@pytest.mark.parametrize("table", [
    ((10.0, -0.1), (30.0, 0.5)),
    ((10.0, 0.1), (30.0, 1.2)),
])
def test_validate_rejects_table_probability_outside_unit_interval(table):
    with pytest.raises(ValueError):
        validate(_cfg_with(p_detect_px=table))


@pytest.mark.parametrize("table", [
    ((30.0, 0.5), (10.0, 0.1)),             # px giam
    ((10.0, 0.1), (10.0, 0.5)),             # px trung
])
def test_validate_rejects_table_not_increasing_in_px(table):
    with pytest.raises(ValueError):
        validate(_cfg_with(p_detect_px=table))


def test_validate_rejects_table_probability_decreasing_with_size():
    with pytest.raises(ValueError):
        validate(_cfg_with(p_detect_px=((10.0, 0.9), (30.0, 0.2))))


def test_validate_rejects_empty_table_when_enabled():
    with pytest.raises(ValueError):
        validate(_cfg_with(p_detect_px=()))


# ---------------------------------------------------------------- (vi) ho so realdet
def test_realdet_profile_exists_and_enables_feature():
    assert "realdet" in C.PROFILES
    cfg = load_profile("realdet")
    assert cfg.synthetic.realdet_enabled is True
    assert len(cfg.synthetic.p_detect_px) >= 2
    assert cfg.synthetic.burst_start_p > 0 and cfg.synthetic.burst_len_mean_frames > 0


def test_realdet_profile_declares_wide_camera_explicitly():
    d = profile_dict("realdet")
    cam = d["camera"]
    assert (cam["fx"], cam["fy"], cam["width"], cam["height"]) == (933, 933, 2304, 1296)
    c = load_profile("realdet").camera
    assert (c.fx, c.fy, c.width, c.height) == (933.0, 933.0, 2304, 1296)


def test_realdet_profile_is_based_on_accept_plane_r15():
    base, new = load_profile("accept_plane_r15"), load_profile("realdet")
    for grp in ("guidance", "acceptance", "target_shape", "gimbal"):
        assert dataclasses.asdict(getattr(new, grp)) == dataclasses.asdict(getattr(base, grp)), grp
    assert new.camera.gimbal_enabled == base.camera.gimbal_enabled
    assert new.camera.tilt_up_deg == base.camera.tilt_up_deg


def test_realdet_profile_round_trips_through_json_file(tmp_path):
    p = tmp_path / "realdet.json"
    p.write_text(json.dumps(profile_dict("realdet")), encoding="utf-8")
    cfg = load_config(str(p))
    assert cfg.synthetic.realdet_enabled is True
    assert [tuple(x) for x in cfg.synthetic.p_detect_px] == [tuple(x) for x in load_profile("realdet").synthetic.p_detect_px]


def test_default_camera_unchanged():
    c = AppConfig().camera
    assert (c.fx, c.fy, c.width, c.height) == (1739.0, 1739.0, 1456, 1088)
    assert (CameraModel().fx, CameraModel().width, CameraModel().height) == (2319.0, 1456, 1088)


def test_accept_plane_r15_profile_untouched():
    before = copy.deepcopy(profile_dict("accept_plane_r15"))
    assert "synthetic" not in before
    assert before["acceptance"] == {"hard_floor_m": 6.0, "dive_range_min_m": 6.0}
