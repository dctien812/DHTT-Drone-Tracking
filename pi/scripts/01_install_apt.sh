#!/bin/bash
set -x
sudo -n true && echo SUDO_OK
dpkg -l | awk '/^ii/{print $2}' | sort > /tmp/pkgs_before.txt
df -B1 --output=used / | tail -1 > /tmp/disk_before.txt
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev libgl1 libglib2.0-0
dpkg -l | awk '/^ii/{print $2}' | sort > /tmp/pkgs_after.txt
comm -13 /tmp/pkgs_before.txt /tmp/pkgs_after.txt > ~/dtrack_apt_installed.txt
mkdir -p ~/dtrack && python3 -m venv ~/dtrack/venv
~/dtrack/venv/bin/pip install -q --upgrade pip
df -h / | tail -1
cat ~/dtrack_apt_installed.txt | wc -l