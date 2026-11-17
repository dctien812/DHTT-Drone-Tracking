#!/bin/bash
set -x
grep -E "^E:|Unable to locate" ~/gazebo_install.log | head
gz sim --versions
cd ~ && [ -d ardupilot_gazebo ] || git clone https://github.com/ArduPilot/ardupilot_gazebo
cd ~/ardupilot_gazebo && git log -1 --format=%H
export GZ_VERSION=harmonic
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo && make -j6
ls ~/ardupilot_gazebo/build/*.so
echo BUILD_DONE