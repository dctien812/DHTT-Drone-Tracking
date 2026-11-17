#!/bin/bash
uptime; nproc; free -m | head -2
cat /etc/os-release | head -3
ls /dev/dxg; echo DISPLAY=$DISPLAY WAYLAND=$WAYLAND_DISPLAY
which gz glxinfo gst-launch-1.0 cmake; dpkg -l | grep -E "^ii\s+(gz-|libgz|gstreamer1.0-plugins-good|libopencv-dev|rapidjson)" | head
python3 --version
df -h ~ | tail -1
ls ~