#!/usr/bin/env bash
# Chay lo nghiem thu vong kin voi ho so co ten (mac dinh accept_gimbal_r25: khop gat + giu 25 m), muc tieu bay thang 10 m/s.
# Dung: run_acceptance.sh            (chay MATRIX mac dinh)
#       MATRIX="1:none 2:none" run_acceptance.sh   (chay lai mot phan)
# Moi muc cua MATRIX = seed:kich_ban[:soft]  (soft = muc tieu phanh mem, TARGET_DECEL m/s^2, mac dinh 4).
# Mac dinh: 3 seed x 2 lan none, blackout, disengage, ca phanh mem.
# An toan: kiem out/_STOP truoc moi lan (co -> thoat), ghi PID vao out/_matrix.pid, ghi uptime truoc moi lan,
# sau moi lan kiem pgrep arducopter trong (khac trong -> dung). Khong xoa gi trong out/.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_ROOT="${OUT_ROOT:-$HERE/out}"
PY="${PY:-$HOME/venv-ardupilot/bin/python}"
PROFILE="${PROFILE:-accept_gimbal_r25}"
SPEED="${SPEED_MS:-10}"
MATRIX="${MATRIX:-1:none 2:none 3:none 1:none 2:none 3:none 1:blackout 1:disengage 1:none:soft}"
TARGET_DECEL="${TARGET_DECEL:-4}"
mkdir -p "$OUT_ROOT"
echo "$$" > "$OUT_ROOT/_matrix.pid"
SUM="$OUT_ROOT/_acceptance_$(date +%Y%m%d_%H%M%S).txt"
echo "ho so=$PROFILE toc do=$SPEED matrix=$MATRIX" | tee -a "$SUM"

summarize() {   # $1 = thu muc ket qua, $2 = ma thoat analyzer, $3 = seed, $4 = kich ban/nhan
  "$PY" - "$1" "$2" "$3" "$4" <<'EOF' | tee -a "$SUM"
import json, os, re, sys
d, rc, seed, tag = sys.argv[1:5]
txt = open(os.path.join(d, "result.txt")).read() if os.path.exists(os.path.join(d, "result.txt")) else ""
def f(p):
    m = re.search(p, txt)
    return m.group(1) if m else "?"
res = {}
m = re.search(r"B4JSON (\{.*\})", txt)
if m:
    res = json.loads(m.group(1))
phases = {k: v for k, v in res.items() if isinstance(v, dict) and "min_d3" in v}
ph = min(phases, key=lambda k: phases[k]["min_d3"]) if phases else "?"
print("%s | seed %s | %s | TB %s m | min %s m t_rel %s s pha %s | TRACK %s%% | ra khung %s lan | rc %s | %s" % (
    os.path.basename(d), seed, tag, f(r"sai so \|d-\d+\|: TB ([\d.]+)"), f(r"min d3 toan chuyen bay = ([\d.]+)"),
    f(r"\(t_rel=([\d.]+)\)"), ph, f(r"supervisor TRACK ([\d.]+)%"), res.get("out_total_n", "?"), rc,
    "PASS" if rc == "0" else "FAIL"))
EOF
}

n=0
for spec in $MATRIX; do
  IFS=: read -r seed scen mode <<<"$spec"
  if [ -e "$OUT_ROOT/_STOP" ]; then echo "co $OUT_ROOT/_STOP: thoat" | tee -a "$SUM"; exit 5; fi
  echo "--- lan $((++n)): $spec ; $(uptime)" | tee -a "$SUM"
  extra=()
  if [ "$mode" = "soft" ]; then extra=(TARGET_PY="$HERE/target_softbrake.py" TARGET_DECEL="$TARGET_DECEL"); fi
  env STRAIGHT=1 PROFILE="$PROFILE" SEED="$seed" SCENARIO="$scen" OUT_ROOT="$OUT_ROOT" "${extra[@]}" \
    bash "$HERE/run_closed_loop.sh" "$SPEED" > "$OUT_ROOT/_acc_run_$n.log" 2>&1
  rc=$?
  d="$(grep -m1 '^out: ' "$OUT_ROOT/_acc_run_$n.log" | sed 's/^out: //' | tr -d '\r')"
  summarize "$d" "$rc" "$seed" "$scen${mode:+/$mode}"
  sleep 3
  if pgrep -x arducopter >/dev/null; then echo "CON arducopter sau lan $n: dung lo" | tee -a "$SUM"; exit 6; fi
done
echo "xong $n lan; pgrep arducopter: $(pgrep -x arducopter | wc -l) tien trinh" | tee -a "$SUM"
