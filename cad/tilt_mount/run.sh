set -e
cd /mnt/d/Personal/Drone-Tracking/cad/tilt_mount
~/venv-cad/bin/python tilt_mount.py 2>&1 | grep -v -i warn
~/venv-cad/bin/python render.py
