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
| `dtrack/search.py` | khối tìm lại mục tiêu sau khi mất hình (giai đoạn 2): `SearchEpisode` (đồng hồ đợt, pha), `SearchPlanner` (quét khớp và yaw); supervisor gọi. Mặc định TẮT |
| `dtrack/logger.py` | log CSV không chặn (khối tìm lại ghi thêm `search.csv` qua `SearchLogger`) |
| `dtrack/app.py` | vòng lặp chính (mặc định 30 Hz), `DetectionSource`, `CameraHailoSource` (giữ chỗ) |
| `simtools/` | CHỈ mô phỏng: `sim_truth_source.py`, `sim_helper.py`, `run_closed_loop.sh`, `analyze_closed_loop.py` |

### Luật dẫn đường (hệ NED, `u` = đường ngắm, `r` = khoảng cách)
- Vận tốc mục tiêu ước lượng `v_t = v_own + ṙ·u + r·(ω × u)` (chỉ khi `range_valid`).
- Lệnh `v = v_t + clip(Kp·(r − r_đặt))·u` (P tiến lại gần còn bị cắt ≤ √(2·a_decel·(r − range_min)): quãng phanh), cộng thành phần đứng giữ mục tiêu ở góc nâng mong muốn `target_elev_ref_deg` (tính trong khung đã bù pitch/roll, chỉ giữ yaw; góc mong muốn hạ thấp theo GIA TỐC LỆNH trước khi tăng tốc, không theo tư thế đo; chỉ thành phần vuông góc đường ngắm).
- `r_đặt = max(range_set_m, range_tau_s·|v|)`. Yaw hướng mũi theo đường ngắm có bù trễ (`yaw_lead_s`) và giới hạn tốc độ đổi.
- An toàn (thứ tự ưu tiên): dữ liệu không hữu hạn → phanh (v = 0, giữ yaw); không có mục tiêu → phanh; `r < range_back_m` (hysteresis; `range_back_m` ≥ `range_min_m`) → lùi theo đường ngắm
  (giới hạn gia tốc `a_back`, không bị bỏ qua hoàn toàn); `range_valid = False` hoặc COAST → KHÔNG tiến lại gần: thành phần dọc đường ngắm không vượt vận tốc bản thân hiện tại, giảm dần; giới hạn tốc độ ngang/lên/xuống, gia tốc (dọc hướng bay `a_max`, phanh `a_decel`, vuông góc `a_lat`), jerk; độ cao tối thiểu.
- COAST / mất hẳn / TRACK nhưng `range_valid = False` (vừa bắt lại, sát mép ảnh): dùng khoảng cách hợp lệ cuối cùng (đóng băng, ṙ = 0) và VẬN TỐC MỤC TIÊU NHỚ ĐƯỢC (EMA lúc TRACK hợp lệ). Bay tiếp theo vận tốc đó, giảm dần sau `blind_grace_s` (`blind_decel_mps2`), không bao giờ nhanh hơn tốc độ ngang hiện tại của mình; mũi quay về hướng ngắm cuối. Bộ nhớ cũ hơn `blind_mem_max_s` bị bỏ.

### Supervisor
- Chỉ gửi lệnh khi FC đã arm, mode GUIDED và có tín hiệu engage (bay thật: kênh RC `engage_rc_channel` > `engage_rc_threshold_us`; SITL: `--auto-engage`, bị từ chối nếu nguồn không phải `sim`). Mất một trong ba → IDLE, ngừng gửi ngay. Không bao giờ arm / cất cánh / đổi sang GUIDED.
- Watchdog → ABORT (phanh nếu còn link): vòng lặp chậm > `loop_slow_s`, mất HEARTBEAT > `heartbeat_timeout_s`, tuổi dữ liệu tư thế > `pose_timeout_s`; lý do ghi vào log và `abort_reasons`.
- COAST tối đa `coast_follow_s` tính từ lúc vào COAST, kể cả khi tracker đã báo LOST/SEARCH (nó reset sau 3 s): vẫn bay tiếp như trên; hết hạn mới LOST (phanh, giữ vị trí); không có mục tiêu quá `lost_rtl_s` → yêu cầu RTL một lần (`rtl_on_lost`).
- Khối tìm lại (`search.enabled`, mặc định `False` = không có đợt tìm, RTL sau `lost_rtl_s` như cũ; lệnh COAST và bộ bám đã đổi theo C1/C2 nên không hoàn toàn giống giai đoạn 1; cần `gimbal.enabled`, không dùng cùng `camera.gimbal_enabled`): đợt `search.total_s` = 20 s tính từ COAST đầu. Pha 0 bay theo dự đoán tối đa `coast_follow_s` = 4 s; pha 1 treo (≤ 0,3 m/s); quy tắc S-16: trước mốc `scan_start_s` = 12,0 s (tính từ đầu đợt; khi bật phải có `coast_follow_s` < `scan_start_s` < `total_s`) khớp KHÔNG quét mà giữ hướng ngắm cuối theo hệ thế giới (`SearchPlanner.follow`, tự bù khi thân đổi tư thế) và drone giữ hướng mũi lúc vào pha 1 (không quét yaw); từ mốc đó (`sweep`) khớp quét `scan_rate_dps` = 60°/s trong `scan_lo_deg`–`scan_hi_deg` (10°–110°), yaw quét ±`yaw_amp_deg` = 45° ở `yaw_rate_dps` = 20°/s, bắt đầu liên tục từ góc hiện tại; khi tracker báo TRACK trong pha ≥ 1 thì khớp ngừng quét và bám (bộ quét cập nhật theo góc khớp thực trong lúc đó), drone vẫn treo; pha 2 leo `climb_m` (mặc định 0 = tắt) từ `climb_start_s` = 10 s, tốc độ `climb_rate_mps` 2 m/s, độc lập với mốc quét; hết `total_s` thì RTL một lần. Tìm lại = TRACK liên tục ≥ `reacquire_hold_s` = 1,0 s, lúc đó đợt đóng. Bật bằng hồ sơ `search_plane_r15` (`config.PROFILES`; file tương đương `simtools/configs/search_plane_r15.json`). Hồ sơ đặt `blind_floor_m` = 0 và `blind_v_cap_mps` = 0 nên cơ chế "giả định mục tiêu hãm" khi bay mù (còn trong mã, có test) TẮT theo quyết định của chủ dự án. Thiết kế: `.office/design-search.md` (S-1…S-16 ở cuối file thắng phần trên). Rủi ro đã biết xem mục cuối file này.
- Khi app kết thúc (SIGINT/SIGTERM/`--stop-file`) mà FC vẫn ở GUIDED: phanh tường minh (v = 0, giữ yaw) tới khi đứng yên hoặc `brake_on_exit_s`, rồi thoát 0.

## Hằng số MAVLink đã xác minh (ArduPilot 4.7.2, `~/ardupilot`)
- `type_mask` vận tốc + yaw = 7 (pos) | 448 (acc) | 2048 (yaw rate) = **2503**; không yaw thêm 1024 = **3527** (`build/sitl/libraries/GCS_MAVLink/include/mavlink/v2.0/common/common.h:1545-1556`; `ArduCopter/GCS_MAVLink_Copter.cpp:896-918`, handler `:998+`).
- GUIDED dừng nếu quá `GUID_TIMEOUT` = 3 s không có lệnh (`ArduCopter/Parameters.cpp:875`, `mode_guided.cpp:1195`) → gửi lại ≥ 10 Hz (app gửi mỗi chu kỳ 30 Hz).
- `ATTITUDE_QUATERNION` là quaternion thân→NED (`GCS_Common.cpp:6090`); đã đối chiếu thực tế với tư thế thật SITL (sai khác ≲ 1°).

## Chạy
Thử đơn vị (không cần SITL), trong WSL:

    cd /mnt/d/Personal/Drone-Tracking/onboard
    ~/venv-ardupilot/bin/python -m pytest -q

Kỳ vọng theo kết quả giai đoạn 2b (2026-11-20): 1412 passed, 1 xfailed (số cũ 1368 passed là trước quy tắc S-16).

Vòng kín SITL (mỗi lần ~2,5–4,5 phút thật; không gọi `sim/run_chase.sh`):

    wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/d/Personal/Drone-Tracking/onboard/simtools && SEED=1 SCENARIO=none bash run_closed_loop.sh 10'

Biến môi trường: `SEED` (seed bộ phát hiện tổng hợp), `SCENARIO` = `none` | `blackout` (tắt nguồn phát hiện 3 s tại t_ws+40 s) | `disengage` (đổi mode LOITER tại t_ws+40 s), `SPEEDUP`, `RANGE`, `CONFIG`, `MAX_WALL`.
Thêm cho đo so sánh camera (B4): `STRAIGHT=1` (mục tiêu bay thẳng, tăng tốc đầu + phanh cuối), `RANGE` (khoảng cách giữ, truyền cho cả app), `CAM_FX` (tiêu cự px), `CAM_TILT` (độ), `GIMBAL=1` (khớp gật một trục ổn định pitch: `camera.gimbal_enabled`, `gimbal_travel_deg` ±50, `gimbal_rate_dps` 300, `gimbal_lag_s` 0.05; mô hình ở `simtools/gimbal_model.py`, tracker nhận quaternion thân hiệu dụng `q_eff`, guidance vẫn dùng tư thế thân và tự đặt `elev_accel_comp = 0` để không bù hai lần). Các biến này ghi `app_cfg.json` vào thư mục kết quả; analyzer đọc lại để in các dòng `B4 ...` (pha, ra khỏi khung, góc trục đẩy–hướng nhìn, hành trình khớp, kích thước mục tiêu, sai số khoảng cách). Mặc định camera cố định như cũ.
Ca tìm lại (chỉ đi với `SCENARIO=blackout`; đặt bất kỳ biến nào dưới đây thì cửa sổ chấm = `EVENT_AT`): `EVENT_AT` (giây kể từ `t_ws`, lúc bắt đầu cửa sổ đo khi khoảng cách đạt mức đặt; mặc định 40; lô `srchG3` đặt 30 cho ca bổ nhào), `BLACKOUT_S` (độ dài mất hình, mặc định 3), `POST_S` (giây quan sát sau khi hết mất hình, mặc định 15), `DIVE_DEG>0` (cắm xuống đúng lúc mất hình), `BLACKOUT_BRAKE` (m/s², mục tiêu hãm đúng lúc mất hình; không đi với `DIVE_DEG`), `BLIND_D3_MIN` (ngưỡng d3 lúc mù, mặc định 8 m), `MEASURE_ONLY=1` (tiêu chí khoảng cách chỉ in để đo), `DRY_RUN=1` (chỉ in dòng lệnh helper và bộ chấm rồi thoát 0, không khởi động gì). `PROFILE=<tên hồ sơ trong config.PROFILES>` thay cho `CONFIG` (đặt `PROFILE` thì `CONFIG` bị bỏ qua). Ví dụ (đã kiểm bằng `DRY_RUN=1`, chưa chạy thật):

    PROFILE=search_plane_r15 SEED=1 SCENARIO=blackout BLACKOUT_S=8 bash run_closed_loop.sh 10

Kết quả ở `onboard/simtools/out/<giờ>_<tốc độ>ms_s<seed>_<kịch bản>/`: `truth.csv` (vị trí THẬT của hai máy từ `SIM_STATE`, 50 Hz), `app_log.csv`, `events.json`, `result.txt`, log các tiến trình.
Cổng SITL: target `5760` (target.py) / `5762` (SimTruthSource) / `5763` (sim_helper); chaser `5770` (app) / `5772` (sim_helper) / `5773` (SimTruthSource).
Chấm điểm (`analyze_closed_loop.py`) chỉ dùng vị trí thật: sai số TB < 3 m trong cửa sổ 120 s, min khoảng cách thật ≥ 8 m trên TOÀN chuyến bay (cất cánh → cả hai dừng), TRACK ≥ 90%, khoảng trống dữ liệu ≤ 0.2 s CHỈ trong cửa sổ đo (khoảng trống toàn chuyến chỉ in tham khảo), ≥ 10 Hz, app thoát 0.
Phép đổi lat/lon → mét dùng trắc địa WGS84 theo vĩ độ (`mavlink_io.latlon_to_ned`).

## Bảng tham số chính (`config.py`)
| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `guidance.range_set_m` / `range_tau_s` | 15 m / 0 | khoảng cách đặt; `r_đặt = max(range_set_m, tau·|v|)` |
| `guidance.range_min_m` | 12.5 m | ngưỡng an toàn (cao hơn 8 m an toàn vì FC trễ ~1 s) |
| `guidance.range_back_m` (+ hyst 1 m) | 12.5 m | vào lùi khẩn khi r < ngưỡng, thoát khi r > ngưỡng + hyst; phải ≥ `range_min_m` và `range_set_m` ≥ ngưỡng + hyst (hồ sơ `accept_gimbal_r25` đặt 15 m) |
| `guidance.back_speed_mps` | 8 | tốc độ lùi so với mục tiêu khi dưới ngưỡng |
| `guidance.kp_range` | 0.3 1/s | hệ số tỉ lệ sai số khoảng cách |
| `guidance.close_speed_max_mps` / `open_speed_max_mps` | 3 / 3 | giới hạn thành phần P (tiến / lùi) |
| `guidance.kp_vert_center` / `vert_center_max_mps` | 0.5 / 2.5 | giữ mục tiêu ở góc nâng mong muốn theo phương đứng |
| `guidance.target_elev_ref_deg` / `elev_ref_max_deg` | 4 / 8 | góc nâng mong muốn của mục tiêu khi không tăng/giảm tốc / cắt ± (bù trước nghiêng mũi theo gia tốc lệnh) |
| `guidance.v_max_mps` | 30 | tốc độ ngang tối đa |
| `guidance.climb_max_mps` / `descend_max_mps` | 4 / 4.8 | tốc độ lên / xuống |
| `guidance.a_max_mps2` / `a_decel_mps2` / `a_lat_mps2` / `a_back_mps2` / `a_max_z_mps2` | 3.5 / 3 / 7 / 12 / 1.5 | gia tốc (dọc tăng tốc, phanh, ngang khi rẽ, khi lùi khẩn, đứng) |
| `guidance.jerk_max_mps3` / `jerk_back_mps3` | 10 / 80 | tốc độ đổi gia tốc lệnh (thường / khi lùi khẩn) |
| `guidance.v_t_mem_tau_s` / `blind_grace_s` / `blind_decel_mps2` / `blind_mem_max_s` | 0.5 / 1 / 1 / 8 | bộ nhớ vận tốc mục tiêu, bay tiếp khi mất mục tiêu |
| `guidance.yaw_rate_max_dps` / `yaw_lead_s` | 90 / 0.5 | giới hạn tốc độ yaw lệnh / bù trễ |
| `guidance.min_alt_m` | 10 | độ cao tối thiểu so với home EKF |
| `camera.tilt_up_deg` | 15 | góc ngẩng camera so với trục mũi |
| `target_shape.span_m` / `length_m` / `height_m` | 0.30 / 0.30 / 0.30 m | hộp bao mục tiêu: sải cánh / thân / cao. `span_m` cũng là kích thước bộ ước lượng khoảng cách và nguồn mô phỏng dùng (một nguồn). Hồ sơ `accept_plane_r25` = `accept_gimbal_r25` + (2.16, 1.50, 0.65); hộp bao nên bbox lớn hơn hình thật ở góc chéo, ước lượng khoảng cách lệch theo hướng nhìn (từ sau ~0.97, ngang ~1.38, chéo 45° ~0.84) |
| `acceptance.hard_floor_m` / `dive_range_min_m` | 8 / 12.5 m | ngưỡng chấm nghiệm thu mô phỏng (sàn cứng toàn chuyến / cận dưới pha cắm và giảm tốc cuối), bộ chấm đọc từ `app_cfg.json`. Hồ sơ `accept_plane_r15` = `accept_plane_r25` + giữ 15 m (`range_back_m` 10, `range_min_m` 8) + ngưỡng 6 / 6 m |
| `camera.fx, fy` | 1739 px | lens 6 mm (≈ 45°×35°); lens 8 mm: 2319 (≈ 35°×26°, quá hẹp cho camera cố định) |
| `supervisor.coast_follow_s` | 4 s | bay tiếp (COAST) tối đa khi mất mục tiêu, rồi phanh |
| `supervisor.lost_rtl_s`, `rtl_on_lost` | 10 s, bật | không có mục tiêu quá lâu → RTL |
| `supervisor.heartbeat_timeout_s` / `pose_timeout_s` / `loop_slow_s` | 3 / 0.5 / 0.25 s | ngưỡng watchdog |
| `supervisor.engage_rc_channel`, `engage_rc_threshold_us` | 8, 1700 | tín hiệu engage khi bay thật |
| `mavlink.resend_hz` | ≥ 10 | tần số gửi lại lệnh tối thiểu |
| `loop_hz` | 30 | tần số vòng lặp |

## Rủi ro đã biết của khối tìm lại (lô SITL `srchG3`, 26 lần, 2026-11-19, và `srchH1`, 20 lần, 2026-11-20; toàn bộ là mô phỏng)
Kết quả `srchG3`: tìm lại bay thẳng 5/5 seed sau 7,97–8,13 s (4 seed `srchG3` + seed 1 lô bù `srchG4`); bổ nhào 25° 5/5 sau 10,97–11,07 s (trước S-16); mất hình 25 s → RTL ở 20,03 s; d3 nhỏ nhất trong cửa sổ mất hình khi mục tiêu bay đều 15,13–15,89 m (yêu cầu 8 m).
Kết quả `srchH1` (sau S-16; thời gian lấy lại hình = state về TRACK lần đầu sau COAST đầu, tính từ lúc bắt đầu mất hình): bổ nhào 25°, mất hình 8 s, seed 1–5: bật 8,22 / 8,16 / 8,17 / 8,18 / 8,14 s (trung bình 8,17 s), tắt 8,16 / 8,17 / 8,17 / 8,23 / 8,17 s (trung bình 8,18 s), chênh −0,006 s; mất hình 7 s: 7,17 / 7,22 s; 9 s: 9,19 / 9,20 s; bay thẳng 8 s bật seed 1–3: tìm lại 3/3 sau 8,16 / 8,18 / 8,20 s; mất hình 25 s: RTL ở 20,04 s từ đầu đợt; mất hình 14 s: quét bắt đầu ở 12,03 s, bám lại ở 14,98 s (hình trở lại ở 14,02 s, trễ 0,96 s); cấu hình `search_plane_r15_climb10`, mất hình 14 s: leo từ 10,6 s, tăng 5,54 m tới lúc tìm lại (14,0 s); các mốc leo tính theo đồng hồ đợt, các số khác tính từ lúc bắt đầu mất hình (lệch khoảng 0,18 s); cùng cách đo, lần trước (`srchG4`, cùng script) 10,67 s / 5,24 m / 13,97 s. Rủi ro:
- (a) Cuối bài, khi mục tiêu dừng, drone vào đợt COAST thứ hai và áp sát 3,89–7,87 m ở 11/19 lần (mẫu số = tất cả lần bay thẳng có mục tiêu dừng cuối bài; không tính ca mất hình 25 s (RTL) và ca mục tiêu hãm 3 / 8 m/s² lúc mất hình. Đếm: `srchG3` lần 1–5, 15, 23–26 (10 lần, 7 dưới 8 m); `srchG4` lần 1, 2, 7, 8 (4 lần, 1 dưới 8 m; lần 1 là ca leo mất hình 14 s, cả chuyến 15,31 m); `srchH1` lần 15, 16, 17, 19, 20 (5 lần, 3 dưới 8 m: 4,72 / 5,54 / 4,51 m; lần 19, 20 là 14,93 / 14,95 m). Bản trước ghi 8/13 do chưa đếm ca mất hình 14 s. 11 lần dưới 8 m là `srchG3` lần 1–5, 24, 26, `srchG4` lần 2 và `srchH1` lần 15–17. `srchG4` lần 2: 5,21 m ngoài cửa sổ mất hình, trong cửa sổ 15,72 m, drone cao hơn mục tiêu 4,00 m, góc nâng 50,1°), kể cả khi tắt tìm lại; lúc gần nhất drone ở trên mục tiêu 3,3–4,2 m, góc nâng 27–75° ("gần như trên đầu" chỉ hợp 3 lần trên 65°); bám bình thường khoảng 11–13° ở ba lần được tính lại (báo cáo đo ghi 11–19° cho lần 6–11, 13–19). Cùng lúc đó mục tiêu ra khỏi khung 1,56–3,88 s, khoảng cách lớn nhất tới 57 m. Chưa sửa. Nhận xét theo bảng: cả 11 lần áp sát đều là ca mất hình 8 s (drone còn đang đuổi khi mục tiêu dừng); 13 ca mất hình 8 s thì 11 bị, 2 ca còn lại (`srchG3` lần 23, 25: 8,47 / 8,70 m) sát ngưỡng 8 m; 3 ca mất hình 14 s không bị. Cú dừng khoảng 7 m/s² là của mục tiêu mô phỏng (một máy bay nhiều cánh quạt nhận lệnh vận tốc 0); máy bay cánh bằng thật khó giảm tốc gấp như vậy khi đang bay. Mức giảm tốc lớn nhất thực tế của mục tiêu chưa được chốt, và chưa quyết định hướng sửa (sửa kịch bản mô phỏng hay sửa luật hãm của drone). Nguyên nhân gốc (đã điều tra, chưa sửa): lệnh dừng của mục tiêu mô phỏng làm nó hãm khoảng 7 m/s² ở đỉnh (5,9 m/s² trung bình 1 s), đứng sau khoảng 2,5 s; drone chỉ được hãm `guidance.a_decel_mps2` = 3,0 và trễ đáp ứng của bộ điều khiển bay (trễ 0,12–0,16 s, hằng số thời gian 0,65–0,75 s) không được tính trong trần tốc độ tiếp cận. Khoảng cách nhỏ nhất phụ thuộc tốc độ drone lúc qua 10 m (9,6 m/s cho 4,13 m; 4,9 m/s cho 8,70 m). Lùi khẩn làm mũi ngóc 36–43°, gimbal kẹt biên 110°, mục tiêu ra đáy khung thành đợt mất hình thứ hai, lệnh lùi chạy tiếp nên drone văng xa 36–57 m. Khối tìm lại không liên quan. Mục tiêu hãm 1,6 m/s² thì không bị; theo mô hình tính (chưa chạy SITL) hãm quá khoảng 3 m/s² sẽ bị. Hướng sửa dự kiến: dùng cự ly dự đoán (cự ly + tốc độ tiếp cận × khoảng 0,85 s) cho trần tiếp cận và lệnh lùi (theo mô hình: 7,3–11,1 m), giới hạn góc ngóc khi lùi, chặn quãng lùi khi mất hình.
- (b) Mục tiêu hãm 1,5 / 3 / 8 m/s² lúc mù (chỉ đo): gần nhất cả chuyến 4,23 / 3,24 / 3,38 m; ca 1,5 m/s² tìm lại ở 17,90 s; ca 3 và 8 m/s² không tìm lại, RTL ở 20 s.
- (c) ĐÃ SỬA (2026-11-20, S-16): ca bổ nhào bật tìm lại từng lấy lại hình chậm hơn tắt ≈ 3 s (≈ 11,0 s so với ≈ 8,0 s); sau sửa bật 8,17 s, tắt 8,18 s (chênh −0,006 s, mức đặt ≤ +1,0 s). Hạn chế: cả 14 lần bổ nhào (7–9 s) ngắn hơn mốc quét 12 s nên khối quét không chạy lần nào; chỉ chứng minh bật không còn làm chậm, không chứng minh quét có ích, chưa có ca nào bật tốt hơn tắt. Đánh đổi: mục tiêu hiện lại ở chỗ khác chỉ được quét tìm từ giây 12 (còn 8 s trước RTL); hình trở lại sau giây 12 có thể trễ tới gần một chu kỳ quét (0,96 s ở mất hình 14 s: hình trở lại ở 14,02 s, bám lại ở 14,98 s). Nguyên nhân cũ: pha 1 quét gimbal cả dải 10°–110° (chu kỳ 3,33 s), mục tiêu bổ nhào (≈ −42° lúc 8 s) chỉ lọt khung khi gimbal ≳ 97–100° (0,2–0,3 s mỗi chu kỳ), và lượt quét qua vùng đó kết thúc đúng lúc hết mất hình ở cả 5 seed. Độ trễ thật 0–3,3 s tùy pha, chưa đo. Hướng dự kiến lúc đó (quét quanh góc dự đoán ≈ ±25°, nâng `scan_lo_deg`) đã bị loại, xem S-16.
- (d) Sau lô bù `srchG4`: C8 mới 1 lần leo thật, đạt (leo 5,20 m từ độ cao thấp nhất trong cửa sổ mất hình, 4,86 m từ lúc bắt đầu mất hình; mất hình 14 s, `configs/search_plane_r15_climb10.json`; d3 nhỏ nhất 15,59 m trong cửa sổ, 15,31 m cả chuyến; sau khi tìm lại độ cao còn tăng tới +20,47 m, đỉnh 53,74 m ở 25,4 s sau lúc mất hình, đúng thiết kế nhưng C8 không bao đoạn này; trần chênh cao khi bám ở xa là quyết định thiết kế còn mở), chưa đủ so với kế hoạch (10 m × 3 seed, 20 m × 1 seed; `srchH1` thêm 1 lần leo 10 m, tăng 5,54 m, vẫn 1 seed); C5 đạt 5/5 seed (và `srchH1` 3/3) nhưng các lần đều bắt lại đúng lúc hình trở lại hoặc trước mốc quét 12 s, chưa chứng minh quét tự tìm ra mục tiêu; C9 đạt, ba ô bám (lần 13–15 `srchG3`, thêm seed 2 và 3 ở `srchG4`) d3 nhỏ nhất 11,10–13,12 m ở các lần bù, ra khung 0 s; C2 chưa chứng minh trực tiếp. (e) Bộ bám mất thời gian TRACK khi có vật gây nhiễu độ tin cậy cao ở mọi khung: 20–29 điểm phần trăm (lần đo độc lập thứ nhất) hoặc khoảng 42–46 điểm (lần thứ hai). (f) Nhiễu đo gấp đôi: 2 lần khoảng cách ≈ 50 m ở đoạn giảm tốc cuối, chưa rõ nguyên nhân. (g) Chưa bay thật, chưa chạy trên Pi.

## Hạn chế và điều CHƯA có
- **Camera thật + Hailo chưa có**: `CameraHailoSource` ném `NotImplementedError`. Mọi số đo vòng kín dùng phát hiện TỔNG HỢP từ vị trí thật của mục tiêu (nhiễu tâm 1.5 px, kích thước 1 px, bỏ sót 20%, giả 5%, trễ 60 ms, cắt mép), nên chưa phản ánh detector thật.
- Kênh RC engage cho bay thật **chưa thử** (chỉ đọc `RC_CHANNELS`; SITL dùng `--auto-engage`). Chưa thử trên phần cứng, chưa bay thật, chưa thử ở tốc độ ≳ 20 m/s.
- Camera cố định: quad nghiêng mũi theo gia tốc và lực cản nên mục tiêu ra khỏi khung ~35° dọc. Khi tăng tốc mạnh (mục tiêu cất cánh ~7 m/s² ở 20 m/s) nghiêng mũi tới ~35–40° nên mục tiêu ra khỏi khung phía trên; khi phanh ngẩng mũi nên ra khỏi khung phía dưới. Cần gimbal hoặc camera rộng hơn / giảm tốc độ bám (so sánh ở bước B4).
- Mô hình SITL là quad `freestyle` 0.8 kg, không phải drone thật; thông số điều khiển chỉnh theo mô hình này.
- `types.py` / khối nhận biết không sửa; góp ý: `TrackState` không có độ tin cậy ngoại suy của khoảng cách khi COAST (guidance tự đóng băng).
