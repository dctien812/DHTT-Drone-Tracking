"""Test (pha do) cho tools/record_frames.py: ghi khung hinh goc + chi muc frames.csv + session.json.

Nguon hinh, dong ho, o dia deu la gia; khong can camera, khong mo mang.
"""
import csv
import datetime as dt
import json

import cv2
import numpy as np
import pytest

from labview.sources import Frame, FrameSource

W, H = 64, 48
WALL = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc)
HEADER = ["saved_idx", "src_idx", "file", "t_mono", "t_wall_iso", "width", "height"]


def rf():
    from tools import record_frames
    return record_frames


def _img(i, w=W, h=H):
    rng = np.random.default_rng(i)
    return rng.integers(0, 256, (h, w, 3), dtype=np.uint8)


class FakeSrc(FrameSource):
    """Tra cac khung theo danh sach chi so nguon `indices`, roi None. on_read(n) goi truoc moi lan read (n tu 1)."""
    name, kind = "fake", "file"

    def __init__(self, indices=range(10), w=W, h=H, on_read=None, raise_at=None, open_raises=False,
                 close_raises=False):
        self.indices, self.w, self.h = list(indices), w, h
        self.on_read, self.raise_at = on_read, raise_at
        self.open_raises, self.close_raises = open_raises, close_raises
        self.opened = self.closed = False
        self.reads = 0

    def open(self):
        if self.open_raises:
            raise RuntimeError("khong mo duoc camera")
        self.opened = True

    def read(self):
        self.reads += 1
        if self.on_read:
            self.on_read(self.reads)
        if self.raise_at == self.reads:
            raise RuntimeError("mat nguon")
        if self.reads > len(self.indices):
            return None
        i = self.indices[self.reads - 1]
        return Frame(_img(i, self.w, self.h), 100.0 + i * 0.5, i)

    def close(self):
        self.closed = True
        if self.close_raises:
            raise RuntimeError("close hong")


def run(src, out, **kw):
    kw.setdefault("wall_clock", lambda: WALL)
    kw.setdefault("free_mb", lambda p: 10_000)
    kw.setdefault("clock", lambda: 0.0)
    return rf().record(src, out, **kw)


def session(out):
    dirs = [p for p in out.iterdir() if p.is_dir()]
    assert len(dirs) == 1, dirs
    return dirs[0]


def rows(sdir):
    with open(sdir / "frames.csv", newline="") as f:
        return list(csv.reader(f))


# ---------- thu muc phien, ten ----------

def test_thu_muc_phien_dat_ten_theo_gio_wall_clock(tmp_path):
    run(FakeSrc(range(2)), tmp_path)
    assert session(tmp_path).name == "20260102_030405"


def test_thu_muc_phien_co_tag(tmp_path):
    run(FakeSrc(range(2)), tmp_path, tag="troi-xanh_1")
    assert session(tmp_path).name == "20260102_030405_troi-xanh_1"


@pytest.mark.parametrize("tag", ["a/b", "a b", "..", "a\\b", "trời", "a.b", "abc\n", "\n"])
def test_tag_la_bi_tu_choi_truoc_khi_mo_nguon(tmp_path, tag):
    src = FakeSrc()
    with pytest.raises(ValueError):
        run(src, tmp_path, tag=tag)
    assert not src.opened
    assert list(tmp_path.iterdir()) == []


def test_thu_muc_phien_da_ton_tai_thi_bao_loi_khong_ghi_de(tmp_path):
    d = tmp_path / "20260102_030405"
    (d / "frames").mkdir(parents=True)
    (d / "frames" / "000000.jpg").write_bytes(b"cu")
    src = FakeSrc()
    with pytest.raises(FileExistsError):
        run(src, tmp_path)
    assert not src.opened
    assert (d / "frames" / "000000.jpg").read_bytes() == b"cu"


# ---------- tham so sai ----------

@pytest.mark.parametrize("kw", [{"every": 0}, {"every": -1}, {"max_frames": 0}, {"jpeg_quality": 0},
                                {"jpeg_quality": 101}, {"fmt": "bmp"}])
def test_tham_so_sai_bi_tu_choi_truoc_khi_mo_nguon(tmp_path, kw):
    src = FakeSrc()
    with pytest.raises(ValueError):
        run(src, tmp_path, **kw)
    assert not src.opened
    assert list(tmp_path.iterdir()) == []


# ---------- anh ----------

def test_luu_anh_jpg_dung_ten_va_kich_thuoc_goc(tmp_path):
    run(FakeSrc(range(3), w=200, h=120), tmp_path)
    fr = session(tmp_path) / "frames"
    assert sorted(p.name for p in fr.iterdir()) == ["000000.jpg", "000001.jpg", "000002.jpg"]
    assert cv2.imread(str(fr / "000001.jpg")).shape == (120, 200, 3)


def test_luu_anh_png_khong_mat_diem_anh(tmp_path):
    run(FakeSrc(range(2)), tmp_path, fmt="png")
    fr = session(tmp_path) / "frames"
    assert sorted(p.name for p in fr.iterdir()) == ["000000.png", "000001.png"]
    assert np.array_equal(cv2.imread(str(fr / "000001.png")), _img(1))


def test_jpeg_quality_anh_huong_den_dung_luong_file(tmp_path):
    run(FakeSrc(range(1)), tmp_path / "lo", jpeg_quality=10)
    run(FakeSrc(range(1)), tmp_path / "hi", jpeg_quality=95)
    lo = (session(tmp_path / "lo") / "frames" / "000000.jpg").stat().st_size
    hi = (session(tmp_path / "hi") / "frames" / "000000.jpg").stat().st_size
    assert lo < hi


def test_every_luu_mot_khung_trong_moi_n_khung_doc_duoc(tmp_path):
    res = run(FakeSrc(range(10)), tmp_path, every=3)
    assert (res["frames_read"], res["frames_saved"]) == (10, 4)
    r = rows(session(tmp_path))[1:]
    assert [x[1] for x in r] == ["0", "3", "6", "9"]
    assert [x[0] for x in r] == ["0", "1", "2", "3"]
    assert [x[2] for x in r] == [f"frames/{i:06d}.jpg" for i in range(4)]


# ---------- frames.csv ----------

def test_csv_co_header_va_mot_dong_moi_anh(tmp_path):
    run(FakeSrc(range(3)), tmp_path)
    r = rows(session(tmp_path))
    assert r[0] == HEADER
    assert len(r) == 4
    saved, src_idx, f, t_mono, t_wall, w, h = r[2]
    assert (saved, src_idx, f, w, h) == ("1", "1", "frames/000001.jpg", str(W), str(H))
    assert float(t_mono) == pytest.approx(100.5)
    assert dt.datetime.fromisoformat(t_wall.replace("Z", "+00:00")).year == 2026


def test_csv_duoc_flush_sau_tung_anh(tmp_path):
    snap = {}

    def peek(n):
        if n == 3:   # luc doc khung thu 3, 2 anh da luu: chi muc phai da nam tren dia
            snap["rows"] = rows(next(p for p in tmp_path.iterdir() if p.is_dir()))

    run(FakeSrc(range(5), on_read=peek), tmp_path)
    assert snap["rows"][0] == HEADER
    assert len(snap["rows"]) == 3


# ---------- dung ----------

def test_dung_khi_du_max_frames(tmp_path):
    res = run(FakeSrc(range(10)), tmp_path, max_frames=3)
    assert res["stop_reason"] == "max_frames"
    assert res["frames_saved"] == 3
    assert len(list((session(tmp_path) / "frames").iterdir())) == 3


def test_max_frames_tinh_tren_anh_da_luu_khong_phai_khung_doc(tmp_path):
    res = run(FakeSrc(range(20)), tmp_path, every=2, max_frames=3)
    assert (res["stop_reason"], res["frames_saved"]) == ("max_frames", 3)


def test_dung_khi_het_nguon(tmp_path):
    res = run(FakeSrc(range(5)), tmp_path)
    assert (res["stop_reason"], res["frames_read"], res["frames_saved"]) == ("source_ended", 5, 5)


def test_dung_khi_qua_max_seconds_theo_clock_gia(tmp_path):
    t = {"now": 1000.0}

    def tick(n):
        t["now"] += 1.0

    # moi lan read dong ho nhay 1 s; max_seconds=3 -> doc o t=0,1,2 roi dung: dung 3 anh
    res = run(FakeSrc(range(100), on_read=tick), tmp_path, max_seconds=3.0, clock=lambda: t["now"])
    assert res["stop_reason"] == "max_seconds"
    assert res["frames_saved"] == 3


def test_dung_khi_stop_event_duoc_dat(tmp_path):
    import threading
    ev = threading.Event()
    res = run(FakeSrc(range(100), on_read=lambda n: ev.set() if n == 3 else None), tmp_path, stop_event=ev)
    assert res["stop_reason"] == "stopped"
    assert res["frames_saved"] <= 3


def test_o_dia_it_ngay_tu_dau_thi_khong_luu_anh(tmp_path):
    res = run(FakeSrc(range(10)), tmp_path, min_free_mb=500, free_mb=lambda p: 100)
    assert res["stop_reason"] == "disk_low"
    assert res["frames_saved"] == 0
    assert json.loads((session(tmp_path) / "session.json").read_text())["stop_reason"] == "disk_low"


def test_o_dia_can_giua_chung_duoc_phat_hien_trong_30_anh(tmp_path):
    def free(path):   # du cho 5 anh dau, sau do het cho
        n = sum(1 for _ in path.rglob("*.jpg")) if path.exists() else 0
        return 1000 if n < 5 else 100

    res = run(FakeSrc(range(300)), tmp_path, min_free_mb=500, free_mb=free)
    assert res["stop_reason"] == "disk_low"
    assert 5 <= res["frames_saved"] <= 35


# ---------- loi ghi anh ----------

def test_imwrite_tra_false_thi_dung_error_va_khong_ghi_dong_csv_hong(tmp_path, monkeypatch):
    real, n = cv2.imwrite, {"c": 0}

    def flaky(path, img, *a, **k):
        n["c"] += 1
        return False if n["c"] == 3 else real(path, img, *a, **k)

    monkeypatch.setattr(cv2, "imwrite", flaky)
    res = run(FakeSrc(range(10)), tmp_path)
    assert res["stop_reason"] == "error"
    assert res["frames_saved"] == 2
    assert len(rows(session(tmp_path))) == 1 + 2


def test_imwrite_nem_loi_thi_dung_error(tmp_path, monkeypatch):
    real, n = cv2.imwrite, {"c": 0}

    def boom(path, img, *a, **k):
        n["c"] += 1
        if n["c"] == 2:
            raise OSError("disk full")
        return real(path, img, *a, **k)

    monkeypatch.setattr(cv2, "imwrite", boom)
    res = run(FakeSrc(range(10)), tmp_path)
    assert (res["stop_reason"], res["frames_saved"]) == ("error", 1)
    assert len(rows(session(tmp_path))) == 1 + 1


# ---------- nguon: dong, open, mat nguon ----------

def test_mo_nguon_va_dong_nguon_khi_chay_binh_thuong(tmp_path):
    src = FakeSrc(range(2))
    run(src, tmp_path)
    assert src.opened and src.closed


def test_luon_dong_nguon_khi_read_nem_loi_va_van_ghi_session_json(tmp_path):
    src = FakeSrc(range(10), raise_at=3)
    res = run(src, tmp_path)   # khong nem lai: tra dict error
    assert res["stop_reason"] == "error"
    assert "mat nguon" in res["error"]
    assert src.closed
    sj = json.loads((session(tmp_path) / "session.json").read_text())
    assert sj["stop_reason"] == "error"
    assert "mat nguon" in sj["error"]
    assert sj["frames_saved"] == 2


def test_open_nem_loi_thi_tra_error_va_van_close(tmp_path):
    src = FakeSrc(range(5), open_raises=True)
    res = run(src, tmp_path)
    assert (res["stop_reason"], res["frames_saved"]) == ("error", 0)
    assert "khong mo duoc" in res["error"]
    assert src.closed
    assert json.loads((session(tmp_path) / "session.json").read_text())["stop_reason"] == "error"


def test_close_nem_loi_thi_tra_error(tmp_path):
    res = run(FakeSrc(range(3), close_raises=True), tmp_path)
    assert res["stop_reason"] == "error"
    assert "close" in res["error"]
    assert (session(tmp_path) / "session.json").exists()


def test_khong_co_khoa_error_khi_dung_binh_thuong(tmp_path):
    assert "error" not in run(FakeSrc(range(2)), tmp_path)


def test_dem_khung_nguon_bi_bo_qua_tu_khoang_nhay_cua_idx(tmp_path):
    res = run(FakeSrc([0, 1, 2, 5, 6, 10]), tmp_path)
    assert (res["frames_read"], res["frames_saved"], res["src_gaps"]) == (6, 6, 2 + 3)


def test_khong_co_khoang_nhay_thi_src_gaps_bang_0(tmp_path):
    assert run(FakeSrc(range(5)), tmp_path)["src_gaps"] == 0


def test_src_gaps_khong_tinh_khung_truoc_khung_dau_tien(tmp_path):
    res = run(FakeSrc(range(7, 12)), tmp_path)
    assert (res["frames_read"], res["src_gaps"]) == (5, 0)


def test_src_gaps_khung_doc_ma_khong_luu_do_every_khong_phai_gap(tmp_path):
    res = run(FakeSrc(range(10)), tmp_path, every=3)
    assert (res["frames_read"], res["frames_saved"], res["src_gaps"]) == (10, 4, 0)


def test_src_gaps_van_dem_khi_every_lon_hon_1(tmp_path):
    res = run(FakeSrc([0, 1, 4, 5, 6, 7]), tmp_path, every=2)   # nhay 1 -> 4: bo 2, 3
    assert (res["frames_read"], res["frames_saved"], res["src_gaps"]) == (6, 3, 2)


# ---------- session.json ----------

def test_session_json_khop_gia_tri_tra_ve_va_dung_tung_khoa(tmp_path):
    res = run(FakeSrc(range(4)), tmp_path, tag="t1", every=2, max_frames=9, max_seconds=60.0, min_free_mb=7,
              jpeg_quality=80)
    sdir = session(tmp_path)
    sj = json.loads((sdir / "session.json").read_text())
    assert sj == json.loads(json.dumps(res))
    assert sj["session_dir"] == str(sdir)
    assert sj["started_at"] == WALL.isoformat()
    assert sj["ended_at"] == WALL.isoformat()
    assert (sj["frames_read"], sj["frames_saved"], sj["src_gaps"], sj["stop_reason"]) == (4, 2, 0, "source_ended")
    p = sj["params"]
    assert (p["tag"], p["every"], p["max_frames"], p["max_seconds"], p["min_free_mb"], p["fmt"],
            p["jpeg_quality"]) == ("t1", 2, 9, 60.0, 7, "jpg", 80)


# ---------- ghi session.json / dong csv that bai (hanh vi mong muon) ----------

def test_ghi_session_json_that_bai_thi_record_tra_error_khong_nem_loi(tmp_path, monkeypatch):
    from pathlib import Path
    real = Path.write_text

    def fail(self, *a, **k):
        if self.name == "session.json":
            raise OSError("No space left on device")
        return real(self, *a, **k)

    rf()
    monkeypatch.setattr(Path, "write_text", fail)
    res = run(FakeSrc(range(3)), tmp_path)   # khong duoc nem OSError ra ngoai
    assert res["stop_reason"] == "error"
    assert "No space left" in res["error"]
    assert res["frames_saved"] == 3


def test_cli_ghi_session_json_that_bai_tra_ma_khac_0_khong_de_oserror_thoat(tmp_path, monkeypatch):
    from pathlib import Path
    real = Path.write_text

    def fail(self, *a, **k):
        if self.name == "session.json":
            raise OSError("No space left on device")
        return real(self, *a, **k)

    _patch_source(monkeypatch, lambda spec, **kw: FakeSrc(range(3)))
    monkeypatch.setattr(Path, "write_text", fail)
    code = rf().main(["--source", "file:x", "--out", str(tmp_path), "--min-free-mb", "0"])   # OSError thoat -> test fail
    assert code not in (0, None)


# ---------- CLI ----------

def cli(argv):
    try:
        return rf().main(argv)
    except SystemExit as e:   # argparse thoat bang SystemExit
        return e.code


def _patch_source(monkeypatch, make):
    import labview.sources as s
    monkeypatch.setattr(s, "make_source", make)
    monkeypatch.setattr(rf(), "make_source", make, raising=False)


@pytest.mark.parametrize("extra", [["--every", "0"], ["--max-frames", "0"], ["--jpeg-quality", "101"],
                                   ["--format", "bmp"], ["--tag", "a/b"]])
def test_cli_tham_so_sai_tra_ma_khac_0_va_khong_tao_thu_muc(tmp_path, monkeypatch, extra):
    _patch_source(monkeypatch, lambda spec, **kw: FakeSrc())
    out = tmp_path / "out"
    code = cli(["--source", "file:x", "--out", str(out)] + extra)
    assert code not in (0, None)
    assert not out.exists() or list(out.iterdir()) == []


def test_cli_chay_voi_nguon_gia_tra_ma_0_va_ghi_anh(tmp_path, monkeypatch):
    got = {}

    def make(spec, **kw):
        got["spec"], got["kw"] = spec, kw
        return FakeSrc(range(5))

    _patch_source(monkeypatch, make)
    code = cli(["--source", "file:x", "--out", str(tmp_path), "--tag", "cli", "--min-free-mb", "0",
                "--cam-width", "1920", "--cam-height", "1080", "--cam-fps", "15"])
    assert code == 0
    assert got["spec"] == "file:x"
    sdir = session(tmp_path)
    assert sdir.name.endswith("_cli")
    assert len(list((sdir / "frames").iterdir())) == 5
    assert json.loads((sdir / "session.json").read_text())["stop_reason"] == "source_ended"


def test_cli_ma_thoat_khac_0_khi_stop_reason_la_error(tmp_path, monkeypatch):
    _patch_source(monkeypatch, lambda spec, **kw: FakeSrc(range(5)))
    monkeypatch.setattr(cv2, "imwrite", lambda *a, **k: False)
    code = cli(["--source", "file:x", "--out", str(tmp_path), "--min-free-mb", "0"])
    assert code not in (0, None)


def test_cli_disk_low_tra_ma_khac_0(tmp_path, monkeypatch):
    _patch_source(monkeypatch, lambda spec, **kw: FakeSrc(range(5)))
    monkeypatch.setitem(rf().record.__kwdefaults__, "free_mb", lambda p: 1.0)   # mac dinh gan luc def
    code = cli(["--source", "file:x", "--out", str(tmp_path), "--min-free-mb", "500"])
    assert code not in (0, None)
    assert json.loads((session(tmp_path) / "session.json").read_text())["stop_reason"] == "disk_low"


def test_cli_thu_muc_phien_da_ton_tai_tra_ma_2_khong_traceback(tmp_path, monkeypatch, capsys):
    import tools.record_frames as m
    monkeypatch.setitem(m.record.__kwdefaults__, "wall_clock", lambda: WALL)
    (tmp_path / "20260102_030405").mkdir()
    _patch_source(monkeypatch, lambda spec, **kw: FakeSrc())
    assert cli(["--source", "file:x", "--out", str(tmp_path), "--min-free-mb", "0"]) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_cli_make_source_nem_valueerror_tra_ma_2_khong_tao_thu_muc(tmp_path, monkeypatch, capsys):
    def bad(spec, **kw):
        raise ValueError("nguon sai")

    _patch_source(monkeypatch, bad)
    out = tmp_path / "out"
    assert cli(["--source", "zzz", "--out", str(out)]) == 2
    assert not out.exists()
    assert "Traceback" not in capsys.readouterr().err
