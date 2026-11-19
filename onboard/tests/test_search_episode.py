"""Test PHA DO cho SearchEpisode (dtrack/search.py, MOI) - .office/design-search.md muc (a), (d) va S-3/S-4.

Chu ky gia dinh (xem bao cao): SearchEpisode(cfg: SearchConfig, coast_follow_s: float);
update(t, tracking: bool, had_target: bool) -> EpisodeTick(ep_id, ep_s|None, phase|None, closed, expired); reset().
Quy uoc tu chot (thiet ke mo ho):
- khong co dot mo: ep_s None, phase None, closed False, expired False;
- tick mo dot: ep_s == 0.0 (dong ho tuyet doi tu luc mo);
- tick dong dot (TRACK lien tuc >= reacquire_hold_s): closed True (dung MOT tick); tick ke tiep ep_s None;
- expired = ep_s > total_s (khong gom bang), ke ca khi tick do dang TRACK chua du hold;
- phase: ep_s <= coast_follow_s -> 0; sau do 1; climb_m > 0 va ep_s >= climb_start_s -> 2.
Thoi diem dung boi so cua 0.25 (nhi phan chinh xac) de bien dung 1,0 s khong lech do lam tron.
Import dtrack.search ben TRONG ham de ca khac van thu thap duoc.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

T0 = 100.0   # moc mo dot (boi so cua 0.25)
Q = 0.25


def mk(coast_follow_s=4.0, **kw):
    from dtrack.search import SearchEpisode
    from dtrack.config import SearchConfig
    return SearchEpisode(SearchConfig(**kw), coast_follow_s)


def open_ep(ep, t=T0):
    """Mo dot: chu ky dau co had_target ma khong TRACK."""
    return ep.update(t, False, True)


# ---------------- mo dot ----------------
def test_no_episode_while_tracking_even_with_had_target():
    ep = mk()
    for k in range(20):
        tk = ep.update(T0 + k * Q, True, True)
        assert tk.ep_s is None and tk.phase is None and not tk.closed and not tk.expired


def test_never_seen_target_never_opens_episode():
    ep = mk()
    for k in range(400):    # 100 s khong thay
        tk = ep.update(T0 + k * Q, False, False)
        assert tk.ep_s is None and tk.phase is None and not tk.expired


def test_opens_at_first_cycle_with_had_target_and_not_tracking():
    ep = mk()
    ep.update(T0 - Q, True, True)
    tk = open_ep(ep)
    assert tk.ep_s == 0.0 and tk.phase == 0 and not tk.closed and not tk.expired


def test_episode_clock_is_absolute_since_open():
    ep = mk()
    open_ep(ep)
    for k in (1, 3, 8, 20, 40):
        tk = ep.update(T0 + k * Q, False, True)
        assert abs(tk.ep_s - k * Q) < 1e-9


# ---------------- chop TRACK ----------------
def test_short_track_blips_do_not_reset_clock():
    ep = mk()
    open_ep(ep)
    t = T0
    # 3 lan chop TRACK 0,75 s (3 tick), moi lan cach nhau 1 tick mat
    for _ in range(3):
        for _ in range(3):
            t += Q
            tk = ep.update(t, True, True)
            assert not tk.closed and tk.ep_s is not None
        t += Q
        ep.update(t, False, True)
    tk = ep.update(t + Q, False, True)
    assert abs(tk.ep_s - (t + Q - T0)) < 1e-9
    assert not tk.closed


def test_track_streak_must_be_continuous_to_close():
    ep = mk()
    open_ep(ep)
    for k in (1, 2, 3):                       # 0,75 s TRACK
        assert not ep.update(T0 + k * Q, True, True).closed
    ep.update(T0 + 4 * Q, False, True)        # roi 1 tick: bo dem chuoi ve 0
    for k in (5, 6, 7):                       # lai 0,75 s: tong 1,5 s nhung khong lien tuc
        assert not ep.update(T0 + k * Q, True, True).closed
    tk = ep.update(T0 + 8 * Q, False, True)
    assert tk.ep_s is not None


def test_track_continuous_exactly_hold_closes_episode():
    ep = mk()
    open_ep(ep)
    ta = T0 + 10.0
    ep.update(ta - Q, False, True)
    ticks = [ep.update(ta + k * Q, True, True) for k in range(0, 5)]   # chuoi 0..1,0 s
    assert [tk.closed for tk in ticks] == [False, False, False, False, True]
    after = ep.update(ta + 5 * Q, True, True)
    assert after.ep_s is None and after.phase is None and not after.closed


def test_track_just_below_hold_does_not_close():
    ep = mk()
    open_ep(ep)
    ta = T0 + 10.0
    ep.update(ta - Q, False, True)
    ticks = [ep.update(ta + k * Q, True, True) for k in range(0, 4)]   # toi 0,75 s
    assert not any(tk.closed for tk in ticks)
    assert ticks[-1].ep_s is not None


def test_hold_comes_from_config():
    ep = mk(reacquire_hold_s=0.5)
    open_ep(ep)
    ta = T0 + 5.0
    ep.update(ta - Q, False, True)
    ticks = [ep.update(ta + k * Q, True, True) for k in range(0, 3)]   # 0, 0,25, 0,5
    assert [tk.closed for tk in ticks] == [False, False, True]


# ---------------- het han ----------------
def test_expired_only_after_total_s_strictly():
    ep = mk(total_s=20.0)
    open_ep(ep)
    assert not ep.update(T0 + 19.75, False, True).expired
    assert not ep.update(T0 + 20.0, False, True).expired
    tk = ep.update(T0 + 20.25, False, True)
    assert tk.expired and tk.ep_s > 20.0


def test_expired_even_while_blinking_track():
    ep = mk(total_s=20.0)
    open_ep(ep)
    ep.update(T0 + 19.25, False, True)
    ep.update(T0 + 19.5, True, True)       # chop TRACK, chuoi 0 s
    ep.update(T0 + 19.75, True, True)
    ep.update(T0 + 20.0, True, True)
    tk = ep.update(T0 + 20.25, True, True)   # chuoi 0,75 s < hold
    assert not tk.closed and tk.expired


# ---------------- ep_id / reset ----------------
def test_ep_id_increases_for_new_episode():
    ep = mk()
    first = open_ep(ep)
    ta = T0 + 5.0
    ep.update(ta - Q, False, True)
    for k in range(0, 6):                    # dong dot
        ep.update(ta + k * Q, True, True)
    tk2 = ep.update(T0 + 30.0, False, True)  # mat lan nua
    assert tk2.ep_s == 0.0
    assert tk2.ep_id > first.ep_id


def test_ep_id_stable_within_episode():
    ep = mk()
    a = open_ep(ep)
    b = ep.update(T0 + 5.0, False, True)
    assert a.ep_id == b.ep_id


def test_reset_closes_episode():
    ep = mk()
    open_ep(ep)
    ep.update(T0 + 3.0, False, True)
    ep.reset()
    tk = ep.update(T0 + 3.25, True, True)
    assert tk.ep_s is None and tk.phase is None and not tk.expired


def test_reset_then_loss_opens_fresh_clock():
    ep = mk()
    open_ep(ep)
    ep.update(T0 + 3.0, False, True)
    ep.reset()
    tk = ep.update(T0 + 50.0, False, True)
    assert tk.ep_s == 0.0


# ---------------- pha ----------------
def _phase_at(ep, s):
    return ep.update(T0 + s, False, True).phase


def test_phase_boundaries_without_climb():
    ep = mk(climb_m=0.0)
    open_ep(ep)
    assert _phase_at(ep, 1.0) == 0
    assert _phase_at(ep, 4.0) == 0            # ep_s <= coast_follow_s
    assert _phase_at(ep, 4.25) == 1
    assert _phase_at(ep, 12.0) == 1
    assert _phase_at(ep, 19.75) == 1


def test_phase_never_2_when_climb_m_zero():
    ep = mk(climb_m=0.0, climb_start_s=10.0)
    open_ep(ep)
    assert all(_phase_at(ep, s) in (0, 1) for s in (9.75, 10.0, 15.0, 19.75))


def test_phase_2_from_climb_start_when_climb_enabled():
    ep = mk(climb_m=5.0, climb_start_s=10.0)
    open_ep(ep)
    assert _phase_at(ep, 4.0) == 0
    assert _phase_at(ep, 9.75) == 1
    assert _phase_at(ep, 10.0) == 2
    assert _phase_at(ep, 19.75) == 2


def test_phase_uses_coast_follow_s_argument():
    ep = mk(coast_follow_s=2.0, total_s=20.0)
    open_ep(ep)
    assert _phase_at(ep, 2.0) == 0
    assert _phase_at(ep, 2.25) == 1
