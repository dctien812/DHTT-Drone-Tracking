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
