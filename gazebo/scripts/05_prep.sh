#!/bin/bash
python3 - <<'EOF'
import cv2
print(cv2.__version__, [l.strip() for l in cv2.getBuildInformation().splitlines() if "GStreamer" in l])
EOF
gst-inspect-1.0 x264enc | head -3; gst-inspect-1.0 avdec_h264 | head -3
sudo apt-get install -y python3-venv >/dev/null 2>&1
[ -d ~/venv-gazebo ] || python3 -m venv --system-site-packages ~/venv-gazebo
~/venv-gazebo/bin/pip install pymavlink 2>&1 | tail -1
~/venv-gazebo/bin/python -c "import pymavlink, cv2, gi; print('ok', pymavlink.__file__)"
ls ~/ardupilot/build/sitl/bin/; ~/ardupilot/build/sitl/bin/arducopter --help 2>&1 | grep -i -E "model|defaults|speedup|sim-address|-I" | head
ls ~/ardupilot/Tools/autotest/default_params | grep -i -E "gazebo|^copter.parm"