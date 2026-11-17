#!/usr/bin/env bash
# Kiem chung chay that bang curl: bash e2e_check.sh <video> <thu_muc_ra> [cong] [luu_anh=1]
# Khoi dong may chu (chi localhost), thu cac diem cuoi, do hieu nang, roi TAT may chu.
VIDEO="$1"; OUT="$2"; PORT="${3:-8765}"; SAVE="${4:-1}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="$HOME/venv-vision/bin/python"
mkdir -p "$OUT"
URL="http://127.0.0.1:$PORT"
cd "$HERE"
"$PY" -m labview --source "file:$VIDEO" --port "$PORT" $EXTRA_ARGS --log-file "$OUT/server.log" >"$OUT/stdout.log" 2>&1 &
PID=$!
echo "$PID" > "$OUT/server.pid"
echo "server PID=$PID"
cleanup() { kill "$PID" 2>/dev/null; for _ in $(seq 1 20); do kill -0 "$PID" 2>/dev/null || break; sleep 0.5; done; kill -9 "$PID" 2>/dev/null; echo "server stopped, alive? $(kill -0 $PID 2>/dev/null && echo YES || echo no)"; }
trap cleanup EXIT

for _ in $(seq 1 120); do
  curl -s "$URL/api/state" | grep -q '"running":true' && break
  kill -0 "$PID" 2>/dev/null || { echo "server died"; tail -20 "$OUT/stdout.log"; exit 1; }
  sleep 1
done
echo "--- GET / ---"; curl -s -o /dev/null -w "http=%{http_code} bytes=%{size_download}\n" "$URL/"; curl -s "$URL/" | grep -o '<title>[^<]*</title>'
echo "--- stream frames in 10 s ---"
N=$(curl -s --max-time 10 "$URL/stream.mjpg" | grep -a -c '^--frame'); echo "frames=$N"
echo "--- wait for a track ---"
for _ in $(seq 1 60); do
  S=$(curl -s "$URL/api/state"); echo "$S" | grep -q '"tracks":\[{' && break; sleep 0.5
done
echo "$S" | "$PY" -c "import sys,json; s=json.load(sys.stdin); print('tracks:',s['tracks']); print('lock:',s['lock'])"
[ "$SAVE" = 1 ] && curl -s "$URL/snapshot.jpg" -o "$OUT/before.jpg"
echo "--- lock ---"
curl -s -X POST -H 'Content-Type: application/json' -d '{"best":true}' "$URL/api/lock"; echo
sleep 0.6
curl -s "$URL/api/state" | "$PY" -c "import sys,json; s=json.load(sys.stdin); print('lock:',s['lock'])"
[ "$SAVE" = 1 ] && curl -s "$URL/snapshot.jpg" -o "$OUT/after.jpg"
echo "--- perf 10 s (lock dang bat) ---"
"$PY" - "$PID" "$URL" <<'EOF'
import sys, time, json, urllib.request, psutil
p = psutil.Process(int(sys.argv[1])); p.cpu_percent(None); time.sleep(10)
cpu = p.cpu_percent(None)
s = json.load(urllib.request.urlopen(sys.argv[2] + "/api/state"))
print(f"cpu_total_percent_of_one_core={cpu:.0f} (16 logical cores) fps={s['fps']} infer_ms={s['infer_ms']} latency_ms={s['latency_ms']} size={s['source']['width']}x{s['source']['height']}")
EOF
echo "--- release ---"
curl -s -X POST -H 'Content-Type: application/json' -d '{}' "$URL/api/release"; echo
sleep 0.6
curl -s "$URL/api/state" | "$PY" -c "import sys,json; s=json.load(sys.stdin); print('lock:',s['lock']); print('events:'); [print(' ',e['ts'],e['msg']) for e in s['events']]"
echo "--- ket noi mang cua tien trinh ---"
ss -tnp 2>/dev/null | grep "pid=$PID" || echo "(khong co ket noi TCP nao cua tien trinh den luc nay)"
