#!/usr/bin/env bash
# Cai ArduPilot SITL (Copter) trong WSL2 Ubuntu 24.04. Chay lai duoc nhieu lan.
# Dung: wsl -d Ubuntu-24.04 -- bash /mnt/d/Personal/Drone-Tracking/sim/setup_wsl.sh
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

AP_DIR="$HOME/ardupilot"
AP_BRANCH="Copter-4.7.2"   # tag ban on dinh (khong co nhanh Copter-4.6)

sudo apt-get update -y
sudo apt-get install -y git python3-pip python3-venv

if [ ! -d "$AP_DIR/.git" ]; then
  git clone --depth 1 --branch "$AP_BRANCH" --recurse-submodules --shallow-submodules \
    https://github.com/ArduPilot/ardupilot.git "$AP_DIR"
fi

cd "$AP_DIR"
# Script chinh thuc cua ArduPilot: cai trinh bien dich, tao venv, cai pymavlink/MAVProxy
USER="$(whoami)" Tools/environment_install/install-prereqs-ubuntu.sh -y

# Nap moi truong (venv + PATH) ma script tren vua ghi vao ~/.profile
set +u
. "$HOME/.profile"
set -u

./waf configure --board sitl
./waf copter

ls -la build/sitl/bin/arducopter
echo "SETUP_OK"
