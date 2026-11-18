#!/usr/bin/env bash
# Chay lo nghiem thu vong kin voi ho so co ten (mac dinh accept_gimbal_r25: khop gat + giu 25 m), muc tieu bay thang 10 m/s.
# Dung: run_acceptance.sh            (chay MATRIX mac dinh)
#       MATRIX="1:none 2:none" run_acceptance.sh   (chay lai mot phan)
# Moi muc cua MATRIX = seed:kich_ban[:che_do]; che_do = soft (muc tieu phanh mem, TARGET_DECEL m/s^2, mac dinh 4)
#   hoac diveNN (NN nguyen duong; che do khac -> bao loi, thoat 2 truoc khi chay gi) (muc tieu bay thang roi cam NN do, do cao hanh trinh 70 m, ha 40 m, cuoi chuyen giam toc 1.5 m/s^2; kich_ban phai la none;
#   cham them pha cam + pha giam toc cuoi, xem docs/scenario_dive.md). Vi du: MATRIX="1:none:dive15 1:none:dive25".
# Mac dinh: 3 seed x dive15, 3 seed x dive25, blackout, disengage (ma tran cu: MATRIX="1:none 2:none 3:none 1:blackout 1:disengage 1:none:soft").
# PASS = ma thoat 0 VA result.txt co "KET QUA: PASS" (thieu thu muc/result.txt -> FAIL).
# An toan: kiem out/_STOP truoc moi lan (co -> thoat), ghi PID vao out/_matrix.pid, ghi uptime truoc moi lan,
# sau moi lan kiem pgrep arducopter trong (khac trong -> dung). Khong xoa gi trong out/.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_ROOT="${OUT_ROOT:-$HERE/out}"
PY="${PY:-$HOME/venv-ardupilot/bin/python}"
PROFILE="${PROFILE:-accept_gimbal_r25}"
SPEED="${SPEED_MS:-10}"
MATRIX="${MATRIX:-1:none:dive15 2:none:dive15 3:none:dive15 1:none:dive25 2:none:dive25 3:none:dive25 1:blackout 1:disengage}"
TARGET_DECEL="${TARGET_DECEL:-4}"
for spec in $MATRIX; do   # kiem TOAN BO ma tran TRUOC khi khoi dong gi (cung dieu kien voi run_closed_loop.sh); sai -> loi, thoat 2
  IFS=: read -r _s _k mode <<<"$spec"
  if [ -n "$mode" ] && [ "$mode" != "soft" ] && ! [[ "$mode" =~ ^dive[1-9][0-9]*$ ]]; then
    echo "che do khong hop le '$mode' trong '$spec' (chi: soft, diveNN voi NN nguyen duong, vd dive15): thoat, khong chay gi" >&2
    exit 2
  fi
  if [[ "$mode" =~ ^dive([0-9]+)$ ]]; then
    [ "$_k" = "none" ] || { echo "'$spec': dive chi di voi kich ban none (khong chay gi)" >&2; exit 2; }
    awk -v s="$SPEED" -v d="${BASH_REMATCH[1]}" 'BEGIN{exit !(d>0 && d<90 && s*sin(d*3.14159265/180)<=5.0)}' \
      || { echo "'$spec': goc ${BASH_REMATCH[1]} voi $SPEED m/s cho toc do xuong > 5 m/s (WP_SPD_DN) hoac goc khong hop le (khong chay gi)" >&2; exit 2; }
  fi
done
mkdir -p "$OUT_ROOT"
echo "$$" > "$OUT_ROOT/_matrix.pid"
SUM="$OUT_ROOT/_acceptance_$(date +%Y%m%d_%H%M%S).txt"
echo "ho so=$PROFILE toc do=$SPEED matrix=$MATRIX" | tee -a "$SUM"

summarize() {   # $1 = thu muc ket qua, $2 = ma thoat analyzer, $3 = seed, $4 = kich ban/nhan
  "$PY" - "$1" "$2" "$3" "$4" <<'EOF' | tee -a "$SUM"
import json, os, re, sys
d, rc, seed, tag = sys.argv[1:5]
rp = os.path.join(d, "result.txt") if d and os.path.isdir(d) else None   # khong thay thu muc -> KHONG doc result.txt cua thu muc hien hanh
txt = open(rp).read() if rp and os.path.exists(rp) else ""
def f(p):
    m = re.search(p, txt)
    return m.group(1) if m else "?"
res = {}
m = re.search(r"B4JSON (\{.*\})", txt)
if m:
    res = json.loads(m.group(1))
phases = {k: v for k, v in res.items() if isinstance(v, dict) and "min_d3" in v}
ph = min(phases, key=lambda k: phases[k]["min_d3"]) if phases else "?"
cam = res.get("cam_xuong", {})
fin = res.get("giam_toc_cuoi", res.get("phanh_cuoi", {}))
print("%s | seed %s | %s | TB %s m | min %s m t_rel %s s pha %s | TRACK %s%% | ra khung %s lan | cam: d3 %s..%s m ra khung %s s | cuoi: d3 %s..%s m ra khung %s s | rc %s | %s" % (
    os.path.basename(d) if rp else "(khong thay thu muc ket qua)", seed, tag, f(r"sai so \|d-\d+\|: TB ([\d.]+)"), f(r"min d3 toan chuyen bay = ([\d.]+)"),
    f(r"\(t_rel=([\d.]+)\)"), ph, f(r"supervisor TRACK ([\d.]+)%"), res.get("out_total_n", "?"),
    "%.1f" % cam["min_d3"] if cam else "-", "%.1f" % cam["max_d3"] if cam else "-", "%.2f" % cam["out_s"] if cam else "-",
    "%.1f" % fin["min_d3"] if fin else "?", "%.1f" % fin["max_d3"] if fin and "max_d3" in fin else "?", "%.2f" % fin["out_s"] if fin else "?", rc,
    "PASS" if rc == "0" and "KET QUA: PASS" in txt else "FAIL"))
EOF
}

n=0
for spec in $MATRIX; do
  IFS=: read -r seed scen mode <<<"$spec"
  if [ -e "$OUT_ROOT/_STOP" ]; then echo "co $OUT_ROOT/_STOP: thoat" | tee -a "$SUM"; exit 5; fi
  n=$((n+1))   # tang o shell chinh (dat trong pipe voi tee thi mat, moi lan deu ghi de _acc_run_0.log)
  echo "--- lan $n: $spec ; $(uptime)" | tee -a "$SUM"
  extra=()
  if [ "$mode" = "soft" ]; then extra=(TARGET_PY="$HERE/target_softbrake.py" TARGET_DECEL="$TARGET_DECEL")
  elif [[ "$mode" =~ ^dive([0-9]+)$ ]]; then extra=(DIVE_DEG="${BASH_REMATCH[1]}"); fi   # cam xuong (scen phai la none), giam toc cuoi nhe
  env STRAIGHT=1 PROFILE="$PROFILE" SEED="$seed" SCENARIO="$scen" OUT_ROOT="$OUT_ROOT" "${extra[@]}" \
    bash "$HERE/run_closed_loop.sh" "$SPEED" > "$OUT_ROOT/_acc_run_$n.log" 2>&1
  rc=$?
  d="$(grep -m1 '^out: ' "$OUT_ROOT/_acc_run_$n.log" | sed 's/^out: //' | tr -d '\r')"
  summarize "$d" "$rc" "$seed" "$scen${mode:+/$mode}"
  sleep 3
  if pgrep -x arducopter >/dev/null; then echo "CON arducopter sau lan $n: dung lo" | tee -a "$SUM"; exit 6; fi
done
echo "xong $n lan; pgrep arducopter: $(pgrep -x arducopter | wc -l) tien trinh" | tee -a "$SUM"
