# Phần mềm bám mục tiêu trên máy đồng hành (Raspberry Pi 5)

Gói `onboard/dtrack`: một quad ArduCopter 4.7.2 bám một drone khác bằng camera đơn cố định, giữ khoảng cách đặt.
Khối NHẬN BIẾT (đã có, không sửa): `types.py`, `geometry.py`, `tracker.py`, `range_estimator.py`, `synthetic.py`.
Khối ĐIỀU KHIỂN và vòng kín mô phỏng (T9a): các file còn lại bên dưới.

## Kiến trúc

```
DetectionSource.poll() -> [Detection]
        |                       MavlinkLink.own_state() -> OwnState (quaternion than->NED, vi tri, van toc)
        v                                   |
 SingleTargetTracker.update(dets, own, t) -> TrackState
        v
 Supervisor.step(SupervisorInput) -> SupervisorOutput(state, send, cmd, request_rtl, reason)
        |   (ben trong: Guidance.step = compute_guidance, ham thuan khong I/O)
        v
 MavlinkLink.send_velocity(vel_ned, yaw)  --SET_POSITION_TARGET_LOCAL_NED-->  FC (GUIDED)
        +--> CycleLogger (CSV moi chu ky, luong ghi rieng, khong chan vong lap)
```

| File | Vai trò |
|---|---|
| `dtrack/config.py` | dataclass cấu hình (đơn vị trong tên trường), nạp TOML/JSON; `make_camera(tilt_up_deg)` |
| `dtrack/guidance.py` | luật dẫn đường thuần: `compute_guidance(track, own, cfg, prev, prev_accel)`; lớp `Guidance` giữ trạng thái |
| `dtrack/supervisor.py` | máy trạng thái IDLE/SEARCH/TRACK/COAST/LOST/ABORT, engage, watchdog |
| `dtrack/mavlink_io.py` | pymavlink: kết nối, yêu cầu luồng, dựng `OwnState`, gửi lệnh vận tốc+yaw, đổi mode RTL, ánh xạ đồng hồ FC |
| `dtrack/logger.py` | log CSV không chặn |
| `dtrack/app.py` | vòng lặp chính (mặc định 30 Hz), `DetectionSource`, `CameraHailoSource` (giữ chỗ) |
| `simtools/` | CHỈ mô phỏng: `sim_truth_source.py`, `sim_helper.py`, `run_closed_loop.sh`, `analyze_closed_loop.py` |

### Luật dẫn đường (hệ NED, `u` = đường ngắm, `r` = khoảng cách)
- Vận tốc mục tiêu ước lượng `v_t = v_own + ṙ·u + r·(ω × u)` (chỉ khi `range_valid`).
- Lệnh `v = v_t + clip(Kp·(r − r_đặt))·u` cộng thành phần đứng giữ mục tiêu giữa ảnh (chỉ thành phần vuông góc đường ngắm).
- `r_đặt = max(range_set_m, range_tau_s·|v|)`. Yaw hướng mũi theo đường ngắm có bù trễ (`yaw_lead_s`) và giới hạn tốc độ đổi.
- An toàn (thứ tự ưu tiên): dữ liệu không hữu hạn → phanh (v = 0, giữ yaw); không có mục tiêu → phanh; `r < range_min_m` (hysteresis) → lùi theo đường ngắm
  (giới hạn gia tốc `a_back`, không bị bỏ qua hoàn toàn); `range_valid = False` hoặc COAST → KHÔNG tiến lại gần: thành phần dọc đường ngắm không vượt vận tốc bản thân hiện tại, giảm dần; giới hạn tốc độ ngang/lên/xuống, gia tốc (dọc hướng bay `a_max`, phanh `a_decel`, vuông góc `a_lat`), jerk; độ cao tối thiểu.
- COAST: dùng khoảng cách hợp lệ cuối cùng (đóng băng, ṙ = 0) thay vì khoảng cách tracker ngoại suy (ngoại suy trôi nhanh khi chính mình đổi tốc độ).

### Supervisor
- Chỉ gửi lệnh khi FC đã arm, mode GUIDED và có tín hiệu engage (bay thật: kênh RC `engage_rc_channel` > `engage_rc_threshold_us`; SITL: `--auto-engage`, bị từ chối nếu nguồn không phải `sim`). Mất một trong ba → IDLE, ngừng gửi ngay. Không bao giờ arm / cất cánh / đổi sang GUIDED.
- Watchdog → ABORT (phanh nếu còn link): vòng lặp chậm > `loop_slow_s`, mất HEARTBEAT > `heartbeat_timeout_s`, tuổi dữ liệu tư thế > `pose_timeout_s`; lý do ghi vào log và `abort_reasons`.
- COAST tối đa `coast_follow_s`, sau đó LOST (phanh, giữ vị trí); không có mục tiêu quá `lost_rtl_s` → yêu cầu RTL một lần (`rtl_on_lost`).
- Khi app kết thúc (SIGINT/SIGTERM/`--stop-file`) mà FC vẫn ở GUIDED: phanh tường minh (v = 0, giữ yaw) tới khi đứng yên hoặc `brake_on_exit_s`, rồi thoát 0.

## Hằng số MAVLink đã xác minh (ArduPilot 4.7.2, `~/ardupilot`)
- `type_mask` vận tốc + yaw = 7 (pos) | 448 (acc) | 2048 (yaw rate) = **2503**; không yaw thêm 1024 = **3527** (`build/sitl/libraries/GCS_MAVLink/include/mavlink/v2.0/common/common.h:1545-1556`; `ArduCopter/GCS_MAVLink_Copter.cpp:896-918`, handler `:998+`).
- GUIDED dừng nếu quá `GUID_TIMEOUT` = 3 s không có lệnh (`ArduCopter/Parameters.cpp:875`, `mode_guided.cpp:1195`) → gửi lại ≥ 10 Hz (app gửi mỗi chu kỳ 30 Hz).
- `ATTITUDE_QUATERNION` là quaternion thân→NED (`GCS_Common.cpp:6090`); đã đối chiếu thực tế với tư thế thật SITL (sai khác ≲ 1°).

## Chạy
Thử đơn vị (không cần SITL), trong WSL:

    cd /mnt/d/Personal/Drone-Tracking/onboard
    ~/venv-ardupilot/bin/python -m pytest -q

Vòng kín SITL (mỗi lần ~5 phút thật; không gọi `sim/run_chase.sh`):

    wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/d/Personal/Drone-Tracking/onboard/simtools && SEED=1 SCENARIO=none bash run_closed_loop.sh 10'

Biến môi trường: `SEED` (seed bộ phát hiện tổng hợp), `SCENARIO` = `none` | `blackout` (tắt nguồn phát hiện 3 s tại t_ws+40 s) | `disengage` (đổi mode LOITER tại t_ws+40 s), `SPEEDUP`, `RANGE`, `CONFIG`, `MAX_WALL`.
Kết quả ở `onboard/simtools/out/<giờ>_<tốc độ>ms_s<seed>_<kịch bản>/`: `truth.csv` (vị trí THẬT của hai máy từ `SIM_STATE`, 50 Hz), `app_log.csv`, `events.json`, `result.txt`, log các tiến trình.
Cổng SITL: target `5760` (target.py) / `5762` (SimTruthSource) / `5763` (sim_helper); chaser `5770` (app) / `5772` (sim_helper) / `5773` (SimTruthSource).
Chấm điểm (`analyze_closed_loop.py`) chỉ dùng vị trí thật: sai số TB < 3 m trong cửa sổ 120 s, min khoảng cách thật ≥ 8 m trên TOÀN chuyến bay (cất cánh → cả hai dừng), TRACK ≥ 90%, khoảng trống dữ liệu ≤ 0.2 s, ≥ 10 Hz, app thoát 0.
Phép đổi lat/lon → mét dùng trắc địa WGS84 theo vĩ độ (`mavlink_io.latlon_to_ned`).

## Bảng tham số chính (`config.py`)
| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `guidance.range_set_m` / `range_tau_s` | 15 m / 0 | khoảng cách đặt; `r_đặt = max(range_set_m, tau·|v|)` |
| `guidance.range_min_m` (+ hyst 2 m) | 10 m | khoảng cách tối thiểu cứng → lùi |
| `guidance.back_speed_mps` | 5 | tốc độ lùi so với mục tiêu khi dưới tối thiểu |
| `guidance.kp_range` | 0.3 1/s | hệ số tỉ lệ sai số khoảng cách |
| `guidance.close_speed_max_mps` / `open_speed_max_mps` | 2 / 3 | giới hạn thành phần P (tiến / lùi) |
| `guidance.kp_vert_center` / `vert_center_max_mps` | 0.5 / 2.5 | giữ mục tiêu giữa ảnh theo phương đứng |
| `guidance.v_max_mps` | 30 | tốc độ ngang tối đa |
| `guidance.climb_max_mps` / `descend_max_mps` | 4 / 4 | tốc độ lên / xuống |
| `guidance.a_max_mps2` / `a_decel_mps2` / `a_lat_mps2` / `a_back_mps2` / `a_max_z_mps2` | 2 / 0.8 / 4 / 3 / 1.5 | gia tốc (dọc tăng tốc, phanh, ngang khi rẽ, khi lùi khẩn, đứng) |
| `guidance.jerk_max_mps3` | 6 | tốc độ đổi gia tốc lệnh |
| `guidance.yaw_rate_max_dps` / `yaw_lead_s` | 90 / 0.5 | giới hạn tốc độ yaw lệnh / bù trễ |
| `guidance.min_alt_m` | 10 | độ cao tối thiểu so với home EKF |
| `camera.tilt_up_deg` | 15 | góc ngẩng camera so với trục mũi |
| `camera.fx, fy` | 1739 px | lens 6 mm (≈ 45°×35°); lens 8 mm: 2319 (≈ 35°×26°, quá hẹp cho camera cố định) |
| `supervisor.coast_follow_s` | 2 s | COAST theo dự đoán tối đa |
| `supervisor.lost_rtl_s`, `rtl_on_lost` | 10 s, bật | không có mục tiêu quá lâu → RTL |
| `supervisor.heartbeat_timeout_s` / `pose_timeout_s` / `loop_slow_s` | 3 / 0.5 / 0.25 s | ngưỡng watchdog |
| `supervisor.engage_rc_channel`, `engage_rc_threshold_us` | 8, 1700 | tín hiệu engage khi bay thật |
| `mavlink.resend_hz` | ≥ 10 | tần số gửi lại lệnh tối thiểu |
| `loop_hz` | 30 | tần số vòng lặp |

## Hạn chế và điều CHƯA có
- **Camera thật + Hailo chưa có**: `CameraHailoSource` ném `NotImplementedError`. Mọi số đo vòng kín dùng phát hiện TỔNG HỢP từ vị trí thật của mục tiêu (nhiễu tâm 1.5 px, kích thước 1 px, bỏ sót 20%, giả 5%, trễ 60 ms, cắt mép), nên chưa phản ánh detector thật.
- Kênh RC engage cho bay thật **chưa thử** (chỉ đọc `RC_CHANNELS`; SITL dùng `--auto-engage`). Chưa thử trên phần cứng, chưa bay thật, chưa thử ở tốc độ ≳ 20 m/s.
- Camera cố định: quad nghiêng mũi theo gia tốc và lực cản nên mục tiêu ra khỏi khung ~35° dọc. Gia tốc dọc (2 m/s²) và phanh (0.8 m/s²) bị giới hạn thấp có chủ đích; ở tốc độ cao hơn (xem báo cáo 20 m/s) mục tiêu ra khỏi khung. Cần gimbal hoặc camera rộng hơn / giảm tốc độ bám.
- Mô hình SITL là quad `freestyle` 0.8 kg, không phải drone thật; thông số điều khiển chỉnh theo mô hình này.
- `types.py` / khối nhận biết không sửa; góp ý: `TrackState` không có độ tin cậy ngoại suy của khoảng cách khi COAST (guidance tự đóng băng).
