"""Test nguon picamera2 bang module picamera2 GIA (khong can Pi), va script hieu chuan bang anh ban co tong hop."""
import sys
import types

import cv2
import numpy as np
import pytest

from labview import sources
from labview.picam import Picamera2Source, focus_controls


class FakeCam:
    instances = []
    cameras = [{"Model": "imx708_wide"}]

    def __init__(self, num=0):
        self.num, self.calls, self.cfg_kwargs, self.frames = num, [], None, 0
        FakeCam.instances.append(self)

    @staticmethod
    def global_camera_info():
        return FakeCam.cameras

    def create_video_configuration(self, **kw):
        self.cfg_kwargs = kw
        return {"cfg": kw}

    def configure(self, cfg):
        self.calls.append("configure")

    def start(self):
        self.calls.append("start")

    def capture_array(self, name="main"):
        self.frames += 1
        img = np.zeros((4, 6, 3), np.uint8)
        img[..., 0], img[..., 1], img[..., 2] = 10, 20, 30   # kenh 0 = B, 1 = G, 2 = R (RGB888 cua picamera2)
        return img

    def stop(self):
        self.calls.append("stop")

    def close(self):
        self.calls.append("close")


@pytest.fixture
def fake_picamera2(monkeypatch):
    FakeCam.instances, FakeCam.cameras = [], [{"Model": "imx708_wide"}]
    mod = types.ModuleType("picamera2")
    mod.Picamera2 = FakeCam
    monkeypatch.setitem(sys.modules, "picamera2", mod)
    return FakeCam


def test_thieu_thu_vien_bao_loi_ro(monkeypatch):
    monkeypatch.setitem(sys.modules, "picamera2", None)   # import -> ImportError
    src = sources.make_source("picamera2")
    assert isinstance(src, Picamera2Source)               # tao nguon khong can thu vien
    with pytest.raises(RuntimeError, match="python3-picamera2"):
        src.open()


def test_khong_thay_camera(fake_picamera2):
    fake_picamera2.cameras = []
    with pytest.raises(RuntimeError, match="Khong mo duoc Pi camera"):
        sources.make_source("picamera2").open()


def test_doc_khung_bgr_qua_module_gia(fake_picamera2):
    src = sources.make_source("picamera2", width=640, height=480, fps=25)
    src.open()
    cam = fake_picamera2.instances[0]
    kw = cam.cfg_kwargs
    assert kw["main"] == {"size": (640, 480), "format": "RGB888"}   # RGB888 cua picamera2 = byte B,G,R
    assert kw["queue"] is False and kw["buffer_count"] <= 3          # luon khung moi nhat
    assert kw["controls"]["FrameRate"] == 25.0
    assert cam.calls == ["configure", "start"]
    f1, f2 = src.read(), src.read()
    assert (f1.index, f2.index) == (0, 1) and f2.ts >= f1.ts
    assert f1.image.shape == (4, 6, 3) and f1.image.dtype == np.uint8
    assert tuple(f1.image[0, 0]) == (10, 20, 30)   # giu nguyen thu tu B,G,R, khong hoan doi kenh
    assert src.live and src.kind == "camera"
    src.close()


def test_dong_camera_khi_dung(fake_picamera2):
    src = sources.make_source("picamera2")
    src.open()
    cam = fake_picamera2.instances[0]
    src.close()
    assert cam.calls[-2:] == ["stop", "close"]
    assert src.read() is None
    src.close()   # goi lan hai khong loi, khong dong lai
    assert cam.calls.count("close") == 1


def test_lay_net():
    assert focus_controls("infinity", None) == {"AfMode": 0, "LensPosition": 0.0}   # mac dinh: co dinh o vo cuc
    assert focus_controls("continuous", None) == {"AfMode": 2}
    assert focus_controls("manual", 0.5) == {"AfMode": 0, "LensPosition": 0.5}
    with pytest.raises(ValueError):
        focus_controls("manual", None)
    with pytest.raises(ValueError):
        focus_controls("auto", None)


def test_tham_so_lay_net_toi_camera(fake_picamera2):
    sources.make_source("picamera2").open()
    assert fake_picamera2.instances[-1].cfg_kwargs["controls"]["LensPosition"] == 0.0
    sources.make_source("picamera2", focus="continuous").open()
    ctl = fake_picamera2.instances[-1].cfg_kwargs["controls"]
    assert ctl["AfMode"] == 2 and "LensPosition" not in ctl
    with pytest.raises(ValueError):
        sources.make_source("picamera2", focus="manual")


def test_cli_tham_so_camera():
    from labview.__main__ import parse
    cfg = parse(["--source", "picamera2", "--cam-width", "1920", "--cam-height", "1080", "--cam-fps", "50",
                 "--focus", "manual", "--lens-position", "0.2"])
    assert (cfg.cam_width, cfg.cam_height, cfg.cam_fps, cfg.cam_focus, cfg.cam_lens_position) == (1920, 1080, 50, "manual", 0.2)
    assert cfg.host == "127.0.0.1"
    assert parse(["--source", "picamera2"]).cam_focus == "infinity"


def _board_view(cols, rows, sq, size, angle_x, angle_y, shift):
    """Anh ban co phang (sq px/o) roi bien dang phoi canh nhe."""
    w, h = (cols + 3) * sq, (rows + 3) * sq
    img = np.full((h, w), 255, np.uint8)
    for r in range(rows + 1):
        for c in range(cols + 1):
            if (r + c) % 2 == 0:
                cv2.rectangle(img, ((c + 1) * sq, (r + 1) * sq), ((c + 2) * sq - 1, (r + 2) * sq - 1), 0, -1)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = src * 0.8 + np.float32([[angle_x, angle_y], [-angle_x, angle_y * 0.5], [-angle_x * 0.5, -angle_y], [angle_x, -angle_y * 0.5]])
    dst += np.float32([size[0] * 0.1 + shift[0], size[1] * 0.1 + shift[1]])
    m = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, m, size, borderValue=255)


def test_hieu_chuan_anh_ban_co_tong_hop(tmp_path):
    from tools import calibrate_camera as cal
    size = (640, 480)
    params = [(0, 0, (0, 0)), (30, 10, (20, 0)), (-30, 10, (-10, 10)), (20, -20, (10, -10)), (-20, -20, (0, 20)),
              (40, 0, (30, 10)), (0, 30, (0, 0)), (-40, 0, (-20, 0))]
    imgs = [_board_view(9, 6, 40, size, ax, ay, sh) for ax, ay, sh in params]
    imgs = [cv2.cvtColor(i, cv2.COLOR_GRAY2BGR) for i in imgs]
    out = tmp_path / "cam.json"
    d = tmp_path / "imgs"
    d.mkdir()
    for i, im in enumerate(imgs):
        cv2.imwrite(str(d / f"{i}.png"), im)
    assert cal.main(["--images", str(d), "--cols", "9", "--rows", "6", "--out", str(out)]) == 0
    import json
    res = json.loads(out.read_text())
    assert (res["width"], res["height"]) == size and res["images_used"] >= 5
    assert len(res["camera_matrix"]) == 3 and len(res["dist_coeffs"]) >= 5
    assert res["camera_matrix"][0][0] > 0 and res["rms_reprojection_px"] < 2.0


def test_hieu_chuan_it_anh_bao_loi(tmp_path):
    from tools import calibrate_camera as cal
    with pytest.raises(ValueError, match="can >= 5"):
        cal.calibrate([np.full((100, 100, 3), 255, np.uint8)] * 3, 9, 6, 25.0)
