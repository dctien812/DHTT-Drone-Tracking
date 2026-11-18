#!/bin/bash
set -x
V=~/dtrack/venv
$V/bin/python -V; $V/bin/pip --version
dpkg -l libgl1 libglib2.0-0 python3-dev 2>&1 | tail -4
df -B1 --output=used / | tail -1 > ~/dtrack/disk_before_pip.txt
$V/bin/pip install torch torchvision  2>&1 | tail -3