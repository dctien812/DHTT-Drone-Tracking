#!/bin/bash
set -x
sudo apt-get update
sudo apt-get install -y curl lsb-release gnupg mesa-utils
sudo curl -sSL https://packages.osrfoundation.org/gazebo.gpg -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/gazebo-stable.list
sudo apt-get update
dpkg-query -W -f='${Package}\n' | sort > /tmp/pkgs_before.txt
sudo apt-get install -y gz-harmonic
sudo apt-get install -y libgz-sim8-dev rapidjson-dev libopencv-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-gl gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly python3-gz-transport13 python3-gz-msgs10 python3-gi gir1.2-gst-plugins-base-1.0 python3-opencv python3-numpy cmake build-essential
dpkg-query -W -f='${Package}\n' | sort > /tmp/pkgs_after.txt
mkdir -p ~/gazebo_logs
comm -13 /tmp/pkgs_before.txt /tmp/pkgs_after.txt > ~/gazebo_logs/installed_pkgs.txt
wc -l ~/gazebo_logs/installed_pkgs.txt
echo INSTALL_DONE