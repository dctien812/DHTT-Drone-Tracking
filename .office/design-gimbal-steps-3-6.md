# Thiết kế bước 3 / 4 / 4b / 5 / 6: khớp gật chủ động trong mô phỏng

Lập: 02 planner, 2026-11-18 (phiên 5), chỉ đọc mã, chưa chạy gì. Trưởng phòng đã duyệt làm theo.
Đường dẫn tính từ `D:\Personal\Drone-Tracking\onboard\`. Đơn vị: radian trong mã, độ trong config. Mọi giá trị servo là GIẢ ĐỊNH.

## Quyết định chung
- Đường mới ở cạnh đường cũ. `camera.gimbal_enabled` và `GimbalModel` (`simtools\gimbal_model.py`, `tests\test_gimbal.py`) giữ nguyên, hồ sơ `accept_*` vẫn chạy khớp cũ. Khớp chủ động mới bật bằng `gimbal.enabled`. Hai cờ cùng bật thì `validate()` ném ValueError.
- Chỉ MỘT đối tượng `SimGimbalPort`, dùng chung cho `App` và `SimTruthSource` (hiện có hai `GimbalModel` riêng ở `app.py:61-65` và `app.py:147-152`; giữ kiểu đó thì hai bên lệch pha).
- Camera với khớp mới: `make_camera(0)` và `q_cam = camera_attitude(q_thân, δ_thật)`. `boresight_body` = trục camera của `make_camera(90°−δ)`.
- Vòng đứng của guidance (`guidance.py:172-182`) điều chỉnh góc nâng LOS về `e_ref`; không đụng khung vòng này. Với `cam_tilt_up_deg=0` thì `err + e_ref = e_ref − elev_los`.
- Phân vai: khớp gật căn LOS vào giữa khung (nhanh); guidance leo/hạ để LOS đạt `e_ref` (chậm). Điểm giữ góc nâng của 4b là `e_ref` ở guidance, không phải ở khớp.
- Quy ước: θ > 0 là quad chúi mũi (pitch = −θ). θ=0 (quad treo, trục đẩy thẳng đứng): δ cần = 90° − elev; elev −12° cần 102°, bị kẹp 90°, camera nhìn ngang, `sat=True`. θ→90°: δ = −elev. Không dùng Euler.
- Giao diện bước 2 (`dtrack\gimbal.py`): `DELTA_MIN_RAD`, `DELTA_MAX_RAD`; `boresight_body(delta)`; `camera_attitude(q_wxyz, delta)`; `elev_to_delta(q, elev_target, delta_min=, delta_max=) -> (delta, sat: bool)`; ValueError với đầu vào không hữu hạn.

## Bước 3: ServoModel + SimGimbalPort
- File mới `simtools\servo_model.py`.
  - `ServoModel(delta_init_rad, delta_min_rad, delta_max_rad, rate_rad_s, lag_s, dead_time_s, quant_rad, slow_factor=1.0)`; `ServoModel.from_config(g: GimbalConfig)`.
  - `command(t, delta_rad) -> float`: kẹp [min,max], lượng tử `round(x/quant)*quant`, trả lệnh đã lượng tử, ghi vào hàng đợi (t_cmd = max(t, t_cmd trước)).
  - `advance(t) -> float` (δ thật, rad). Lần gọi đầu đặt `_t=t` và trả `delta_init`. `t ≤ _t` thì trả giá trị hiện tại, không lùi.
  - `reset(delta_init_rad=None)`, thuộc tính `last_rate_rad_s`.
- Mô hình: lệnh hiệu dụng = lệnh mới nhất có `t_cmd ≤ t − dead_time`; chưa có lệnh nào thì `delta_init`. Sau đó trễ bậc nhất rồi giới hạn tốc độ như `gimbal_model.py:50-52`, chia bước con ≤ 5 ms để kết quả không phụ thuộc nhịp gọi.
- `slow_factor`: `rate/slow`, `lag×slow`, `dead_time×slow`.
- `SimGimbalPort(servo)`: `command(t, delta_rad)`; `angle(t) -> float`; `last_cmd` (rad); `rate()` (rad/s); `reset()`. Không cần lớp cha.
- Config (SỬA `dtrack\config.py`; chỉ bước này đụng file đó, thêm TẤT CẢ trường mới của 3/4/4b một lượt):
  - `GimbalConfig` mới ở `AppConfig.gimbal` (thêm sau `config.py:130`): `enabled=False`; `delta_min_deg=10`, `delta_max_deg=90`, `delta_init_deg=90`; `hold_offset_deg=0.0` (+ = mục tiêu nằm dưới tâm khung); `frozen=False` (đối chứng khớp đứng yên: luôn lệnh `delta_init_deg`); `rate_dps=300`, `lag_s=0.05`, `dead_time_s=0.02`, `quant_deg=0.1`, `slow_factor=1.0`.
  - `GuidanceConfig` thêm sau `config.py:37`: `elev_ramp_enabled=False`, `elev_ramp_dps=2.0`. Điểm cuối của dốc dùng lại `target_elev_ref_deg`.
  - `AppConfig.__post_init__` (`config.py:132-136`): nếu `gimbal.enabled` thì `camera.tilt_up_deg=0`, rồi `guidance.cam_tilt_up_deg` đồng bộ (đặt trước dòng 134), `elev_accel_comp=0`.
  - `validate()` (`config.py:153`): cấm hai cờ khớp cùng bật; `0<min<max≤90`; `min≤init≤max`; `rate>0`; `lag,dead_time,quant≥0`; `slow_factor>0`; `elev_ramp_dps>0`.
  - Hồ sơ khớp chủ động trong `PROFILES`: dựng sau khi việc khoảng cách 15 m xong.
- Test đơn vị: (1) δ không vượt [min,max] dù lệnh ngoài; (2) nhảy 40° trong 10 ms thì |Δ| ≤ rate·dt; (3) sau 1 τ đạt 63,2% (rate lớn); (4) lệnh không có tác dụng trước `t_cmd+dead`; (5) lệnh 45,04° với quant 0,1 ra 45,0°; (6) `slow_factor=2` thì thời gian đáp ứng gấp ~2; (7) kết quả như nhau khi gọi 30 Hz hay 200 Hz (sai ≤ 0,1°); (8) `t` lùi hoặc lặp không đổi trạng thái; (9) chưa lệnh thì giữ `delta_init`; (10) `reset`; (11) config: mặc định không đổi hành vi, `__post_init__`, `validate`, nạp JSON.

## Bước 4: GimbalController
- File mới `dtrack\gimbal_control.py`; cần `dtrack\gimbal.py`.
  - `GimbalPort` (Protocol): `command(t, delta_rad)`, `angle(t) -> float`.
  - `GimbalCommand` (frozen dataclass): `t`, `delta_cmd_rad`, `sat: bool`, `mode` ("init"|"track"|"coast"|"hold"|"hold_last"|"frozen"), `elev_los_rad: Optional`, `elev_aim_rad: Optional`.
  - `GimbalController(cfg: GimbalConfig)`: `reset()` và `step(t, q_body, track: TrackState) -> GimbalCommand`.
- Luật mỗi chu kỳ (30 Hz, `app.run`, sau `sup.step`):
  - `frozen`: δ=`delta_init`.
  - TRACK/COAST có `los_ned` hợp lệ (norm ≥ 0,5): `elev_los=asin(clip(−u_z/|u|))`, `aim=elev_los+hold_offset`, `δ,sat=elev_to_delta(q_body, aim, δmin, δmax)`. Nhớ `last_aim`, `locked=True`.
  - SEARCH/LOST chưa từng khóa: δ=`delta_init`, mode "init".
  - SEARCH/LOST sau khi đã khóa: `elev_to_delta(q_body, last_aim)`, mode "hold" (giữ hướng nhìn so với đường chân trời khi thân đổi). Giai đoạn 2 sẽ thay bằng quét.
  - `elev_to_delta` ném ValueError: bắt, trả lệnh trước, mode "hold_last". Không ném ra ngoài.
  - Không có vòng I, không tự giới hạn tốc độ (servo lo).
- Test đơn vị: (1) θ=30°, elev −12° → δ=72°; (2) `hold_offset=3°` thì aim = elev_los + 3°; (3) θ=0, elev −12° → δ=90°, `sat=True`; (4) SEARCH chưa khóa → `delta_init`, mode init; (5) khóa rồi LOST, θ đổi 30°→10° → δ tăng 20°, aim giữ nguyên; (6) COAST dùng LOS như TRACK; (7) `frozen`; (8) q hoặc LOS NaN không ném, mode `hold_last`; (9) `reset` về init; (10) giới hạn tùy chỉnh; (11) vòng kín với `SimGimbalPort` và `camera_attitude`: mục tiêu cố định, thân lắc ±10°, khớp lý tưởng thì LOS trong ±0,5° quanh tâm khung; khớp chậm ×2 thì sai số có chặn.

## Bước 4b: chuyển tiếp sau khi khóa
- File mới `dtrack\elev_ramp.py`: `ElevRefRamp(final_deg, rate_dps, dt_max_s)`.
  - `update(t, elev_los_rad: Optional) -> Optional[float]` (độ). Chưa khởi động mà `elev_los` hợp lệ thì value=elev_los (lần TRACK đầu sau `reset`). Đã khởi động thì tiến về `final` với bước ≤ `rate·min(t−t_prev, dt_max)`, hai chiều.
  - `value`, `reset()`. Không khởi động lại sau khi mất mục tiêu.
- SỬA `dtrack\guidance.py`:
  - `compute_guidance_ex` (`:73-77`) thêm `elev_ref_deg: Optional[float]=None`. Khác None thì tại `:179-180` bỏ cắt ±`elev_ref_max_deg` và bỏ phần bù gia tốc, dùng thẳng giá trị đó.
  - `Guidance.__init__/reset` (`:285-294`) tạo và reset ramp nếu `cfg.elev_ramp_enabled`.
  - `Guidance.step` (`:340`) gọi `ramp.update(track.t, elev_los)` trước `compute_guidance_ex` (`:361`). `step_blind` (`:326`) gọi `ramp.update(t, None)` rồi truyền giá trị đó (`:334`). Ramp chưa khởi động thì `elev_ref_deg=None` (đường cũ).
  - Thuộc tính `last_elev_ref_deg` để bước 5 ghi log. Cờ tắt thì kết quả y hệt cũ.
- Test đơn vị: (1) khởi động từ elev đo, không nhảy; (2) bước ≤ rate·dt, đơn điệu, dừng đúng `final`, cả hai chiều; (3) không khởi động khi chưa có TRACK; (4) `t` lặp/lùi không đổi; (5) `dt` lớn bị chặn bằng `dt_max`; (6) `reset`; (7) NaN không làm hỏng; (8) ramp tắt thì lệnh bit-bằng bản cũ; (9) ramp bật, elev_los > e_ref thì vận tốc đứng dương (xuống); lệnh leo ≤ `climb_max` (`:272`); (10) `step_blind` vẫn dùng ramp.

## Bước 5: nối vào app + `gimbal.csv`
- SỬA `dtrack\app.py`:
  - `App.__init__` (`:49-65`) thêm `gimbal_port=None`, `gimbal_logger=None`; tạo `GimbalController` nếu `cfg.gimbal.enabled`. Bật mà thiếu port thì ValueError.
  - `run` (`:93-98`), mỗi chu kỳ: `δ=port.angle(now)` → `own_cam=replace(own, q=camera_attitude(own.q, δ))` → tracker (vẫn tự nội suy theo `t_capture`, `tracker.py:136-145`) → supervisor → `gc=ctrl.step(now, own.q_world_body, track)` → `port.command(now, gc.delta_cmd_rad)` → `gimbal_logger.log_gimbal(...)`.
  - `own is None` thì không lệnh. Nhánh `GimbalModel` cũ `:95-96` giữ nguyên.
  - `build_source(args, cfg, gimbal_port=None)` (`:155`): giữ tương thích hai tham số (`test_target_shape.py:286`).
  - `main` (`:187-203`) tạo port một lần, đưa cho nguồn và App; `gimbal.csv` cùng thư mục với `--log`; đóng trong `finally`.
- SỬA `simtools\sim_truth_source.py`: `__init__` (`:57-62`) thêm `gimbal_port=None`; `_own` (`:97-102`): có port thì `q = camera_attitude(q, port.angle(now))`; nhánh cũ giữ.
- SỬA `dtrack\logger.py`: dòng `:42` đổi `COLUMNS` → `self.columns`; thêm `GimbalLogger(CycleLogger)` với cột `t, mode, delta_cmd_deg, delta_act_deg, delta_rate_dps, elev_los_deg, elev_aim_deg, elev_ref_deg, sat, theta_deg` (θ suy từ ma trận, `asin(R[2,0])`). `app_log.csv` không đổi cột.
- Không sửa shell.
- Test đơn vị (link, source, port giả): (1) cờ tắt: không có `gimbal.csv`, hành vi cũ; (2) cờ bật: `port.angle` trước `tracker.update`, `command` sau `sup.step`, q cho tracker bằng `camera_attitude`; (3) `own None` thì không `command`; (4) thiếu port → ValueError; (5) `gimbal.csv` đúng cột và số dòng; (6) `SimTruthSource` với port: mục tiêu trên trục quang rơi đúng tâm ảnh; δ sai 20° thì ra ngoài khung; (7) `build_source` hai tham số vẫn chạy; (8) hai cờ khớp cùng bật thì lỗi.

## Bước 6: bộ chấm đọc góc khớp thật
- SỬA `simtools\analyze_closed_loop.py` `b4_metrics` (`:90-210`):
  - `:97-98`, `:108-112`: đọc `gimbal` từ `app_cfg.json`, mặc định từ `GimbalConfig()`; `gimbal.enabled` thì `Rbc=make_camera(0)`.
  - Thêm `load_gimbal_csv(path)` trả `(t, δ_act_rad, sat)`.
  - `:125-127`: `qc = camera_attitude(qb, np.interp(T[i], tg, dg))` thay cho `gm.step`.
  - Thiếu `gimbal.csv`, hoặc >2% mẫu truth trong [t_go, t_end] nằm ngoài khoảng thời gian của file: ném lỗi; nhánh `except` ở `:490` biến thành `b4res` rỗng và tiêu chí "ra khỏi khung" FAIL (không đoán).
  - `:182-187`: ghi `res["gimbal"]` = {δ min/max/trung vị, `rate_max`, `n_sat_enter`, số mẫu chạm giới hạn, theo từng pha: δ trung vị/min/max, θ trung vị/max, tốc độ mục tiêu trung vị} và dòng "B4 khớp gật (chủ động)".
  - Không có `gimbal.enabled` thì mã cũ giữ nguyên.
- Test đơn vị (`tests\test_analyze_gimbal.py`): (1) truth + `gimbal.csv` khớp thì ra khung bằng 0; (2) δ lệch 40° thì ra khung và FAIL; (3) thiếu `gimbal.csv` thì FAIL, không crash; (4) số lần chạm giới hạn đúng với chuỗi `sat` dựng sẵn; (5) không có khóa `gimbal` thì kết quả bằng cũ; (6) thống kê theo pha đúng giá trị tay.

## Thứ tự
- Việc khoảng cách 15 m (đụng `config.py` PROFILES, `analyze_closed_loop.py`) làm TRƯỚC bước 3 và bước 6.
- Đợt A (song song): bước 2 (`dtrack\gimbal.py`) ‖ việc 15 m; rồi bước 3 (`servo_model.py` + `config.py`).
- Đợt B (song song, file rời nhau): bước 4 (`gimbal_control.py`) ‖ 4b (`guidance.py` + `elev_ramp.py`) ‖ bước 6 (`analyze_closed_loop.py`).
- Đợt C: bước 5 (`app.py`, `sim_truth_source.py`, `logger.py`).

## Rủi ro và giả định
- δ_max=90° nên quad treo/chậm (θ≈0) không nhìn xuống được: `sat=True`. Mục tiêu ở −12° cách mép khung dọc (±17,4°) chỉ 5°, ở −15° còn 2,4°. Nếu bước 7 thấy mất khung lúc chuyển thì thêm cổng dừng dốc khi `sat` hoặc lệch tâm quá ngưỡng.
- Lệnh khớp chỉ theo góc nâng LOS, bỏ qua lệch phương vị.
- Tracker nội suy camera ở 30 Hz trong khi khớp quay tới 300°/s: sai số đo ở bước 7.
- `__post_init__` ghi đè `camera.tilt_up_deg` khi `gimbal.enabled`: ghi vào tài liệu.
- `app_log.csv` và `gimbal.csv` giả định cùng đồng hồ với truth: 07 kiểm ở lần chạy đầu.
- Giả định cần đo: MG90S `rate_dps` 300, `lag_s` 0,05, `dead_time_s` 0,02, `quant_deg` 0,1; tốc độ dốc 2°/s; phản hồi góc khớp coi như hoàn hảo.
- Phương án đã loại: mở rộng `GimbalModel` cũ; PID trên sai số pixel; đặt dốc 4b trong GimbalController; ghi gimbal vào `app_log.csv`; hai mô hình khớp riêng; dựng δ qua Euler; khởi động lại dốc mỗi lần mất mục tiêu.
