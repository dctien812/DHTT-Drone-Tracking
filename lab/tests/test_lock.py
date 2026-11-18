import pytest
from labview.lock import LockManager, Track, hit_test


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def T(i, x1, y1, x2, y2, c=0.5):
    return Track(i, (x1, y1, x2, y2), c)


TRACKS = [T(1, 10, 10, 50, 50, 0.6), T(2, 100, 100, 140, 140, 0.9), T(3, 105, 105, 120, 120, 0.4)]


def make(timeout=2.0):
    clk, ev = Clock(), []
    return LockManager(timeout, clk, ev.append), clk, ev


def test_lock_and_release():
    m, clk, ev = make()
    assert m.update(TRACKS).active is False
    assert m.lock_id(2, TRACKS) is True
    st = m.update(TRACKS)
    assert st.active and st.track_id == 2 and st.track.id == 2
    assert m.release() is True
    assert m.update(TRACKS).active is False
    assert m.release() is False
    assert any("KHOA" in e for e in ev) and any("HUY" in e for e in ev)


def test_lock_unknown_id_rejected():
    m, _, _ = make()
    assert m.lock_id(99, TRACKS) is False
    assert m.locked_id() is None


def test_auto_release_after_timeout():
    m, clk, ev = make(2.0)
    m.lock_id(1, TRACKS)
    only2 = [TRACKS[1]]
    clk.t += 1.5
    st = m.update(only2)
    assert st.active and st.track is None and abs(st.lost_for_s - 1.5) < 1e-9
    clk.t += 0.6  # tổng 2.1 s > 2.0
    st = m.update(only2)
    assert st.active is False and m.locked_id() is None
    assert any("TU BO KHOA" in e for e in ev)


def test_reacquire_within_timeout_resets_clock():
    m, clk, _ = make(2.0)
    m.lock_id(1, TRACKS)
    clk.t += 1.9
    assert m.update([]).active
    assert m.update(TRACKS).track.id == 1     # thấy lại
    clk.t += 1.9
    assert m.update([]).active                # đồng hồ mất dấu bắt đầu lại từ lần thấy cuối
    clk.t += 0.2
    assert m.update([]).active is False


def test_custom_timeout():
    m, clk, _ = make(0.5)
    m.lock_id(1, TRACKS)
    clk.t += 0.6
    assert m.update([]).active is False


def test_hit_test_inside_prefers_smallest():
    assert hit_test(110, 110, TRACKS).id == 3     # nằm trong cả 2 và 3 -> khung nhỏ nhất
    assert hit_test(130, 130, TRACKS).id == 2
    assert hit_test(30, 30, TRACKS).id == 1


def test_click_outside_all_boxes():
    assert hit_test(300, 300, TRACKS) is None
    assert hit_test(70, 30, TRACKS, margin=0) is None
    m, _, _ = make()
    assert m.lock_point(300, 300, TRACKS, margin=12) is None
    assert m.locked_id() is None


def test_click_margin_picks_nearest():
    assert hit_test(55, 30, TRACKS, margin=10).id == 1
    assert hit_test(65, 30, TRACKS, margin=10) is None


def test_lock_point_and_best():
    m, _, _ = make()
    assert m.lock_point(30, 30, TRACKS) == 1
    assert m.lock_best(TRACKS) == 2
    assert m.lock_best([]) is None


# ---------------- gán lại khóa khi bộ theo dõi đổi ID
from labview.lock import ReacquireParams


def moving_lock(params=None, extra=()):
    """Khóa ID 1 (khung 40x40) đang đi sang phải 100 px/s; trả (manager, clock, events). Đồng hồ ở t0+0.1."""
    clk, ev = Clock(), []
    m = LockManager(2.0, clk, ev.append, params)
    others = list(extra)
    m.lock_id(1, [T(1, 100, 100, 140, 140)] + others)
    clk.t += 0.1
    assert m.update([T(1, 110, 100, 150, 140)] + others).state == "tracking"
    return m, clk, ev


def test_reacquire_new_track_near_prediction_and_similar_size():
    m, clk, ev = moving_lock()
    clk.t += 0.1  # dự đoán: tâm (140,120)
    st = m.update([T(5, 121, 101, 161, 141)])
    assert st.active and st.track_id == 5 and st.track.id == 5
    assert st.state == "reacquired" and st.reacquired == 1
    assert m.locked_id() == 5 and any("GAN LAI" in e for e in ev)


def test_no_reacquire_far_track():
    m, clk, _ = moving_lock()
    clk.t += 0.1
    st = m.update([T(6, 600, 100, 640, 140)])
    assert st.active and st.track is None and st.state == "searching" and st.reacquired == 0
    assert st.predicted == (140.0, 120.0)
    assert m.locked_id() == 1


def test_no_reacquire_very_different_size():
    m, clk, _ = moving_lock()
    clk.t += 0.1
    st = m.update([T(7, 135, 115, 145, 125), T(8, 40, 40, 240, 240)])  # rộng 10 (0,25x) và 200 (5x), cả hai gần dự đoán
    assert st.state == "searching" and st.track is None and m.locked_id() == 1


def test_reacquire_picks_nearest_candidate():
    m, clk, _ = moving_lock()
    clk.t += 0.1
    st = m.update([T(9, 150, 100, 190, 140), T(10, 121, 101, 161, 141), T(11, 100, 130, 140, 170)])
    assert st.track_id == 10


def test_established_other_track_is_not_stolen():
    other = T(2, 160, 100, 200, 140)  # đã có mặt từ trước, cùng cỡ, gần vị trí dự đoán
    m, clk, _ = moving_lock(extra=[other])
    clk.t += 0.1
    st = m.update([other])
    assert st.state == "searching" and st.track is None and m.locked_id() == 1


def test_timeout_drops_lock_when_no_candidate():
    m, clk, ev = moving_lock()
    clk.t += 1.0
    assert m.update([]).state == "searching"
    clk.t += 1.2
    assert m.update([T(6, 600, 100, 640, 140)]).active is False
    assert m.locked_id() is None and any("TU BO KHOA" in e for e in ev)


def test_gate_grows_with_lost_time():
    m, clk, _ = moving_lock()
    clk.t += 0.1
    far = T(5, 300, 100, 340, 140)  # tâm (320,120), cách dự đoán 180 px; cổng 0,1 s ~ 68 px
    assert m.update([far]).state == "searching"
    clk.t += 0.9  # mất 1,0 s: dự đoán (230,120) (ngoại suy 1 s), cổng 40*(1,5+2)=140 px, cách 90 px
    assert m.update([far]).track_id == 5


def test_reacquire_count_and_state_flash():
    m, clk, _ = moving_lock()
    clk.t += 0.1
    assert m.update([T(5, 121, 101, 161, 141)]).reacquired == 1
    clk.t += 0.1
    assert m.update([T(5, 131, 101, 171, 141)]).state == "reacquired"
    clk.t += 0.1
    st = m.update([T(12, 141, 101, 181, 141)])  # ID 5 biến mất, ID 12 mới xuất hiện
    assert st.track_id == 12 and st.reacquired == 2
    clk.t += 2.5
    st = m.update([T(12, 150, 101, 190, 141)])
    assert st.state == "tracking" and st.reacquired == 2
    m.lock_id(12, [T(12, 150, 101, 190, 141)])  # khóa mới: đếm lại từ 0
    assert m.update([T(12, 150, 101, 190, 141)]).reacquired == 0


def test_reacquire_can_be_disabled():
    m, clk, _ = moving_lock(ReacquireParams(enabled=False))
    clk.t += 0.1
    st = m.update([T(5, 121, 101, 161, 141)])
    assert st.state == "searching" and st.track is None and m.locked_id() == 1


# ---------------- D1/D2: ngưỡng conf, kẹp trong khung, rời khung, lịch sử vận tốc
FRAME = (640, 512)


def test_candidate_below_min_conf_is_rejected():
    m, clk, _ = moving_lock(ReacquireParams(min_conf=0.4))
    clk.t += 0.1
    assert m.update([T(5, 121, 101, 161, 141, c=0.3)]).state == "searching"
    assert m.update([T(5, 121, 101, 161, 141, c=0.45)]).track_id == 5


def test_predicted_position_clamped_to_frame():
    m, clk, _ = moving_lock()          # 100 px/s sang phải, tâm cuối (130,120)
    clk.t += 0.9                       # ngoại suy 0,9 s -> x = 220; khung rộng 200 thì kẹp ở 200
    st = m.update([], (200, 512))
    assert st.predicted == (200.0, 120.0)
    assert m.update([], None).predicted == pytest.approx((220.0, 120.0))


def test_no_reacquire_when_target_left_through_edge():
    clk, ev = Clock(), []
    m = LockManager(2.0, clk, ev.append)
    m.lock_id(1, [T(1, 560, 100, 600, 140)])
    clk.t += 0.1
    m.update([T(1, 580, 100, 620, 140)], FRAME)   # sát mép phải (640-620=20 < 20? =20 => dùng mép 630 bên dưới)
    clk.t += 0.1
    m.update([T(1, 590, 100, 630, 140)], FRAME)   # 10 px tới mép phải, đang đi sang phải
    clk.t += 0.1
    near = T(5, 560, 100, 600, 140)               # ngay vị trí kẹp, cùng cỡ: nếu không có luật rời khung thì sẽ gán
    st = m.update([near], FRAME)
    assert st.state == "searching" and st.track is None and m.locked_id() == 1
    # cùng tình huống nhưng đi vào trong (vận tốc hướng vào) thì vẫn gán lại được
    clk2 = Clock(); m2 = LockManager(2.0, clk2)
    m2.lock_id(1, [T(1, 600, 100, 630, 140)])
    clk2.t += 0.1
    m2.update([T(1, 570, 100, 610, 140)], FRAME)
    clk2.t += 0.1
    assert m2.update([T(5, 560, 100, 600, 140)], FRAME).track_id == 5


def test_velocity_history_restarts_after_reacquire():
    m, clk, _ = moving_lock()                      # 100 px/s sang phải
    clk.t += 0.1
    assert m.update([T(5, 121, 101, 161, 141)]).track_id == 5
    assert m._hist == [(clk.t, 141.0, 121.0)]     # chỉ còn quan sát của track mới
    clk.t += 0.1
    st = m.update([])                              # chưa có vận tốc mới: dự đoán đứng yên tại tâm track mới
    assert st.predicted == (141.0, 121.0)
