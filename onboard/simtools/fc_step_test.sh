#!/usr/bin/env bash
# Phep thu bac dap ung van toc FC (1 SITL, instance 1). Dung: fc_step_test.sh  -> out/<ts>_fcstep/{steps.csv,result.txt}
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM="$(cd "$HERE/../../sim" && pwd)"
PY="${PY:-$HOME/venv-ardupilot/bin/python}"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="$HERE/out/${TS}_fcstep"; RUN="$HOME/sitl_run/fcstep_$TS"
if pgrep -x arducopter >/dev/null; then echo "co arducopter khac dang chay" >&2; exit 3; fi
mkdir -p "$OUT" "$RUN"; echo "out: $OUT"
"$SIM/run_sitl.sh" 1 "-35.3633957,149.165230,584,0" "$RUN" 1 > "$OUT/sitl.log" 2>&1 &
SP=$!
trap 'kill $SP 2>/dev/null; sleep 1; kill -9 $SP 2>/dev/null' EXIT
(cd "$HERE/.." && timeout 400 "$PY" simtools/fc_step_test.py --out "$OUT") 2>&1 | tee "$OUT/result.txt"