# Gazebo Harmonic + ArduPilot SITL trong WSL2 (spike 2026-11-17)

Ket luan: chay duoc, dung hinh bang card (D3D12 -> RX 9060 XT) va bang CPU (llvmpipe). Camera 640x480 ~10 fps ra Python.

## Cai tai lap (distro Ubuntu-24.04, user drone)
Chay lan luot (trong `scripts\`): `01_install.sh` (kho apt OSRF + gz-harmonic + phu thuoc), `02_build.sh` (clone + build ardupilot_gazebo, commit f116b03),
`05_prep.sh` (gstreamer1.0-tools, python3-venv, venv `~/venv-gazebo --system-site-packages` + pymavlink).
Goi: xem `results\installed_pkgs.txt` (680 goi, gom ca phu thuoc; chup SAU khi cai mesa-utils/curl/gnupg/lsb-release).
Cai them sau snapshot: `gstreamer1.0-tools`, `python3-venv`.

## Bien moi truong (da gom trong `scripts\env.sh`, `RENDER=gpu|cpu`)
- `GZ_VERSION=harmonic`
- `GZ_SIM_SYSTEM_PLUGIN_PATH=$HOME/ardupilot_gazebo/build`
- `GZ_SIM_RESOURCE_PATH=$HOME/ardupilot_gazebo/models:$HOME/ardupilot_gazebo/worlds`
- GPU: `GALLIUM_DRIVER=d3d12` (BAT BUOC: mac dinh Mesa roi ve llvmpipe) + `MESA_D3D12_DEFAULT_ADAPTER_NAME=9060`
- CPU: `LIBGL_ALWAYS_SOFTWARE=1`
Chi dat `MESA_D3D12_DEFAULT_ADAPTER_NAME` ma khong co `GALLIUM_DRIVER=d3d12` thi KHONG dung card (xem `results\glxinfo.txt`).

## Chay
- Chay het: `wsl -d Ubuntu-24.04 -- bash /mnt/d/Personal/Drone-Tracking/gazebo/scripts/20_full.sh <gpu|cpu> iris_runway.sdf`
- gz headless: `gz sim -s -r --headless-rendering iris_runway.sdf`
- SITL: `arducopter --model JSON --speedup 1 --slave 0 --sim-address=127.0.0.1 -I0 --defaults copter.parm,gazebo-iris.parm` (MAVLink tcp:5760)
- Bay: `fly.py` (GUIDED, arm, takeoff). Camera: bat phat bang
  `gz topic -t /world/iris_runway/model/iris_with_gimbal/model/gimbal/link/pitch_link/sensor/camera/image/enable_streaming -m gz.msgs.Boolean -p "data: 1"`
  roi `cam_recv.py` (GStreamer appsink -> numpy BGR, UDP 5600 H.264 RTP).

## Go bo
```
sudo apt-get remove --purge -y gz-harmonic libgz-sim8-dev python3-gz-transport13 python3-gz-msgs10 gstreamer1.0-tools
sudo apt-get autoremove -y      # xem ky danh sach truoc; hoac go theo results/installed_pkgs.txt
sudo rm /etc/apt/sources.list.d/gazebo-stable.list /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
rm -rf ~/ardupilot_gazebo ~/venv-gazebo ~/gazebo_logs ~/gazebo_install.log
```

## Luu y
- `gz sim` bi segfault luc tat (SIGTERM) o ca hai che do; khong anh huong khi chay.
- World `gimbal.sdf` can tai model tu fuel.gazebosim.org (Internet); `iris_runway.sdf` da co camera nen dung cai nay.
- Do luc may co tai nen (agent khac huan luyen CPU, load ~10-14/16), RTF dao dong.
