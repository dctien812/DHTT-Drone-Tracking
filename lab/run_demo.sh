#!/usr/bin/env bash
# Chay man hinh lab voi video mau (chi localhost). Dung: bash run_demo.sh [duong_dan_video] [cong]
# Mo http://localhost:<cong>/ tren trinh duyet Windows. Ctrl+C de dung.
set -e
cd "$(dirname "$0")"
VIDEO="${1:-/mnt/d/Personal/DHTT-TRACKING-TEST/AI-6/video/V_DRONE_001.mp4}"
PORT="${2:-8080}"
exec "$HOME/venv-vision/bin/python" -m labview --source "file:$VIDEO" --port "$PORT"
