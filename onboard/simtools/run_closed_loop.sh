#!/usr/bin/env bash
# Vong kin SITL: 2 SITL (target + chaser) + target.py (sim/) + sim_helper.py + dtrack.app --auto-engage.
# Dung: run_closed_loop.sh <toc_do_target_m/s>
# Bien moi truong: SEED (mac dinh 1, seed bo phat hien tong hop), SCENARIO (none|blackout|disengage),
#   SPEEDUP (mac dinh 1), RANGE (15), CONFIG (file TOML/JSON cua app, tuy chon), MAX_WALL (giay that, 900),
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
(cd "$SIM" && exec "$PY" "$SIM/target.py" --speed "$SPEED" --go-file "$OUT/go" --stop-file "$OUT/stop") \
  > "$OUT/target.log" 2>&1 &
PIDS+=("$!")

(cd "$ONBOARD" && exec timeout "$MAX_WALL" "$PY" "$HERE/sim_helper.py" --out "$OUT" --speed "$SPEED" \
  --scenario "$SCENARIO" --range "$RANGE") > "$OUT/helper.log" 2>&1 &
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
  [ -n "${CONFIG:-}" ] && CFGARG=(--config "$CONFIG")
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

"$PY" "$HERE/analyze_closed_loop.py" "$OUT" --speed "$SPEED" --range "$RANGE" 2>&1 | tee "$OUT/result.txt"
AN_RC="${PIPESTATUS[0]}"
echo "analyze exit code: $AN_RC (thu muc: $OUT)"
exit "$AN_RC"
