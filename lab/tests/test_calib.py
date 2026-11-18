"""--calib / quy doi he so theo ti le thu nho khung."""
import json
import logging
import math

import numpy as np
import pytest

from labview.__main__ import parse
from labview.config import Config, ConfigError, apply_calib
from labview.pipeline import Pipeline
from labview.sources import Frame
from test_server import FakeDetector, FakeSource


def _calib(tmp_path, w=1280, h=720, fx=1000.0, fy=1010.0, cx=650.0, cy=355.0):
    p = tmp_path / "camera.json"
    p.write_text(json.dumps({"width": w, "height": h, "camera_matrix": [[fx, 0, cx], [0, fy, cy], [0, 0, 1]],
                             "dist_coeffs": [0.1, 0, 0, 0, 0]}))
    return str(p)


def _run(cfg, w, h):
    pipe = Pipeline(FakeSource(), FakeDetector(), cfg)
    pipe.process_frame(Frame(np.zeros((h, w, 3), np.uint8), 0.0, 0))
    return pipe


def test_calib_khung_thu_nho_ra_dung_ti_le(tmp_path):
    cfg = parse(["--source", "file:x", "--calib", _calib(tmp_path), "--max-width", "640"])
    assert (cfg.fx, cfg.fy, cfg.cx, cfg.cy, cfg.calib_size) == (1000.0, 1010.0, 650.0, 355.0, (1280, 720))
    k = _run(cfg, 1280, 720)._k                     # 1280 -> 640: ti le 0.5
    assert (k.fx, k.fy, k.cx, k.cy) == pytest.approx((500.0, 505.0, 325.0, 177.5))
    k = _run(parse(["--source", "file:x", "--calib", _calib(tmp_path)]), 1280, 720)._k   # mac dinh 960: ti le 0.75
    assert (k.fx, k.fy, k.cx, k.cy) == pytest.approx((750.0, 757.5, 487.5, 266.25))
    k = _run(parse(["--source", "file:x", "--calib", _calib(tmp_path), "--max-width", "0"]), 1280, 720)._k
    assert (k.fx, k.cx) == pytest.approx((1000.0, 650.0))       # khong thu nho: nguyen ban


def test_fx_tay_cung_tinh_tren_khung_goc(tmp_path):
    cfg = Config(fx=1000.0, cx=640.0, cy=360.0, max_width=640)
    k = _run(cfg, 1280, 720)._k
    assert (k.fx, k.fy, k.cx, k.cy) == pytest.approx((500.0, 500.0, 320.0, 180.0))
    cfg = parse(["--source", "file:x", "--calib", _calib(tmp_path), "--fx", "2000", "--max-width", "640"])
    assert cfg.fx == 2000.0 and cfg.fy == 1010.0                  # --fx tay thang file


def test_canh_bao_lech_ti_le_khung(tmp_path, caplog):
    cfg = parse(["--source", "file:x", "--calib", _calib(tmp_path), "--max-width", "0"])
    with caplog.at_level(logging.WARNING, logger="labview"):
        pipe = _run(cfg, 640, 480)                                 # 4:3 khac 16:9 luc hieu chuan
    assert any("CANH BAO: ti le khung 640x480" in e["msg"] for e in pipe.events)
    assert any(r.levelno == logging.WARNING and "ti le khung" in r.message for r in caplog.records)
    # cung ti le, khac do phan giai: van bao, va quy doi dung (640/1280 = 0.5)
    pipe = _run(cfg, 640, 360)
    assert any("khac do phan giai hieu chuan" in e["msg"] for e in pipe.events)
    assert pipe._k.fx == pytest.approx(500.0)
    # dung do phan giai: khong canh bao
    assert not any("hieu chuan" in e["msg"] for e in _run(cfg, 1280, 720).events)


def test_calib_file_hong_bao_loi(tmp_path):
    for body in ("khong phai json", json.dumps({"width": 640}), json.dumps({"width": 0, "height": 480,
                 "camera_matrix": [[1, 0, 1], [0, 1, 1], [0, 0, 1]]})):
        p = tmp_path / "bad.json"
        p.write_text(body)
        with pytest.raises(ConfigError):
            apply_calib(Config(), str(p))
    with pytest.raises(ConfigError):
        apply_calib(Config(), str(tmp_path / "khong_co.json"))
