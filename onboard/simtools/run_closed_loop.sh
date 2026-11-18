#!/usr/bin/env bash
# Vong kin SITL: 2 SITL (target + chaser) + target.py (sim/) + sim_helper.py + dtrack.app --auto-engage.
# Dung: run_closed_loop.sh <toc_do_target_m/s>
# Bien moi truong: SEED (mac dinh 1, seed bo phat hien tong hop), SCENARIO (none|blackout|disengage),
#   STRAIGHT=1 (muc tieu bay thang, khong re: target.py --first-turn rat lon), SPEEDUP (mac dinh 1),
#   CAM_FX (px), CAM_TILT (do), GIMBAL=1 (khop gat on dinh pitch) -> ghi $OUT/app_cfg.json, analyzer doc lai de tinh hinh hoc camera.
#   RANGE (15; khoang cach dat, truyen cho helper, bo cham VA app qua file cau hinh tam neu CONFIG khong dat), CONFIG (file TOML/JSON cua app, tuy chon), MAX_WALL (giay that, 900),
#   PROFILE (ten ho so cau hinh trong dtrack/config.py PROFILES, vd accept_gimbal_r25; ghi de RANGE/CONFIG),
#   TARGET_PY (script muc tieu, mac dinh sim/target.py; ca phanh mem: simtools/target_softbrake.py voi TARGET_DECEL m/s^2),
#   DIVE_DEG (>0: ca cam xuong, vd 15 hoac 25 do; xem docs/scenario_dive.md), DIVE_DROP (m ha xuong, 40), ALT (do cao hanh trinh m, 70 khi DIVE_DEG>0),
#   OUT_ROOT (mac dinh onboard/simtools/out).
# Chi kill cac PID do chinh script nay tao (khong pkill). Khong goi sim/run_chase.sh.
# Exit code = exit code cua analyze_closed_loop.py (0 PASS, 1 FAIL); app thoat khac 0 -> FAIL.
set -uo pipefail

SPEED="${1:?cach dung: run_closed_loop.sh <toc_do m/s>}"
SEED="${SEED:-1}"
SCENARIO="${SCENARIO:-none}"
SPEEDUP="${SPEEDUP:-1}"
RANGE="${RANGE:-15}"
MAX_WALL="${MAX_WALL:-900}"
PY="${PY:-$HOME/venv-ardupilot/bin/python}"
# PROFILE=<ten ho so trong dtrack/config.py PROFILES>: cau hinh app lay tu ho so; RANGE lay theo ho so
PROFILE="$(printf '%s' "${PROFILE:-}" | tr -d '\r\n')"
if [ -n "$PROFILE" ]; then
  RANGE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && "$PY" -c 'import sys;from dtrack.config import profile_dict;print(profile_dict(sys.argv[1])["guidance"]["range_set_m"])' "$PROFILE")" \
    || { echo "ho so khong hop le: $PROFILE" >&2; exit 4; }
fi
# bo CR/LF dinh vao tham so (lenh goi tu Windows co the dinh CRLF) de ten thu muc ket qua khong co '\r'
STRAIGHT="${STRAIGHT:-0}"
DIVE_DEG="${DIVE_DEG:-0}"; DIVE_DROP="${DIVE_DROP:-40}"; ALT="${ALT:-}"
for _v in SPEED SEED SCENARIO SPEEDUP RANGE MAX_WALL STRAIGHT DIVE_DEG DIVE_DROP ALT; do
  printf -v "$_v" '%s' "$(printf '%s' "${!_v}" | tr -d '\r\n')"
done
# DIVE_DEG>0: ca CAM XUONG (muc tieu bay thang roi dot ngot cam goc DIVE_DEG, ha DIVE_DROP m, cuoi chuyen giam toc nhe);
# can SCENARIO=none, tu dat STRAIGHT=1, ALT mac dinh 70 (do cao hanh trinh m), TARGET_PY=target_dive.py, TARGET_DECEL mac dinh 1.5
DIVE=0
if [ "$DIVE_DEG" != "0" ]; then
  DIVE=1
  [ "$SCENARIO" = "none" ] || { echo "DIVE_DEG chi di voi SCENARIO=none" >&2; exit 2; }
  # tran toc do xuong cua SITL muc tieu = WP_SPD_DN 5 m/s (freestyle.param): kiem som, khong de target_dive tu choi sau khi SITL da len
  awk -v s="$SPEED" -v d="$DIVE_DEG" 'BEGIN{exit !(d>0 && d<90 && s*sin(d*3.14159265/180)<=5.0)}' \
    || { echo "DIVE_DEG=$DIVE_DEG voi $SPEED m/s cho toc do xuong > 5 m/s (WP_SPD_DN cua SITL muc tieu) hoac goc khong hop le" >&2; exit 2; }
  STRAIGHT=1; ALT="${ALT:-70}"
  export TARGET_DECEL="${TARGET_DECEL:-1.5}"
fi
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ONBOARD="$(cd "$HERE/.." && pwd)"
SIM="$(cd "$ONBOARD/../sim" && pwd)"
PY="${PY:-$HOME/venv-ardupilot/bin/python}"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="${OUT_ROOT:-$HERE/out}/${TS}_${SPEED}ms_s${SEED}_${SCENARIO}"
RUN="${SITL_RUN_DIR:-$HOME/sitl_run}/cl_${TS}_${SPEED}_${SEED}"
HOME_TARGET="-35.363261,149.165230,584,0"
HOME_CHASER="-35.3633957,149.165230,584,0"
export PYTHONDONTWRITEBYTECODE=1

if pgrep -x arducopter >/dev/null; then
  echo "co tien trinh arducopter khac dang chay (khong phai cua script nay); dung lai de khong dung vao no" >&2
  exit 3
fi

PIDS=()
cleanup() {
  for p in "${PIDS[@]:-}"; do
    [ -n "$p" ] && kill "$p" 2>/dev/null || true
  done
  sleep 1
  for p in "${PIDS[@]:-}"; do
    [ -n "$p" ] && kill -9 "$p" 2>/dev/null || true
  done
}
trap cleanup EXIT

mkdir -p "$OUT" "$RUN"
echo "out: $OUT"
cp "$0" "$OUT/run_closed_loop.sh.txt" 2>/dev/null || true

"$SIM/run_sitl.sh" 0 "$HOME_TARGET" "$RUN/target" "$SPEEDUP" > "$OUT/sitl_target.log" 2>&1 &
PIDS+=("$!")
"$SIM/run_sitl.sh" 1 "$HOME_CHASER" "$RUN/chaser" "$SPEEDUP" > "$OUT/sitl_chaser.log" 2>&1 &
PIDS+=("$!")
TARGS=()
[ "$STRAIGHT" = "1" ] && TARGS=(--first-turn 1000000)
[ -n "$ALT" ] && TARGS+=(--alt "$ALT")
HARGS=()
[ -n "$ALT" ] && HARGS+=(--alt "$ALT")
if [ "$DIVE" = "1" ]; then
  TARGS+=(--dive-file "$OUT/dive" --dive-deg "$DIVE_DEG" --dive-drop "$DIVE_DROP")
  HARGS+=(--dive-deg "$DIVE_DEG" --dive-drop "$DIVE_DROP")
  TARGET_PY="${TARGET_PY:-$HERE/target_dive.py}"
fi
TARGET_PY="${TARGET_PY:-$SIM/target.py}"      # TARGET_PY=$HERE/target_softbrake.py (+ TARGET_DECEL) cho ca phanh mem
(cd "$SIM" && exec "$PY" "$TARGET_PY" --speed "$SPEED" "${TARGS[@]}" --go-file "$OUT/go" --stop-file "$OUT/stop") \
  > "$OUT/target.log" 2>&1 &
PIDS+=("$!")

(cd "$ONBOARD" && exec timeout "$MAX_WALL" "$PY" "$HERE/sim_helper.py" --out "$OUT" --speed "$SPEED" \
  --scenario "$SCENARIO" --range "$RANGE" "${HARGS[@]}" $([ "$STRAIGHT" = "1" ] && echo --straight)) > "$OUT/helper.log" 2>&1 &
HELPER=$!
PIDS+=("$HELPER")

# cho chaser vao vi tri xuat phat roi moi chay app
for i in $(seq 1 1200); do
  [ -f "$OUT/ready" ] && break
  kill -0 "$HELPER" 2>/dev/null || { echo "helper chet som" >&2; break; }
  sleep 1
done

APP_RC=99
if [ -f "$OUT/ready" ]; then
  CFGARG=()
  if [ -n "$PROFILE" ]; then
    (cd "$ONBOARD" && "$PY" -c 'import json,sys;from dtrack.config import profile_dict;print(json.dumps(profile_dict(sys.argv[1])))' "$PROFILE") > "$OUT/app_cfg.json"
    CFGARG=(--config "$OUT/app_cfg.json")
  elif [ -n "${CONFIG:-}" ]; then CFGARG=(--config "$CONFIG"); cp "$CONFIG" "$OUT/app_cfg.json" 2>/dev/null || true
  elif [ "$RANGE" != "15" ] || [ -n "${CAM_FX:-}" ] || [ "${GIMBAL:-0}" = "1" ] || [ -n "${CAM_TILT:-}" ]; then
    # cau hinh tam tu bien moi truong: RANGE (khoang cach giu), CAM_FX (tieu cu px), CAM_TILT (do), GIMBAL=1 (khop gat)
    RANGE="$RANGE" "$PY" -c 'import json,os
c={"guidance":{"range_set_m":float(os.environ["RANGE"])}}
cam={}
if os.environ.get("CAM_FX"): cam["fx"]=cam["fy"]=float(os.environ["CAM_FX"])
if os.environ.get("CAM_TILT"): cam["tilt_up_deg"]=float(os.environ["CAM_TILT"])
if os.environ.get("GIMBAL")=="1": cam["gimbal_enabled"]=True
if cam: c["camera"]=cam
print(json.dumps(c))' > "$OUT/app_cfg.json"
    CFGARG=(--config "$OUT/app_cfg.json")
  fi
  (cd "$ONBOARD" && exec "$PY" -m dtrack.app "${CFGARG[@]}" --connect tcp:127.0.0.1:5770 --source sim --auto-engage \
    --sim-target tcp:127.0.0.1:5762 --sim-chaser tcp:127.0.0.1:5773 --sim-seed "$SEED" \
    --sim-blackout-file "$OUT/blackout" --stop-file "$OUT/app_stop" --log "$OUT/app_log.csv") \
    > "$OUT/app.log" 2>&1 &
  APP=$!
  PIDS+=("$APP")
  sleep 1
  touch "$OUT/app_up"
  wait "$HELPER"
  HRC=$?
  # app thoat sau app_stop (phanh tuong minh roi thoat); cho toi 60 s
  for i in $(seq 1 60); do kill -0 "$APP" 2>/dev/null || break; sleep 1; done
  if kill -0 "$APP" 2>/dev/null; then echo "app khong thoat sau 60 s" >> "$OUT/app.log"; kill "$APP"; APP_RC=98
  else wait "$APP"; APP_RC=$?; fi
else
  HRC=97
fi
echo "$APP_RC" > "$OUT/app.rc"
echo "helper rc=$HRC app rc=$APP_RC"
sleep 2
cleanup
PIDS=()

ANARGS=(--helper-rc "$HRC")        # ma thoat helper -> bo cham (khac 0 hoac thieu events.json -> FAIL)
[ "$DIVE" = "1" ] && ANARGS+=(--expect-dive "$DIVE_DEG")    # lan chay cam xuong: thieu events.json/moc -> FAIL
"$PY" "$HERE/analyze_closed_loop.py" "$OUT" --speed "$SPEED" --range "$RANGE" "${ANARGS[@]}" 2>&1 | tee "$OUT/result.txt"
AN_RC="${PIPESTATUS[0]}"
echo "analyze exit code: $AN_RC (thu muc: $OUT)"
exit "$AN_RC"
