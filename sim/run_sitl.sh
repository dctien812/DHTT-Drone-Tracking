#!/usr/bin/env bash
# Khoi dong 1 instance ArduCopter SITL headless (binary truc tiep, khong MAVProxy).
# Dung: run_sitl.sh <instance 0|1> <home lat,lon,alt,yaw> <workdir> [speedup]
#   instance I -> sysid I+1 (MAV_SYSID), cong TCP: SERIAL0 = 5760+10*I (SITL doi ket noi o day),
#   SERIAL1 = 5762+10*I. Moi instance chay trong <workdir> rieng (eeprom.bin, logs/).
set -euo pipefail

INST="${1:?instance}"
HOME_LOC="${2:?home lat,lon,alt,yaw}"
WORKDIR="${3:?workdir}"
SPEEDUP="${4:-1}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AP="${ARDUPILOT_DIR:-$HOME/ardupilot}"
BIN="$AP/build/sitl/bin/arducopter"
[ -x "$BIN" ] || { echo "Chua co binary $BIN" >&2; exit 1; }

mkdir -p "$WORKDIR"
cd "$WORKDIR"
# -w xoa eeprom de moi lan chay deu sach.
# Mo hinh vat ly: freestyle quad 0.8 kg cua ArduPilot (ROMFS, drag 20 m/s @ 45 do, hover 0.125). Mo hinh '+' mac dinh
# (hover 0.39) chi bay duoc ~18.4 m/s (do thuc te), khong du cho kich ban B. Tham so di kem: models/freestyle.param.
# Dinh dang model "<frame>:@ROMFS/<json>" theo Tools/autotest/pysim/vehicleinfo.py:240 (duong dan tuyet doi
# toi file json bi SITL tu choi: PANIC "failed to load", da thu).
exec "$BIN" -w --model "X:@ROMFS/models/freestyle.json" --speedup "$SPEEDUP" --home "$HOME_LOC" \
  -I "$INST" --sysid "$((INST + 1))" \
  --defaults "$AP/Tools/autotest/default_params/copter.parm,$AP/Tools/autotest/default_params/copter-X.parm,$AP/Tools/autotest/models/freestyle.param,$HERE/chase.parm"