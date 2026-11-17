#!/usr/bin/env bash
# Chay tron 1 kich ban chase. Dung: run_chase.sh <toc_do_target_m/s>
# Bien moi truong tuy chon: SPEEDUP (mac dinh 1), MAX_WALL (giay tuong, mac dinh 1200),
#   SITL_RUN_DIR (mac dinh ~/sitl_run, nen o ext4 cua WSL), PY (python cua venv).
# Exit code = exit code cua analyze.py (0 = PASS, 1 = FAIL).
set -euo pipefail

SPEED="${1:?cach dung: run_chase.sh <toc_do m/s>}"
SPEEDUP="${SPEEDUP:-1}"
MAX_WALL="${MAX_WALL:-1200}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-$HOME/venv-ardupilot/bin/python}"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="$HERE/out/${TS}_${SPEED}ms"
RUN="${SITL_RUN_DIR:-$HOME/sitl_run}/${TS}_${SPEED}ms"
# Phai khop voi TARGET_HOME / CHASER_HOME trong chaselib.py (chaser cach target 15 m ve phia nam)
HOME_TARGET="-35.363261,149.165230,584,0"
HOME_CHASER="-35.3633957,149.165230,584,0"
export PYTHONDONTWRITEBYTECODE=1

PIDS=()
cleanup() {
  for p in "${PIDS[@]:-}"; do
    [ -n "$p" ] && kill "$p" 2>/dev/null || true
  done
  sleep 1
  pkill -x arducopter 2>/dev/null || true
}
trap cleanup EXIT

# don tien trinh cu cua chinh bo script nay (khong dung vao ./waf hay setup_wsl.sh)
pkill -x arducopter 2>/dev/null || true
pkill -f "$HERE/target.py" 2>/dev/null || true
pkill -f "$HERE/chaser.py" 2>/dev/null || true
sleep 1

mkdir -p "$OUT" "$RUN"
echo "out: $OUT"
echo "sitl workdir: $RUN"

"$HERE/run_sitl.sh" 0 "$HOME_TARGET" "$RUN/target" "$SPEEDUP" > "$OUT/sitl_target.log" 2>&1 &
PIDS+=("$!")
"$HERE/run_sitl.sh" 1 "$HOME_CHASER" "$RUN/chaser" "$SPEEDUP" > "$OUT/sitl_chaser.log" 2>&1 &
PIDS+=("$!")

"$PY" "$HERE/target.py" --speed "$SPEED" --go-file "$OUT/go" --stop-file "$OUT/stop" \
  > "$OUT/target.log" 2>&1 &
PIDS+=("$!")

set +e
timeout "$MAX_WALL" "$PY" "$HERE/chaser.py" --speed "$SPEED" --csv "$OUT/chase.csv" \
  --go-file "$OUT/go" --stop-file "$OUT/stop" 2>&1 | tee "$OUT/chaser.log"
CH_RC="${PIPESTATUS[0]}"
echo "chaser exit code: $CH_RC"
sleep 2
cleanup
PIDS=()

"$PY" "$HERE/analyze.py" "$OUT/chase.csv" --speed "$SPEED" 2>&1 | tee "$OUT/result.txt"
AN_RC="${PIPESTATUS[0]}"
for d in target chaser; do
  cp -r "$RUN/$d/logs" "$OUT/logs_$d" 2>/dev/null || true
done
echo "analyze exit code: $AN_RC (thu muc: $OUT)"
exit "$AN_RC"
