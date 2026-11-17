cd /mnt/d/Personal/Drone-Tracking/cad/tilt_mount
~/venv-cad/bin/python -m pytest -q -x -p no:cacheprovider tests 2>&1 | tail -40
