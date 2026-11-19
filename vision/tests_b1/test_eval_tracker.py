"""Test pha do cho vision/scripts/b1a/eval_tracker.py (A4: ty le thoi gian o TRACK cua bo bam du an).

Chu ky da chot:
  track_time_fraction(frames, camera=None, mode="all") -> {"track_fraction", "n_frames", "n_track", "statuses"}
     frames = [{"t": giay, "dets": [(cx, cy, w, h, conf), ...]}, ...]   # pixel o thang 2304, anh 2304x1296
     camera: dtrack.types.CameraModel; None -> CameraModel(width=2304, height=1296, fx=933, fy=933, cx=1152, cy=648)
     Camera co dinh: OwnState dung yen, quaternion (1,0,0,0). Dung SingleTargetTracker(camera) cua
     onboard/dtrack/tracker.py voi TrackerConfig mac dinh; moi khung goi update(dets -> Detection voi
     t_capture = t, own, t_now = t). track_fraction = so khung status == TRACK / so khung.
     mode: "all" (mac dinh) = dua MOI phat hien cua khung vao bo bam (dung nhu onboard/dtrack/app.py tren drone that);
           "top1" = chi phat hien conf cao nhat moi khung; gia tri khac -> ValueError.
     BAO CAO A4 PHAI NEU CHE DO (mode) da dung.
     (Module tu them onboard/ vao sys.path; test khong lam ho.)

So mong doi da do bang chay that tracker.py tren cung chuoi (script rieng, khong nam trong test):
  300 khung 30 Hz day du -> 298 TRACK (2 khung dau chua xac nhan, confirm_hits=3)
  mat 30 khung (1 s) giua chuoi -> 274 TRACK (COAST khi tuoi do > 0,25 s; 2 do lien tiep de bat lai)
  600 khung, mat 120 khung (4 s > 3 s) -> 483 TRACK (LOST, phai xac nhan lai 3 do)
  khong phat hien -> 0
"""
import math
import os
import random
import sys

import pytest

ONBOARD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "onboard"))


def camera(fx=933.0):
    if ONBOARD not in sys.path:
        sys.path.insert(0, ONBOARD)
    from dtrack.types import CameraModel
    return CameraModel(width=2304, height=1296, fx=fx, fy=fx, cx=1152.0, cy=648.0)


def make_frames(n, fps, missing=()):
    out = []
    for k in range(n):
        t = k / fps
        dets = [] if k in missing else [(1000.0 + 20.0 * t, 648.0, 30.0, 20.0, 0.9)]
        out.append({"t": t, "dets": dets})
    return out


def test_full_detection_stream_is_almost_always_tracking():
    from eval_tracker import track_time_fraction
    r = track_time_fraction(make_frames(300, 30), camera())
    assert r["n_frames"] == 300
    assert r["n_track"] == 298
    assert r["track_fraction"] == pytest.approx(298 / 300)
    assert r["track_fraction"] >= 0.98


def test_one_second_gap_reduces_track_time_by_expected_amount():
    from eval_tracker import track_time_fraction
    full = track_time_fraction(make_frames(300, 30), camera())["track_fraction"]
    gap = track_time_fraction(make_frames(300, 30, set(range(100, 130))), camera())
    assert gap["n_track"] == 274
    assert gap["track_fraction"] == pytest.approx(274 / 300)
    assert 0.02 < full - gap["track_fraction"] < 0.10
    # khung 99 la do cuoi; khung 106 tuoi 7/30 s con TRACK, khung 107 tuoi 8/30 s > 0,25 s la COAST
    assert gap["statuses"][106] == "track" and gap["statuses"][107] == "coast"


def test_gap_longer_than_three_seconds_needs_reconfirmation():
    from eval_tracker import track_time_fraction
    r = track_time_fraction(make_frames(600, 30, set(range(200, 320))), camera())
    assert r["n_track"] == 483
    assert r["track_fraction"] == pytest.approx(0.805)


def test_no_detections_means_zero_track_time():
    from eval_tracker import track_time_fraction
    r = track_time_fraction(make_frames(300, 30, set(range(300))), camera())
    assert r["track_fraction"] == 0.0 and r["n_track"] == 0


def test_low_confidence_detections_are_ignored_by_tracker():
    from eval_tracker import track_time_fraction
    frames = make_frames(100, 30)
    for f in frames:
        f["dets"] = [(cx, cy, w, h, 0.1) for cx, cy, w, h, _ in f["dets"]]   # < min_conf 0,25
    assert track_time_fraction(frames, camera())["track_fraction"] == 0.0


def test_frame_rate_comes_from_timestamps_not_frame_count():
    from eval_tracker import track_time_fraction
    # 10 Hz, mat 10 khung = 1 s: 89 TRACK tren 100 khung (do bang tracker that)
    r = track_time_fraction(make_frames(100, 10, set(range(40, 50))), camera())
    assert r["n_track"] == 89



def test_default_camera_is_2304x1296_fx_933():
    from eval_tracker import track_time_fraction
    frames = make_frames(300, 30, set(range(100, 130)))
    a = track_time_fraction(frames)                     # camera=None
    b = track_time_fraction(frames, camera(933.0))
    assert a["statuses"] == b["statuses"] and a["n_track"] == b["n_track"] == 274
    # fx khac thi duoc tuy y (tham so), khong ghim so
    assert track_time_fraction(frames, camera(2800.0))["n_track"] > 0




def sine_frames(n=600, period=120, peak_px_per_frame=24.0):
    amp = peak_px_per_frame * period / (2 * math.pi)
    return [{"t": k / 30, "dets": [(1152.0 + amp * math.sin(2 * math.pi * k / period), 648.0, 30.0, 20.0, 0.9)]}
            for k in range(n)]


def test_fast_smooth_motion_24px_per_frame_stays_in_track():
    """Van toc dinh 24 px/khung (~p95 buoc that o thang 2304), du phat hien, fx mac dinh 933.
    Do bang tracker.py that: hinh sin 600 khung -> 598 TRACK; mot chieu 90 khung -> 88 TRACK (fx 933 va 2800).
    Nguong dat tru bien an toan. Song tam giac dao chieu tuc thoi (van toc doi 48 px/khung) la dang chuyen
    dong nhan tao lam bo bam rot (08 do 162/600 o fx 933): khong dung de cham."""
    from eval_tracker import track_time_fraction
    sine = track_time_fraction(sine_frames(), None)
    assert sine["n_track"] >= 585
    oneway = [{"t": k / 30, "dets": [(100.0 + 24.0 * k, 648.0, 30.0, 20.0, 0.9)]} for k in range(90)]
    assert track_time_fraction(oneway, None)["n_track"] >= 80


def noisy(frames, conf, seed=0):
    rng = random.Random(seed)
    return [{"t": f["t"], "dets": f["dets"] + [(rng.uniform(50, 2250), rng.uniform(50, 1250), 30.0, 20.0, conf)]}
            for f in frames]


def test_top1_mode_with_lower_confidence_noise_equals_clean_run():
    """Do that: sach 598/600 ; top1 + nhieu conf 0,5 (< 0,9 cua muc tieu) 598/600."""
    from eval_tracker import track_time_fraction
    clean = make_frames(600, 30)
    a = track_time_fraction(clean, camera())["track_fraction"]
    b = track_time_fraction(noisy(clean, 0.5), camera(), mode="top1")["track_fraction"]
    assert abs(a - b) <= 0.01


def test_all_mode_with_higher_confidence_noise_degrades_track_time_documented_behaviour():
    """Ghi nhan hanh vi hien tai cua tracker.py: moi khung them mot phat hien nhieu conf 0,95 (> 0,9)
    o cho khac, mode "all" -> do that 423/600 = 0,705 so voi 598/600 = 0,997 (giam ~29 diem).
    Bao cao A4 vi vay phai neu mode."""
    from eval_tracker import track_time_fraction
    clean = make_frames(600, 30)
    a = track_time_fraction(clean, camera())["track_fraction"]
    b = track_time_fraction(noisy(clean, 0.95), camera(), mode="all")["track_fraction"]
    assert b <= a - 0.05


def test_default_mode_is_all():
    from eval_tracker import track_time_fraction
    frames = noisy(make_frames(600, 30), 0.95)
    assert track_time_fraction(frames, camera())["statuses"] == track_time_fraction(frames, camera(), mode="all")["statuses"]


def test_unknown_mode_raises():
    from eval_tracker import track_time_fraction
    with pytest.raises(ValueError):
        track_time_fraction(make_frames(10, 30), camera(), mode="top2")



# ---------------- vong 3 ----------------
def test_empty_frames_raise():
    from eval_tracker import track_time_fraction
    with pytest.raises(ValueError):
        track_time_fraction([], camera())


@pytest.mark.parametrize("ts", [[0.0, 0.1, 0.1, 0.2], [0.0, 0.2, 0.1, 0.3], [0.3, 0.2, 0.1]])
def test_non_increasing_time_raises(ts):
    from eval_tracker import track_time_fraction
    frames = [{"t": t, "dets": [(1000.0, 648.0, 30.0, 20.0, 0.9)]} for t in ts]
    with pytest.raises(ValueError):
        track_time_fraction(frames, camera())


def test_return_counts_gives_tuple_and_default_stays_dict():
    from eval_tracker import track_time_fraction
    frames = make_frames(300, 30)
    assert track_time_fraction(frames, camera(), return_counts=True) == (298, 300)
    assert isinstance(track_time_fraction(frames, camera()), dict)


def test_all_mode_result_does_not_depend_on_input_order_when_conf_differs():
    from eval_tracker import track_time_fraction
    target = lambda k: (1000.0 + 0.67 * k, 648.0, 30.0, 20.0, 0.9)
    noise = lambda k: (200.0 + 7.0 * (k % 40), 300.0 + 11.0 * (k % 30), 30.0, 20.0, 0.95)
    f1 = [{"t": k / 30, "dets": [target(k), noise(k)]} for k in range(300)]
    f2 = [{"t": k / 30, "dets": [noise(k), target(k)]} for k in range(300)]
    a = track_time_fraction(f1, camera())
    b = track_time_fraction(f2, camera())
    assert a["statuses"] == b["statuses"]
