"""Noi cau hinh nguon phat hien 'realdet' (AppConfig.synthetic) vao SimTruthSource qua build_source.
Khong can SITL: SimStateReader duoc thay bang ban gia."""
import json
from types import SimpleNamespace

import pytest

from dtrack.app import build_source
from dtrack.config import load_config, load_profile, profile_dict


class _FakeReader:
    def __init__(self, url, rate_hz=50.0, clock=None, connect_timeout=60.0):
        self.last = None

    def poll(self):
        pass

    def close(self):
        pass


def _args(seed=7):
    return SimpleNamespace(source="sim", sim_target="T", sim_chaser="C", sim_seed=seed, sim_blackout_file=None)


@pytest.fixture(autouse=True)
def _fake_reader(monkeypatch):
    import simtools.sim_truth_source as sts
    monkeypatch.setattr(sts, "SimStateReader", _FakeReader)


def _synth_of(src):
    return src.det.cfg


def _assert_realdet_table(sc, expected):
    assert sc.realdet_enabled is True
    assert [tuple(r) for r in sc.p_detect_px] == [tuple(r) for r in expected["p_detect_px"]]
    assert sc.burst_start_p == expected["burst_start_p"]
    assert sc.burst_len_mean_frames == expected["burst_len_mean_frames"]


def test_realdet_profile_enables_realdet_in_source_detector():
    cfg = load_profile("realdet")
    sc = _synth_of(build_source(_args(), cfg))
    _assert_realdet_table(sc, profile_dict("realdet")["synthetic"])


def test_old_profile_source_keeps_current_synthetic_values():
    cfg = load_profile("accept_plane_r15")
    sc = _synth_of(build_source(_args(seed=7), cfg))
    assert sc.realdet_enabled is False
    assert sc.p_detect_px == ()
    assert sc.burst_start_p == 0.0
    assert (sc.frame_rate_hz, sc.latency_s, sc.center_sigma_px, sc.size_sigma_px) == (30.0, 0.06, 1.5, 1.0)
    assert (sc.p_miss, sc.p_false, sc.clip_to_frame) == (0.20, 0.05, True)


def test_sim_seed_takes_effect_with_realdet_profile():
    cfg = load_profile("realdet")
    sc = _synth_of(build_source(_args(seed=4242), cfg))
    assert sc.realdet_enabled is True      # nen khong the pass chi vi nguon mac dinh
    assert sc.seed == 4242


def test_seed_override_does_not_mutate_shared_app_config_synthetic():
    cfg = load_profile("realdet")
    seed_before = cfg.synthetic.seed
    assert seed_before != 4242
    sc = _synth_of(build_source(_args(seed=4242), cfg))
    assert sc.realdet_enabled is True      # chi co y nghia khi cfg.synthetic that su duoc dung
    assert sc.seed == 4242
    assert cfg.synthetic.seed == seed_before


def test_old_profile_seed_override_does_not_mutate_app_config_synthetic():
    cfg = load_profile("accept_plane_r15")
    seed_before = cfg.synthetic.seed
    src = build_source(_args(seed=4242), cfg)
    assert _synth_of(src).seed == 4242
    assert cfg.synthetic.seed == seed_before


def test_json_round_trip_of_realdet_profile_still_enables_realdet(tmp_path):
    p = tmp_path / "realdet.json"
    p.write_text(json.dumps(profile_dict("realdet")), encoding="utf-8")
    cfg = load_config(str(p))
    sc = _synth_of(build_source(_args(), cfg))
    _assert_realdet_table(sc, profile_dict("realdet")["synthetic"])
