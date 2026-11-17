# Chặng 1: chaser giữ 15 m tới target (SITL, khoảng cách từ dữ liệu chuẩn)

Hai ArduCopter SITL chạy cùng lúc trong WSL (`Ubuntu-24.04`): **target** (instance 0, sysid 1) bay tốc độ cho trước
và đổi hướng; **chaser** (instance 1, sysid 2) đọc vị trí/vận tốc target qua MAVLink của target
(GLOBAL_POSITION_INT, cổng SERIAL1 của target) rồi bay GUIDED giữ 15 m. Chưa có camera.

## Chạy

Từ PowerShell (không có `&&`):

    wsl -d Ubuntu-24.04 -- bash /mnt/d/Personal/Drone-Tracking/sim/run_chase.sh 10
    wsl -d Ubuntu-24.04 -- bash /mnt/d/Personal/Drone-Tracking/sim/run_chase.sh 20

`10` và `20` là tốc độ ngang của target (m/s): kịch bản A và B. Mỗi lần chạy mất khoảng 3-4 phút thật ở `SPEEDUP=1` (đã đo).
Exit code của `run_chase.sh` = exit code của `analyze.py` (0 PASS, 1 FAIL).
Kết quả nằm ở `sim/out/<timestamp>_<speed>ms/`: `chase.csv`, `result.txt`, `target.log`, `chaser.log`,
`sitl_*.log` và `logs_*` (file .BIN của ArduPilot, nếu có). Thư mục làm việc SITL ở `~/sitl_run/` (ext4).

Biến môi trường: `SPEEDUP` (mặc định 1, hệ số tăng tốc mô phỏng), `MAX_WALL` (giây thật, mặc định 1200).

## File

- `run_sitl.sh <instance> <home> <workdir> [speedup]`: 1 SITL headless (`-I`, `--sysid`, `--home`, `--defaults`).
- `chase.parm`: tham số ghi đè (WP_SPD, WP_ACC, ATC_ANGLE_MAX), có chú thích lý do. Cả hai drone dùng mô hình vật lý
  freestyle 0.8 kg của ArduPilot (`X:@ROMFS/models/freestyle.json` + `models/freestyle.param`); mô hình `+` mặc định
  chỉ bay được ~18,4 m/s (đã đo) nên không đủ cho kịch bản B. Đây là giả định mô hình, không phải drone thật.
- `target.py --speed V`: cất cánh 30 m, chờ tín hiệu, bay tốc độ V; giữ 20 s rồi cứ 30 s đổi hướng 1 lần
  theo chu kỳ +60, -90, +90, -60 độ (xoay 15 độ/s).
- `chaser.py --speed V --csv ...`: luật `v = v_target + clamp(kp*(d - 15), ±12) * L` (L là đường ngắm), giữ cùng độ cao,
  ghi CSV ~20 Hz (thời gian sim). Ngắt an toàn: khoảng cách < 10 m thì lùi ra (tiêu chí nghiệm thu vẫn là 8 m).
- `analyze.py chase.csv`: tính và in PASS/FAIL.
- `chaselib.py`: hàm dùng chung.

## Định nghĩa cửa sổ đo (thời gian sim, từ MAVLink, không phải đồng hồ tường)

- Khoảng cách = 3D giữa target và chaser.
- Cửa sổ 120 s bắt đầu khi target đã đạt >= 90% tốc độ đặt **và** chaser (từ lúc đó) đã vào trong 15 ± 3 m.
- "Không bao giờ < 8 m" kiểm trên toàn chuyến bay từ khi cả hai cùng có độ cao >= 2 m đến hết dữ liệu.
- Tiêu chí: sai số TB |d − 15| < 3 m trong cửa sổ; min khoảng cách >= 8 m; cửa sổ đủ 120 s;
  target đổi hướng >= 2 lần trong cửa sổ (hướng đi lệch >= 30 độ so với 8 s trước).

## Đọc kết quả

`result.txt` in sai số TB / RMS / max, khoảng cách min/max, tốc độ target TB trong cửa sổ, từng tiêu chí
`[PASS]`/`[FAIL]` và dòng `KET QUA`. Nếu target không đạt 90% tốc độ hoặc chaser không vào dải 15 ± 3 m thì
không có cửa sổ và kết quả là FAIL (xem `target.log` để biết target có đạt tốc độ không).

## Hạn chế

Vị trí là ước lượng EKF của mỗi drone (GPS mô phỏng), không phải vị trí thật của mô phỏng. SITL lắng nghe TCP
trên mọi giao diện của WSL (không đổi được trong firmware); WSL2 mặc định NAT nên không ra ngoài máy.
