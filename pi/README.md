# Pi 5 - buoc S3 (do toc do nhan dien tren CPU)

Ket noi (tu WSL Ubuntu-24.04): `ssh -i ~/.ssh/id_pi_lab -o IdentitiesOnly=yes <PI_USER>@<PI_HOST>`
Chay script tren Pi: `wsl -d Ubuntu-24.04 -- bash /mnt/d/Personal/Drone-Tracking/pi/scripts/pi_run.sh <script.sh>`

Thu tu: 01_install_apt.sh (can sudo co mat khau: KHONG chay duoc, khong can vi libgl1/python3-dev da co san),
03b_torch_full.sh (torch day du, ~3 GB gom thu vien CUDA vi wheel aarch64 tren PyPI bat buoc), 05_pkgs.sh,
04_copy_assets.sh, 06_export_all.sh (ncnn/onnx/openvino x 640/480/320 ngay tren Pi), 08_start_grid.sh (luoi do),
soak.py (chay ben 30 phut; chua chay).
Luu y: dat TMPDIR=~/dtrack/tmp vi /tmp tren Pi la tmpfs 2 GB, pip tai torch se day /tmp.

Go bo: `rm -rf ~/dtrack ~/.cache/pip ~/.config/Ultralytics` tren Pi (khong co goi apt nao duoc cai them).