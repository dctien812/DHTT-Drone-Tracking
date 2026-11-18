"""Test nguon picamera2 bang module picamera2 GIA (khong can Pi), va script hieu chuan bang anh ban co tong hop."""
import sys
import threading
import time
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
    assert kw["queue"] is False and kw["buffer_count"] == 4          # luon khung moi nhat; mac dinh 4 (2 co the tut khung)
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


# ---------------- (c)(d)(e)(f): doc loi, buffer, canh bao, dong an toan
def _fast(src):
    src.retry_delay_s = 0.0
    return src


def test_read_loi_mot_lan_thi_thu_lai(fake_picamera2, caplog):
    class Flaky(fake_picamera2):
        def capture_array(self, name="main"):
            if self.frames == 0:
                self.frames += 1
                raise OSError("loi nhat thoi")
            return super().capture_array(name)
    sys.modules["picamera2"].Picamera2 = Flaky
    src = _fast(sources.make_source("picamera2"))
    src.open()
    with caplog.at_level("WARNING", logger="labview"):
        f = src.read()
    assert f is not None and f.index == 0
    assert any("capture_array loi" in r.message for r in caplog.records)   # exception duoc log, khong nuot
    assert src.read() is not None
    src.close()


def test_read_loi_lien_tuc_bao_mat_nguon(fake_picamera2):
    class Dead(fake_picamera2):
        def capture_array(self, name="main"):
            self.frames += 1
            raise OSError("mat ket noi")
    sys.modules["picamera2"].Picamera2 = Dead
    src = _fast(sources.make_source("picamera2"))
    src.open()
    assert src.read() is None
    assert Dead.instances[0].frames == src.max_retries + 1   # 1 lan dau + max_retries lan thu lai
    src.close()


def test_read_het_gio_khi_camera_dung_hinh(fake_picamera2):
    gate = threading.Event()

    class Frozen(fake_picamera2):
        def capture_array(self, name="main"):
            gate.wait(10)
            return super().capture_array(name)
    sys.modules["picamera2"].Picamera2 = Frozen
    src = sources.make_source("picamera2")
    src.frame_timeout_s = 0.2
    src.open()
    t0 = time.monotonic()
    assert src.read() is None                  # pipeline se bao "Mat nguon hinh"
    assert time.monotonic() - t0 < 2.0
    gate.set()
    src.close()


def test_close_khi_read_dang_chan_khong_treo(fake_picamera2):
    gate = threading.Event()

    class Blocking(fake_picamera2):
        def capture_array(self, name="main"):
            gate.wait(30)
            raise OSError("bi huy")

        def stop(self):
            gate.wait(30)                       # ca stop cung ket
            super().stop()
    sys.modules["picamera2"].Picamera2 = Blocking
    src = sources.make_source("picamera2")
    src.frame_timeout_s, src.teardown_timeout_s = 30.0, 0.3
    src.open()
    out = []
    rt = threading.Thread(target=lambda: out.append(src.read()), daemon=True)
    rt.start()
    time.sleep(0.1)
    t0 = time.monotonic()
    src.close()
    rt.join(2.0)
    try:
        assert time.monotonic() - t0 < 4.0     # khong treo
        assert not rt.is_alive() and out == [None]   # read() dang cho cung duoc nha ra
        src.close()                             # goi lai van an toan
    finally:
        gate.set()


@pytest.mark.parametrize("fail_at", ["configure", "start"])
def test_loi_configure_start_van_dong_camera(fake_picamera2, fail_at):
    class Bad(fake_picamera2):
        pass

    def boom(self, *a, **k):
        raise RuntimeError("hong")
    setattr(Bad, fail_at, boom)
    sys.modules["picamera2"].Picamera2 = Bad
    with pytest.raises(RuntimeError, match="Khong mo duoc Pi camera"):
        sources.make_source("picamera2").open()
    assert "close" in Bad.instances[0].calls


def test_buffers_va_kich_thuoc_thuc(fake_picamera2, caplog):
    class Sized(fake_picamera2):
        def camera_configuration(self):
            return {"main": {"size": (1536, 864)}}

        def capture_array(self, name="main"):
            return np.zeros((864, 1536, 3), np.uint8)
    sys.modules["picamera2"].Picamera2 = Sized
    src = sources.make_source("picamera2", width=1280, height=720, buffers=6)
    with caplog.at_level("WARNING", logger="labview"):
        src.open()
    assert Sized.instances[0].cfg_kwargs["buffer_count"] == 6
    assert (src.w, src.h) == (1536, 864)
    assert any("khac yeu cau" in r.message for r in caplog.records)
    src.close()
    with pytest.raises(ValueError):
        sources.make_source("picamera2", buffers=1)


def test_fps_thuc_duoc_do(fake_picamera2):
    src = sources.make_source("picamera2", fps=30)
    src.fps_window = 5
    src.open()
    for _ in range(6):
        src.read()
    assert src.fps != 30.0 and src.fps > 0       # do tu khung that, khong chep theo yeu cau
    src.close()


def test_lens_position_bi_bo_qua_thi_canh_bao(caplog):
    with caplog.at_level("WARNING", logger="labview"):
        sources.make_source("picamera2", focus="infinity", lens_position=0.5)
    assert any("--lens-position" in r.message and "bi bo qua" in r.message for r in caplog.records)
    caplog.clear()
    with caplog.at_level("WARNING", logger="labview"):
        sources.make_source("picamera2", focus="manual", lens_position=0.5)
    assert not caplog.records


def test_cli_cam_buffers_va_hfov_mac_dinh():
    from labview.__main__ import parse
    assert parse(["--source", "picamera2"]).cam_buffers == 4
    assert parse(["--source", "picamera2", "--cam-buffers", "3"]).cam_buffers == 3
    c = parse(["--source", "picamera2"])
    assert c.hfov_deg == 102.0 and c.hfov_note                      # tu dong, co ghi chu de log
    assert parse(["--source", "picamera2", "--hfov", "90"]).hfov_deg == 90.0
    assert parse(["--source", "file:x"]).hfov_deg == 66.0           # webcam/video giu 66


def _board_dir(tmp_path, ext, extra_sizes=()):
    d = tmp_path / "imgs"
    d.mkdir()
    params = [(0, 0, (0, 0)), (30, 10, (20, 0)), (-30, 10, (-10, 10)), (20, -20, (10, -10)), (-20, -20, (0, 20)),
              (40, 0, (30, 10)), (0, 30, (0, 0)), (-40, 0, (-20, 0))]
    for i, (ax, ay, sh) in enumerate(params):
        im = cv2.cvtColor(_board_view(9, 6, 40, (640, 480), ax, ay, sh), cv2.COLOR_GRAY2BGR)
        assert cv2.imwrite(str(d / f"b{i}{ext}"), im, [cv2.IMWRITE_JPEG_QUALITY, 98])
    for j, size in enumerate(extra_sizes):
        cv2.imwrite(str(d / f"x{j}{ext}"), np.full((size[1], size[0], 3), 200, np.uint8))
    return d


def test_hieu_chuan_duoi_JPG_lan_co_anh(tmp_path, capsys):
    from tools import calibrate_camera as cal
    d = _board_dir(tmp_path, ".JPG", extra_sizes=[(320, 240), (640, 480)])   # 1 anh khac co, 1 anh dung co nhung khong co ban co
    out = tmp_path / "cam.json"
    assert cal.main(["--images", str(d), "--cols", "9", "--rows", "6", "--out", str(out)]) == 0
    import json
    res = json.loads(out.read_text())
    assert (res["width"], res["height"]) == (640, 480) and res["images_total"] == 10 and res["images_used"] >= 5
    cap = capsys.readouterr()
    assert "BO QUA x0.JPG" in cap.err and "320x240" in cap.err            # khac co: ten + ly do
    assert "BO QUA x1.JPG" in cap.err and "khong tim thay ban co" in cap.err
    assert f"--calib {out}" in cap.out and "--fx" not in cap.out         # in lenh dung --calib


def test_hieu_chuan_lan_co_hoa_thi_bao_loi():
    from tools import calibrate_camera as cal
    a, b = np.full((100, 100, 3), 255, np.uint8), np.full((50, 50, 3), 255, np.uint8)
    with pytest.raises(ValueError, match="khong co co da so"):
        cal.calibrate([a, a, b, b], 9, 6, 25.0)
