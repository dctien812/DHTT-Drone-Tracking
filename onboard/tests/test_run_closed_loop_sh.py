"""simtools/run_closed_loop.sh o che do DRY_RUN=1 (Q8): in ra dung dong lenh se goi helper va bo cham roi thoat 0, khong chay gi.
PHA DO TDD: DRY_RUN chua co trong script (ca nao cung do cho toi khi 05 them); de KHONG BAO GIO khoi dong SITL nham, moi ca kiem tra
script co chuoi "DRY_RUN" truoc khi chay (khong co -> fail ngay, khong goi script).

Dinh dang DRY_RUN chot (05 phai in dung):
  DRY_RUN helper: <PY> <HERE>/sim_helper.py --out <OUT> --speed <S> --scenario <SC> --range <R> [...co khac...]
  DRY_RUN analyzer: <PY> <HERE>/analyze_closed_loop.py <OUT> --speed <S> --range <R> --helper-rc 0 [...co khac...]
  (moi dong in mot lan, token cach nhau dau cach, dung shlex; --helper-rc luon la 0 khi DRY_RUN). Thoat 0, khong tao thu muc OUT, khong goi
  pgrep/SITL. Kiem som gia tri bien (xem test): sai -> thoat 2, KHONG in dong DRY_RUN.
CHUOI HIEN TAI (doc tu script, dong 120-121 va 179) khi khong dat bien moi:
  helper:   sim_helper.py --out OUT --speed S --scenario SCENARIO --range RANGE            (HARGS rong, them --straight neu STRAIGHT=1)
  analyzer: analyze_closed_loop.py OUT --speed S --range RANGE --helper-rc HRC             (ANARGS = --helper-rc, + --expect-dive/--window/--blind-d3-min/--score-final tuy bien)
Bien moi ngoai script hien co: MEASURE_ONLY=1 -> bo cham them --measure-only; DRY_RUN=1.
"""
import os
import shlex
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ONBOARD = os.path.abspath(os.path.join(HERE, ".."))
SCRIPT = os.path.join(ONBOARD, "simtools", "run_closed_loop.sh")

pytestmark = pytest.mark.skipif(os.name == "nt" or shutil.which("bash") is None, reason="can bash (chay pytest trong WSL/Linux)")

CLEAN_VARS = ("SCENARIO", "STRAIGHT", "DIVE_DEG", "DIVE_DROP", "ALT", "EVENT_AT", "BLACKOUT_S", "POST_S", "BLACKOUT_BRAKE",
              "BLIND_D3_MIN", "MEASURE_ONLY", "TARGET_PY", "TARGET_DECEL", "PROFILE", "CONFIG", "RANGE", "CAM_FX", "CAM_TILT",
              "GIMBAL", "SEED", "SPEEDUP", "DRY_RUN", "OUT_ROOT")


def run_dry(tmp_path, speed="10", **env_extra):
    text = open(SCRIPT, encoding="utf-8").read()
    if "DRY_RUN" not in text:
        pytest.fail("run_closed_loop.sh chua ho tro DRY_RUN (khong chay script de tranh khoi dong SITL)")
    env = {k: v for k, v in os.environ.items() if k not in CLEAN_VARS}
    env.update({"DRY_RUN": "1", "OUT_ROOT": str(tmp_path / "out"), "PY": "python3"})
    env.update({k: str(v) for k, v in env_extra.items()})
    r = subprocess.run(["bash", SCRIPT, speed], cwd=ONBOARD, env=env, capture_output=True, text=True, timeout=60)
    return r


def parse(args):
    pos, flags, i = [], {}, 0
    while i < len(args):
        t = args[i]
        if t.startswith("--"):
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                flags[t] = args[i + 1]
                i += 2
            else:
                flags[t] = True
                i += 1
        else:
            pos.append(t)
            i += 1
    return pos, flags


def dry_lines(r):
    def get(prefix, script):
        ls = [ln for ln in r.stdout.splitlines() if ln.startswith(prefix)]
        assert len(ls) == 1, (prefix, r.stdout, r.stderr)
        toks = shlex.split(ls[0][len(prefix):])
        idx = next(i for i, t in enumerate(toks) if t.endswith(script))
        return toks[idx + 1:]
    return get("DRY_RUN helper:", "sim_helper.py"), get("DRY_RUN analyzer:", "analyze_closed_loop.py")


# ---------------------------------------------------------------- khong dat bien moi -> dong lenh nhu hien tai
def test_dry_run_without_new_vars_matches_current_command_lines(tmp_path):
    r = run_dry(tmp_path)
    assert r.returncode == 0, (r.stdout, r.stderr)
    h, an = dry_lines(r)
    assert h[0] == "--out" and h[1].startswith(str(tmp_path / "out")), h
    assert h[2:] == ["--speed", "10", "--scenario", "none", "--range", "15"], h
    assert an[0] == h[1], an                                              # OUT la tham so vi tri dau cua bo cham
    assert an[1:7] == ["--speed", "10", "--range", "15", "--helper-rc", "0"] and len(an) == 7, an


def test_dry_run_creates_nothing_and_exits_zero(tmp_path):
    r = run_dry(tmp_path)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert not (tmp_path / "out").exists() or os.listdir(tmp_path / "out") == [], os.listdir(tmp_path)


def test_dry_run_straight_flag_passthrough(tmp_path):
    h, _ = dry_lines(run_dry(tmp_path, SCENARIO="none", STRAIGHT="1"))
    assert "--straight" in h, h


# ---------------------------------------------------------------- ba kich ban moi + ba ca ham
SC = [
    ("S1_bay_thang", dict(SCENARIO="blackout", STRAIGHT="1", EVENT_AT="30", BLACKOUT_S="8"),
     {"--scenario": "blackout", "--post-s": "15", "--window": "30", "--event-at": "30", "--blackout-s": "8", "--straight": True},
     ["--blackout-dive", "--blackout-brake", "--dive-deg"],
     {"--window": "30"}, ["--expect-dive", "--score-final", "--measure-only", "--blind-d3-min"]),
    ("S2_cam_xuong", dict(SCENARIO="blackout", DIVE_DEG="25", ALT="70", BLACKOUT_S="8"),
     {"--scenario": "blackout", "--post-s": "15", "--window": "40", "--blackout-s": "8", "--blackout-dive": True, "--dive-deg": "25",
      "--dive-drop": "40", "--alt": "70", "--straight": True},
     ["--event-at", "--blackout-brake"],
     {"--window": "40", "--expect-dive": "25"}, ["--score-final", "--measure-only"]),
    ("S3_khong_tro_lai", dict(SCENARIO="blackout", STRAIGHT="1", EVENT_AT="30", BLACKOUT_S="25"),
     {"--scenario": "blackout", "--post-s": "15", "--window": "30", "--event-at": "30", "--blackout-s": "25", "--straight": True},
     ["--blackout-dive", "--blackout-brake"],
     {"--window": "30"}, ["--expect-dive", "--score-final"]),
] + [
    ("ham_%s" % b, dict(SCENARIO="blackout", BLACKOUT_BRAKE=b, EVENT_AT="30", BLACKOUT_S="8"),
     {"--scenario": "blackout", "--post-s": "15", "--window": "30", "--event-at": "30", "--blackout-s": "8", "--blackout-brake": b,
      "--straight": True},
     ["--blackout-dive"],
     {"--window": "30", "--score-final": True}, ["--expect-dive", "--measure-only"])
    for b in ("1.5", "3", "8")
]


@pytest.mark.parametrize("name,env,h_expect,h_absent,a_expect,a_absent", SC, ids=[s[0] for s in SC])
def test_dry_run_new_scenarios_have_exact_flags(tmp_path, name, env, h_expect, h_absent, a_expect, a_absent):
    r = run_dry(tmp_path, **env)
    assert r.returncode == 0, (r.stdout, r.stderr)
    h, an = dry_lines(r)
    _, hf = parse(h)
    _, af = parse(an)
    for k, v in h_expect.items():
        assert hf.get(k) == v, (k, hf)
    for k in h_absent:
        assert k not in hf, (k, hf)
    assert "--helper-rc" in af
    for k, v in a_expect.items():
        assert af.get(k) == v, (k, af)
    for k in a_absent:
        assert k not in af, (k, af)


def test_dry_run_post_s_and_blind_d3_min_and_measure_only(tmp_path):
    h, an = dry_lines(run_dry(tmp_path, SCENARIO="blackout", EVENT_AT="30", BLACKOUT_S="8", POST_S="7", BLIND_D3_MIN="6",
                              MEASURE_ONLY="1"))
    _, hf = parse(h)
    _, af = parse(an)
    assert hf["--post-s"] == "7", hf
    assert af["--blind-d3-min"] == "6" and af["--measure-only"] is True, af


def test_dry_run_measure_only_absent_by_default(tmp_path):
    _, an = dry_lines(run_dry(tmp_path, SCENARIO="blackout", EVENT_AT="30", BLACKOUT_S="8"))
    assert "--measure-only" not in an, an


# ---------------------------------------------------------------- bay thang tu dat STRAIGHT=1
def test_dry_run_blackout_scenario_sets_straight_automatically(tmp_path):
    """Kich ban bay thang co EVENT_AT / BLACKOUT_S, thieu STRAIGHT=1 va khong DIVE_DEG -> helper van nhan --straight."""
    h, _ = dry_lines(run_dry(tmp_path, SCENARIO="blackout", EVENT_AT="30", BLACKOUT_S="8"))
    assert "--straight" in h, h
    h2, _ = dry_lines(run_dry(tmp_path / "b", SCENARIO="blackout", BLACKOUT_S="25"))
    assert "--straight" in h2, h2


# ---------------------------------------------------------------- gia tri sai -> thoat 2 truoc khi khoi dong gi
BAD = [
    dict(SCENARIO="blackout", EVENT_AT="abc"),
    dict(SCENARIO="blackout", EVENT_AT="-5"),
    dict(SCENARIO="blackout", EVENT_AT="0"),
    dict(SCENARIO="blackout", BLACKOUT_S="0"),
    dict(SCENARIO="blackout", BLACKOUT_S="x"),
    dict(SCENARIO="blackout", POST_S="-1"),
    dict(SCENARIO="blackout", BLACKOUT_BRAKE="0"),
    dict(SCENARIO="blackout", BLACKOUT_BRAKE="-2"),
    dict(SCENARIO="blackout", BLIND_D3_MIN="-1"),
    dict(SCENARIO="blackout", BLIND_D3_MIN="abc"),
    dict(SCENARIO="none", EVENT_AT="30"),                                  # bien kich ban moi ngoai SCENARIO=blackout
    dict(SCENARIO="none", BLACKOUT_BRAKE="3"),
    dict(SCENARIO="blackout", BLACKOUT_BRAKE="3", DIVE_DEG="25"),         # ham cung cam xuong
]


@pytest.mark.parametrize("env", BAD, ids=["-".join("%s=%s" % kv for kv in e.items()) for e in BAD])
def test_dry_run_invalid_values_exit_2_before_anything(tmp_path, env):
    r = run_dry(tmp_path, **env)
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "DRY_RUN helper:" not in r.stdout and "DRY_RUN analyzer:" not in r.stdout, r.stdout
    assert not (tmp_path / "out").exists() or os.listdir(tmp_path / "out") == []


def test_dry_run_blind_d3_min_zero_is_valid(tmp_path):
    r = run_dry(tmp_path, SCENARIO="blackout", EVENT_AT="30", BLACKOUT_S="8", BLIND_D3_MIN="0")
    assert r.returncode == 0, (r.stdout, r.stderr)
    _, an = dry_lines(r)
    assert parse(an)[1]["--blind-d3-min"] == "0", an
