# Thiết kế khối tìm lại mục tiêu (bước 1 giai đoạn 2, 02 planner, 2026-11-19)

Trạng thái: XONG CÒN NGHI NGỜ. 02 không có công cụ chạy lệnh: các số hình học ở (f) là tính tay. Chưa đọc `sim/target.py` và các test dẫn đường chi tiết. Vị trí dòng ở `guidance.py` lệch sau khi bước 6 sửa, nên chỉ theo tên hàm. 08 rà bản này ở bước 11.

## (a) Pha, nơi đặt, ai gọi ai

**Quyết định cấu trúc**
- Đồng hồ đợt mất, RTL và ghép lệnh nằm ở `supervisor.py` (chỗ vốn giữ `_lost_t`, `_rtl_sent`, `supervisor.py:73-75,182-186`).
- Logic thuần (quét, leo) nằm ở `dtrack/search.py` mới, để test không cần guidance.
- Khi `search.enabled=False`, nhánh cũ giữ nguyên từng dòng. Nhánh mới là phương thức riêng `_step_search`, thay cho khối `supervisor.py:132-188`.

**`search.py` (chữ ký)**
- `tri_sweep(s, start, lo, hi, first_dir) -> float`: hàm thuần, sóng tam giác đi từ `start` về phía `first_dir`, phản xạ ở `lo`/`hi`.
- `SearchEpisode(cfg, coast_follow_s)`: `update(t, tracking: bool, had_target: bool) -> EpisodeTick(ep_id, ep_s|None, phase|None, closed, expired)`; `reset()`.
- `SearchPlanner(cfg, delta_min_rad, delta_max_rad)`: `begin(t, own, yaw0, delta0, p_stop_ned|None)`; `step(t, own, phase) -> SearchOutput(vel_ned, yaw_rad, scan_delta_rad, climb_m, reason)`.
- `SearchInfo`: ep_id, ep_s, phase, run_s, closed, climb_m, scan_delta_rad, r_hat.

**Điểm chạm ở file khác**
- `SupervisorInput.gimbal_delta_rad: Optional[float]=None` (app điền `delta_act`).
- `SupervisorOutput.search: Optional[SearchInfo]=None`.
- `Supervisor.__init__(cfg, gcfg, scfg=None, gimbal_cfg=None)`.
- `GimbalController.step(t, q_body, track, scan_delta_rad=None)`: khác None thì kẹp vào [min,max] và trả mode `"scan"`, kiểm trước nhánh TRACK/COAST (`gimbal_control.py:55-71`).

**Mỗi chu kỳ (`app.run`)**: 1. `sup.step` chạy watchdog; 2. `SearchEpisode.update`; 3. chọn pha; 4. tạo lệnh; 5. `gimbal_ctrl.step(..., scan_delta_rad=out.search.scan_delta_rad)`; 6. ghi `search.csv`.

**Pha** (`ep_s` = giây từ đầu đợt mất)

| Pha | Điều kiện | Lệnh |
|---|---|---|
| TRACK | tracker TRACK | `guidance.step` như cũ; đồng hồ KHÔNG đặt lại |
| 0 | `ep_s ≤ coast_follow_s` (4 s) | như cũ: COAST dùng `step`, tracker bỏ thì `step_blind`; thêm luật ở (e) |
| 1 | `4 < ep_s < total_s`, và (`climb_m=0` hoặc `ep_s < climb_start_s`) | `Guidance.step_hover` cho vx, vy; yaw quét; khớp quét. Trạng thái giữ `LOST`, lý do `search:p1` |
| 2 | `climb_m>0`, `ep_s ≥ climb_start_s`, có `p_stop` và cách nó ≥ 8 m theo phương ngang | vx, vy như pha 1; vz leo `min(climb_rate, 0.5·(climb_m−tăng))`, dừng khi còn ≤ 0,25 m; khớp quét dải thấp |
| RTL | đợt còn mở và `ep_s > total_s` | `request_rtl` một lần (tái dùng `_rtl_sent`), bất kể trạng thái tracker |

- Không thêm giá trị `SupState`: `analyze_closed_loop.py:563` đếm theo `lost/search`.
- Chưa từng thấy mục tiêu: giữ nguyên, `lost_rtl_s` tính từ lúc engage.
- Pha 1 và 2 quét theo góc khớp δ trực tiếp, không ổn định theo góc nâng (`elev_to_delta` bão hòa sát giới hạn; lúc treo θ≈0 nên góc nâng trục camera = 90°−δ).

## (b) Khóa cấu hình mới (đều ở `config.py`, một lượt)

**`SearchConfig`**, gắn vào `AppConfig.search` (`_fill` nạp được dataclass lồng nhau, `config.py:235`).

| Khóa | Mặc định | Ràng buộc `validate()` |
|---|---|---|
| `enabled` | False | bật thì bắt buộc `gimbal.enabled` |
| `total_s` | 20.0 | `> supervisor.coast_follow_s`, ≤ 300 |
| `reacquire_hold_s` | 1.0 | 0,2–10 |
| `climb_m` | 0.0 | ≥ 0, hữu hạn |
| `climb_start_s` | 10.0 | trong (`coast_follow_s`, `total_s`) |
| `climb_rate_mps` | 2.0 | 0 < x ≤ `guidance.climb_max_mps` |
| `scan_rate_dps` | 60.0 | 0 < x ≤ 0,5·`gimbal.rate_dps`/`slow_factor` |
| `scan_lo_deg` / `scan_hi_deg` | 10 / 110 | `gimbal.delta_min ≤ lo`, `hi ≤ delta_max`, `hi−lo ≥ 20` |
| `climb_scan_lo_deg` | 70.0 | `scan_lo ≤ x < scan_hi` |
| `yaw_amp_deg` | 45.0 | 0–90 (0 = không quét yaw) |
| `yaw_rate_dps` | 20.0 | 0 < x ≤ `guidance.yaw_rate_max_dps` |

**`GuidanceConfig`** (0 = tắt, giữ hành vi cũ)

| Khóa | Mặc định | Ràng buộc |
|---|---|---|
| `blind_floor_m` | 0.0 | ≥ 0 |
| `blind_back_margin_m` | 2.0 | ≥ 0 |
| `blind_target_decel_mps2` | 3.0 | > 0 |
| `blind_v_cap_mps` | 0.0 | 0 hoặc ≤ `v_max_mps` |

**Hồ sơ mới `search_plane_r15`**: sao chép `accept_plane_r15`, bỏ `camera.gimbal_enabled`, thêm `gimbal.enabled`; camera Wide tường minh (fx 933, 2304×1296); `search.enabled=True`, `blind_floor_m=8`, `blind_v_cap_mps=12`. Nếu bước 7 đã có hồ sơ Wide + realdet thì dùng làm gốc.

## (c) Mẫu quét
- Giới hạn servo: `config.py:122` `rate_dps=300` (GIẢ ĐỊNH chưa đo); `lag_s=0,05`, `dead_time_s=0,02` (`:123-124`); `delta_min/max=10/110` (`:117-118`, cùng `gimbal.py:16-17`).
- Khớp: 60°/s (0,2 lần 300). Sai số bám tam giác ≈ 60×0,07 = 4,2°. Chu kỳ đầy đủ 2×100/60 = 3,3 s.
- Thứ tự: từ δ hiện tại, về `hi` (nhìn xuống) trước, rồi `lo`, lặp.
- Yaw: tâm = yaw lệnh lúc bắt đầu pha 1, biên ±45°, 20°/s, bắt đầu về phía +, chu kỳ 9 s.
- Phủ: Wide HFOV ≈ 102°, VFOV ≈ 69,6°. Lúc treo δ=10..110° ứng góc nâng +80..−20°, phủ dọc −54,8..+114,8°.
- Với tracker: cần 3 lần khớp (`tracker.py:34`) sau khi reset ở 3 s (`:36`). Mục tiêu trong khung mỗi lượt quét ≥ 0,8 s.

## (d) Đợt mất và bắt lại
- Mở đợt: chu kỳ đầu có `_had_target` mà tracker báo COAST, LOST hoặc SEARCH, và không có đợt đang mở (chậm hơn lần khớp cuối 0,25 s, `tracker.py:35`; C7 cho ±0,5 s).
- Kết thúc (bắt lại): TRACK liên tục ≥ `reacquire_hold_s` = 1,0 s.
- Chớp TRACK ngắn hơn: chỉ đặt lại bộ đếm chuỗi TRACK, không đặt lại đồng hồ đợt.
- Bỏ `_lost_t=None` ở `supervisor.py:140` trong nhánh mới.
- `_reset_engaged` và ABORT hồi phục (`:127-130`) đóng đợt.

## (e) An toàn lúc mù
- E1: không có `_mem` hợp lệ thì phanh, không bay mù (`_mem` chỉ ghi ở nhánh `valid`).
- E2: `_mem` thêm vị trí của mình (`_update_mem(t, info, own)`). `Guidance.predicted_rel(t, own) -> Optional[Vec3]`: vị trí mục tiêu = P0 + v̂0·s(dt), mục tiêu hãm 3 m/s² ngay từ lúc mất (dừng ở v0²/2a); vector tương đối tính từ `own.pos_ned` thật. `Guidance.stopped_target_ned(t, own)`: vị trí mục tiêu khi dừng hẳn. Hai hàm thay khoảng cách đóng băng ở `step_blind` và nhánh COAST. Ghi `Guidance.last_r_hat`.
- E3: nhánh `blind_floor_m>0` dùng cfg hiệu dụng `range_back_m = floor + margin` (10 m), `range_min_m = floor` (8 m); lùi khẩn dùng logic `min_range` sẵn có.
- E4: vận tốc ngang bay mù ≤ `blind_v_cap_mps`, kẹp ở `_safe_hold`.
- E5: `Guidance.step_hover(track, own)` = `step_blind` với `v_t_hold=0`: treo, vẫn lùi nếu r̂ < 10 m. Hết `_mem` (8 s, `config.py:55`) thì chỉ treo.
- E6: pha 2 chỉ leo thẳng đứng; yêu cầu cách `p_stop` ≥ 8 m ngang. Không biết `p_stop` thì không leo.
- Với E3–E5: mục tiêu thật lùi nhanh hơn mô hình (3 m/s²) thì không tránh được (rủi ro 3).

## (f) Ba kịch bản SITL

**Thay đổi `sim_helper.py`, `run_closed_loop.sh`**
- `--post-s` (mặc định 15): kết thúc ở `blackout_end + post_s` (hiện `sim_helper.py:306-322` cắt ở `t_ws + window + 5`).
- `--blackout-dive`: tại `event_at` tạo cả file `blackout` và `dive`; ghi `ev["blackout_dive"]`, `ev["t_dive_cmd"]`.
- `run_closed_loop.sh:40` cho `SCENARIO=blackout` cùng `DIVE_DEG`; thêm env `BLACKOUT_S`, `EVENT_AT`, `POST_S`.
- `analyze_closed_loop.py` bỏ qua `dive_and_final_scoring` khi `ev.blackout_dive`.

| Kịch bản | Cấu hình | Blackout | Mong đợi |
|---|---|---|---|
| S1 bay thẳng | 10 m/s, `STRAIGHT=1`, `event_at`=30 | 8 s | bắt lại ≥ 4/5 seed |
| S2 cắm xuống | `DIVE_DEG=25`, `ALT=70`, dive cùng lúc blackout | 8 s | bắt lại (ước 9,5–11 s, chưa kiểm) |
| S3 không trở lại | như S1 | 25 s | RTL ở 20 ± 0,5 s |

**Hình học tính tay (chưa chạy)**, giả định drone chạy ~21 m trước khi dừng:
- S1: khoảng cách ≈ 10·t − 6 m: 34 m lúc 4 s, 74 m lúc 8 s, 94 m lúc 10 s, 114 m lúc 12 s. Góc nâng ≈ 0°, phương vị không đổi; yaw ±45° nằm trong HFOV ±51°. Khớp thấy mục tiêu khi δ ∈ [59°, 110°] (≈ 51% chu kỳ).
- S2 lúc 8 s: dx≈65 m, dz≈33–37 m, khoảng cách ≈ 75 m, góc nâng −26° đến −29°; cần δ ∈ [85°, 110°] (≈ 25% chu kỳ).
- Điểm yếu: hold cũ (boresight +4°, mép dưới −30,8°) có thể vẫn thấy S2 sát mép → cần đối chứng `search.enabled=False`.
- Khoảng cách nhận dạng: 2,16 m ở fx 933, cách 126 m còn 16 px. Blackout dài hơn ~13 s có thể vượt khoảng nhận dạng (phụ thuộc realdet, GIẢ ĐỊNH).

## (g) Bộ đo trong `analyze_closed_loop.py`
Hàm mới `reacq_metrics(a, truth, app, search_rows, ev)`, gọi tại `:575` (nhánh blackout) và khi `ev.blackout_dive`.

| Chỉ số | Cột dùng | Định nghĩa |
|---|---|---|
| `t_ep0` | `search.csv: ep_id, ep_s` | mốc đầu đợt |
| `reacq_s` | `closed`, `run_s` | thời điểm hàng đầu của chuỗi TRACK đóng đợt − `t_ep0` |
| `rtl_s` | `app_log: rtl` | hàng `rtl=1` đầu tiên − `t_ep0` |
| `d3_blind_min` | `truth: d3` | min trong [`t_ep0`, bắt lại hoặc RTL] |
| `climb_max` | `truth: ch_alt` | max − giá trị đầu đợt |

Dòng in: `TIM LAI: dot=%d bat dau t=%.2f | %s | d3 min luc mu=%.2f m | do cao tang max=%.2f m | pha max=%d` (trường thứ hai: `bat lai sau %.2f s`, `RTL sau %.2f s` hoặc `chua ket thuc`). Tiêu chí: `crit("RTL o 20 +- 0.5 s", …)` (chỉ S3), `crit("d3 luc mu >= 8 m", …)`, `crit("do cao tang <= climb_m + 1", …)` (khi `climb_m>0`). `search.enabled` đọc từ `app_cfg.json` như `cfg_gimbal_enabled` (`:258`). Thiếu `search.csv` khi bật thì FAIL kèm `khong do duoc`.

## (h) Cột log mới
`app_log.csv` KHÔNG đổi (`tests/test_app_gimbal.py:38,192,361` ghim cột). Thêm `SEARCH_COLUMNS` và `SearchLogger(CycleLogger)` trong `logger.py`, ghi `search.csv` cạnh `--log` (mẫu `GimbalLogger`, `logger.py:91-103`): `t, ep_id, ep_s, phase, run_s, closed, climb_m, scan_delta_deg, yaw_cmd_deg, r_hat`. `App.__init__` thêm `search_logger=None`; `main` tạo khi `cfg.search.enabled`. `gimbal.csv` chỉ thêm mode `"scan"`.

## Test theo quyết định (cho bước 13)
| File test | Ca |
|---|---|
| `test_search_episode.py` | đồng hồ tuyệt đối; chớp TRACK < 1 s không đặt lại; TRACK ≥ 1 s đóng đợt; RTL ở 20 ± 0,5 s |
| `test_search_planner.py` | `tri_sweep` biên và phản xạ; quét trong [10°,110°] ≤ 60°/s; pha 2 tăng ≤ `climb_m` + 1 m; không leo khi không có `p_stop`; không leo khi p_stop gần hơn 8 m |
| `test_guidance_blind.py` | không `_mem` thì phanh; mô hình điểm khối, trễ FC 1 s, mục tiêu hãm 3 m/s²: d ≥ 8 m; cắt vận tốc ở `blind_v_cap_mps`; `blind_floor_m=0` thì bit-bằng cũ |
| `test_gimbal_scan.py` | `scan_delta_rad` kẹp vào [min,max]; mode `scan` |
| `test_analyze_reacq.py` | csv dựng sẵn → `reacq_s`, `rtl_s`, `d3_blind_min` đúng giá trị tính tay |

## (i) Phương án đã loại và rủi ro
**Đã loại:** đặt hết trong `supervisor.py`; thêm `SupState.REACQ`; thêm cột vào `app_log.csv`; mặc định `search.enabled=True` (RTL đổi 10 → 20 s); quét theo góc nâng ổn định; giữ khoảng cách đóng băng.

**Rủi ro**
1. Mất kiểu cụm (realdet) có thể cộng dồn đợt mất ≥ 20 s dù vẫn bám phần lớn thời gian → RTL oan; `reacquire_hold_s` cần quét thử.
2. Tracker cắt ở 3 s buộc xác nhận lại 3 lần khớp giữa lúc quét.
3. `blind_target_decel=3` là giả định; mục tiêu thật hãm 8 m/s² (`config.py:21`) có thể vượt sàn 8 m.
4. `pos_ned` của FC nhảy thì r̂ sai.
5. Lúc phanh θ có thể ±15°, lệch vùng phủ.
6. Mục tiêu hãm nhẹ 1,5 m/s² + blackout hiện có thể đã vi phạm sàn (tính tay d ≈ 7,5 m lúc 4 s): chính là ca blackout:soft của bước 14; cần chạy trước/sau.

**Chưa kiểm:** ngưỡng kích thước nhận dạng; thời gian bắt lại S1/S2; `pos_ned` thật có đủ ổn định.

## Đề xuất của 02
- Bước 16 thiếu các file `app.py`, `logger.py`, `run_closed_loop.sh`, README (bảng khóa cấu hình).
- Bước 18 thêm S1/S2 với `search.enabled=False` làm đối chứng.
- 07 viết trước test "mục tiêu hãm 1,5 m/s² + blackout, d3 ≥ 8 m" làm số đo "trước" cho C6.

---

# SỬA THEO PHẢN BIỆN CỦA 08 (2026-11-19, trưởng phòng chốt). Phần này THẮNG phần trên khi mâu thuẫn.

08 kết luận: hình học đúng (tự tính lại khớp), cấu trúc hợp lý, nhưng NÊN SỬA trước khi viết test. Các quyết định:

**S-1 (Nghiêm trọng, C6): mô hình mục tiêu lúc mù phải bảo thủ.** Mục tiêu trong mô phỏng hãm ~8 m/s² (`config.py:22`), không phải 3. Với giả định 3 m/s², drone có thể dừng cách mục tiêu thật ≈ 0 m. Sửa:
- `blind_target_decel_mps2` mặc định 8.0.
- Khoảng cách dự đoán dùng cho an toàn (E2, E3, E5) là GIÁ TRỊ NHỎ NHẤT của hai mô hình: mục tiêu hãm `blind_target_decel_mps2` ngay lúc mất, và mục tiêu giữ nguyên vận tốc nhớ. Tức luôn giả định mục tiêu ở vị trí gần mình nhất trong hai khả năng.
- Thêm kịch bản S4: mục tiêu phanh 8 m/s² đúng lúc mất hình (blackout 8 s). Chạy ở bước 14 (số đo "trước", mã chưa có tìm lại) và bước 18 (sau). Test đơn vị C6 tương ứng trong `test_guidance_blind.py` (mục tiêu hãm 8 m/s² và mục tiêu hãm 1,5 m/s²).

**S-2 (C7): cách đo RTL.** Phần "một phát hiện giả không đặt lại đồng hồ" kiểm bằng test đơn vị `SearchEpisode` (blackout trong SITL chặn cả phát hiện giả, `sim_truth_source.py:88-91`). Trong `analyze_closed_loop.py`, thời điểm RTL đối chiếu với mốc độc lập `events.json: blackout_start` (cộng trễ ~0,3 s của tracker), không chỉ với `search.csv` (đồng hồ của chính mã).

**S-3: hành vi khi tracker báo TRACK trong pha ≥ 1 mà chưa đủ `reacquire_hold_s`.** Drone TIẾP TỤC treo (`step_hover`), không đuổi; khớp NGỪNG quét và bám mục tiêu (`scan_delta_rad=None`, GimbalController chạy nhánh TRACK như thường); yaw giữ nguyên giá trị quét hiện tại. Đủ 1,0 s TRACK liên tục thì đóng đợt, trả quyền cho `guidance.step`. TRACK rớt trước đó thì quét tiếp từ δ hiện tại (không nhảy về điểm đầu). Lý do: mỗi lượt quét mục tiêu chỉ nằm trong khung ~0,8 s < 1,0 s, nếu vẫn quét thì không bao giờ đủ hold. Trong pha 0 (≤ 4 s) giữ hành vi cũ.

**S-4: bổ sung danh sách test bước 13.** `validate()` cho `SearchConfig` và các khóa `GuidanceConfig` mới; `search.enabled=False` cho chuỗi `SupervisorOutput` giống hệt cũ (RTL ở 10 s); ABORT hồi phục đóng đợt; RTL chỉ gửi một lần; `ep_id` tăng khi mở đợt mới; mục tiêu chưa từng thấy thì không mở đợt; biên đúng 1,0 s; nối app (`gimbal_delta_rad`, `scan_delta_rad`); `SearchLogger` đủ cột và `app_log.csv` không đổi; `pos_ned` nhảy (r̂ không được tin mù quáng: bước nhảy vị trí > ngưỡng thì coi như không có khoảng cách hợp lệ → phanh); C6 hãm 8 m/s²; quét 60°/s với `SyntheticDetector` + tracker thật vẫn xác nhận được 3 lần khớp (nếu không, hạ `scan_rate_dps` mặc định và ghi lại).

**S-5: hồ sơ dùng cho SITL.** `PROFILES["realdet"]` và `accept_plane_r15` dùng khớp kiểu cũ (`camera.gimbal_enabled`) nên `report_run.py:71` đánh dấu không hỗ trợ. Các lần chạy bước 14 và 18 dùng cấu hình JSON dựa trên `onboard/simtools/configs/plane_r15_gimbal_e12_wide.json` (khớp kiểu mới `gimbal.enabled`, camera Wide) cộng khối `synthetic` của realdet; hồ sơ `search_plane_r15` cũng dựng từ gốc này (đúng như mục (b): bỏ `camera.gimbal_enabled`, thêm `gimbal.enabled`).

**S-6: giới hạn của realdet.** 08 mô phỏng tracker thật: hold 1,0 s đóng đợt tốt khi bbox ≥ 16 px (≤ 126 m); ở ≤ 12 px (≥ 168 m) 1,9–42% đợt kéo quá 20 s → RTL oan. Bám bình thường ở 15 m (≥ 100 px) không bị. Hệ quả: không dùng blackout dài hơn ~13 s cho kịch bản mong đợi bắt lại (S1 lúc 12 s đã 114 m, 17,8 px, p 0,59). Rủi ro 1 ở mục (i) viết "cộng dồn" là sai: đợt đóng sau mỗi 1 s TRACK.

**S-7: số liệu 08 tính lại** (fx 933, sải 2,16 m, bảng realdet): 74 m → 27,5 px, p 0,79; 94 m → 21,6 px, 0,72; 114 m → 17,8 px, 0,59; 126 m → 16,1 px, 0,505; 244 m → 8,3 px, 0,145. Dải δ nhìn thấy mục tiêu: S1 ≈ [55°, 110°]; S2 [83,5°, 110°]. Blackout 8 s: pha 1 chạy ≈ 3,75 s ≈ 1,1 chu kỳ quét trước khi hình trở lại; bắt lại rồi đóng đợt ước 9–10 s. Tracker rớt TRACK khi bỏ lỡ ≥ 5 khung liên tiếp. Giả định "drone chạy 21 m trước khi dừng" chỉ đúng khi có E2.

**S-8: dòng dẫn lệch 1** sau thay đổi bước 7: `config.py:21` nay `:22`, `:55` nay `:56`, `:117-124` nay `:118-125`. Thêm vị trí vào `_mem` (E2) phải sửa cả chỗ unpack 4 phần tử trong `step_blind`.

**S-9: các điểm 07 tự chốt khi viết test bước 13a (trưởng phòng chấp nhận, mã viết theo test).** `closed` chỉ True đúng một tick (tick chuỗi TRACK đạt hold), tick sau `ep_s`/`phase` là None; `expired` chỉ khi `ep_s > total_s`. `phase` chỉ theo `ep_s` (pha 2 khi `climb_m > 0` và `ep_s ≥ climb_start_s`); `p_stop` chỉ chặn leo trong planner. `vel_ned` của planner chỉ có nghĩa ở `vz` (vx, vy do `step_hover` cấp); `climb_m` trong output là độ cao đã tăng lũy kế. `yaw_amp_deg=0` thì yaw giữ `yaw0` hoặc None. Tạm ngừng quét (S-3): supervisor không gọi `planner.step`; khi gọi lại planner tiếp từ δ cuối của chính nó và `dt` đầu tiên bị kẹp (không nhảy theo thời gian nghỉ). `run_s` = độ dài chuỗi TRACK hiện tại. Ràng buộc `SearchConfig` chỉ áp khi `enabled=True`. Treo trong S-3: tốc độ ngang ≤ 0,3 m/s. `scan_delta_rad` kẹp trực tiếp, không phụ thuộc `q_body`. ABORT hồi phục: không còn đợt mở, RTL theo `lost_rtl_s` tính từ lúc hồi phục. Chữ ký: `tri_sweep(s, start, lo, hi, first_dir=±1)`, `SearchEpisode(cfg, coast_follow_s)`, `SearchPlanner(cfg, dmin_rad, dmax_rad)`, `Supervisor(cfg, gcfg, scfg, gimbal_cfg)`.

**S-10 (sau test bước 13b): ngưỡng lùi lúc mù phụ thuộc tốc độ.** 07 đo trên vòng mô phỏng điểm khối (trễ lệnh bậc nhất 1 s, gia tốc ngang cắt ở `a_back_mps2`, mục tiêu cách 15 m, cả hai bay 10 m/s): mã HIỆN TẠI để khoảng cách nhỏ nhất 1,02 m khi mục tiêu phanh 8 m/s² lúc mất hình, và 3,23 m khi hãm 1,5 m/s². Cài đúng chữ E3 (floor 8, margin 2 cố định) chỉ đạt 1,89 m; margin 6 → 6,31 m; margin ≥ 8 → 10,83 m; phanh ngay lúc mất → 11,25 m. Chốt: lùi/phanh khi r̂ < `blind_floor_m + blind_back_margin_m + d_dừng`, `d_dừng = v_tiến·blind_react_s + v_tiến²/(2·a_back_mps2)`, `v_tiến` = thành phần vận tốc drone hướng về vị trí dự đoán của mục tiêu (≥ 0). Khóa mới `GuidanceConfig.blind_react_s` mặc định 1,0 (GIẢ ĐỊNH, chưa đo), 0–5. `blind_back_margin_m` giữ 2,0.

**S-11: rủi ro đã biết, thiết kế KHÔNG phủ.** Mục tiêu phanh rồi quay đầu lao lại 5 m/s lúc drone đang mù: bản cài thử đo 1,02–1,06 m. Không mô hình nào trong E1–E6 bao được. Ca test giữ `xfail`. Ghi vào tài liệu ở bước 20.

**S-12: các điểm 07 tự chốt ở bước 13b (trưởng phòng chấp nhận).** `pos_ned` nhảy 50 m trong một chu kỳ thì phanh từ chu kỳ đó trở đi (ngưỡng cụ thể 05 chọn); `SearchLogger.log` nhận 10 giá trị đúng thứ tự cột, `None` ghi ô trống, `closed` ghi 1/0; `reacq_metrics` kiểm qua `main()` (dòng `TIM LAI:` và tiêu chí); RTL đối chiếu hai mốc: theo `search.csv` ≈ 20 s và `rtl − blackout_start` ≈ 20,3 s, mỗi mốc ±0,5 s; cấu hình JSON có `search: {enabled: false}` phải nạp được.

**S-13 (người dùng đổi tiêu chí C6, 2026-11-19; THẮNG S-1 và S-10 ở chỗ mâu thuẫn).** Nghiệm thu: mục tiêu bay đều lúc mất hình → d3 min ≥ 8 m; hãm nhẹ tới 3 m/s² → ≥ 6 m; phanh gấp 8 m/s² → chỉ đo. `blind_target_decel_mps2` mặc định 3,0. Trong công thức `d_dừng` của S-10, `v_tiến` là tốc độ TIẾP CẬN TƯƠNG ĐỐI (phương án B): vận tốc drone trừ vận tốc dự đoán của mục tiêu theo mô hình, chiếu lên hướng tới mục tiêu, lấy ≥ 0. Số của 07 trên bản cài thử (min m / khoảng cách tới mục tiêu thật lúc 4 s / lúc 8 s):

| Ca | HEAD | A (tuyệt đối) | B (tương đối, CHỌN) |
|---|---|---|---|
| Bay đều 10 m/s | 15,00 / 17,5 / 49,7 | 15,00 / 51,8 / 95,4 | 15,00 / 38,9 / 86,3 |
| Hãm 1,5 | 3,23 / 5,7 / 3,4 | 14,98 / 39,9 / 48,9 | 13,61 / 27,0 / 39,8 |
| Hãm 3,0 | 1,02 / 5,8 / 13,5 | 14,83 / 28,7 / 32,3 | 10,68 / 15,7 / 23,2 |
| Phanh 8,0 (chỉ đo) | 1,02 / 16,1 / 23,9 | 10,80 / 18,2 / 21,8 | 1,62 / 5,4 / 12,8 |

Lý do chọn B: đạt ngưỡng nghiệm thu và drone bị bỏ lại ít hơn A (ca bay đều 38,9 m so với 51,8 m lúc 4 s), lợi cho bắt lại. Cái giá đã biết: ca phanh gấp 8 m/s² còn 1,62 m (người dùng cho chỉ đo); ca bay đều drone vẫn bị bỏ lại xa hơn HEAD (38,9 so với 17,5 m lúc 4 s) vì mô hình giả định mục tiêu có thể hãm 3 m/s². Kịch bản SITL S4 đổi thành hai ca: hãm 3 m/s² (ngưỡng 6 m) và phanh 8 m/s² (chỉ đo).

**S-14 (người dùng chốt 2026-11-19; bổ sung S-13).** Khóa mới `GuidanceConfig.blind_grace_model_s`, mặc định 1,5 (0–3; 0 = hành vi cũ): khi tuổi bộ nhớ nhỏ hơn giá trị này, r̂ chỉ dùng mô hình "mục tiêu giữ nguyên vận tốc nhớ"; sau đó lấy min của hai mô hình (mô hình hãm vẫn tính từ lúc mất hình). Lý do (08 đo): với min ngay từ đầu, mất hình 1,5 s khi mục tiêu bay đều làm drone lùi và bị bỏ lại 52 m sau 8 s. Số vá thử của 08 với 1,5 s: mất hình 1,5 s giữ 15,1 m; bay đều 15,00 m; hãm 3 m/s² còn 6,83 m (mức yêu cầu 6); hãm 1,5 còn 12,12 m. Hạn chế đã biết: mất hình 2–3 s khi mục tiêu bay đều vẫn bị bỏ lại 57–107 m sau 8 s; 2,0 s làm ca hãm 3 m/s² còn 2,77 m nên không dùng.

**S-15 (người dùng chốt 2026-11-19 sau bảng đo đánh đổi; THẮNG S-13, S-14 về giá trị dùng trong hồ sơ).** Hồ sơ `search_plane_r15` TẮT cơ chế hãm phòng: `blind_floor_m = 0`, `blind_v_cap_mps = 0`. Cơ chế và các khóa `blind_*` vẫn giữ trong mã (mặc định tắt, có test), để bật lại khi cần. `validate()` bỏ luật "bật search thì `blind_floor_m > 0`". Lý do: bảng `onboard/simtools/out/_tradeoff/tradeoff.md`: mọi mức bật đều làm drone tụt lại khi hình chập chờn (kiểu khắc nghiệt: 10–12/12 seed > 30 m), còn tắt thì giữ 15–16 m. Cái giá đã chấp nhận: mục tiêu hãm 1,5–3 m/s² đúng lúc drone mù → áp sát ~1,0 m (số mô hình). Khi tắt: pha 0 bay tiếp theo vận tốc nhớ; pha ≥ 1 treo + quét.

**S-16 (giai đoạn 2b, 2026-11-20; đã sửa mã và đã rà; THẮNG phần trên về mẫu quét ở pha 1, tức mục (c)): không quét trước mốc `scan_start_s`.**
- Quy tắc: khóa mới `search.scan_start_s` mặc định 12,0 s tính từ đầu đợt tìm (= COAST đầu). Ràng buộc khi bật tìm lại: `supervisor.coast_follow_s` < `scan_start_s` < `search.total_s` (kiểm ở `config.py`). Trước mốc: gimbal KHÔNG quét mà giữ hướng ngắm cuối theo hệ thế giới (tự bù khi thân drone đổi tư thế; `SearchPlanner.follow`), drone giữ hướng mũi lúc vào pha 1 (không quét yaw). Từ mốc: quét gimbal cả dải và quét yaw như cũ (`sweep`), bắt đầu liên tục từ góc hiện tại. Pha 2 (leo, nếu `climb_m` > 0) chạy độc lập với mốc quét, bắt đầu ở `climb_start_s`. S-3 (có phát hiện thì tạm ngừng quét; nay bộ quét cập nhật theo góc khớp thực trong lúc đó), đồng hồ 20 s và RTL không đổi. Không dùng hướng dự đoán `Guidance.predicted_rel` (hàm có trong mã nhưng không được gọi).
- Lý do: trước đây pha 1 quét cả dải 10–110° ngay (chu kỳ 3,33 s), nên mục tiêu bổ nhào chỉ lọt khung 0,2–0,3 s mỗi chu kỳ; ở bổ nhào 25° mất hình 8 s, bật tìm lại lấy lại hình ≈ 11,0–11,2 s, chậm hơn tắt ≈ 3 s.
- Phương án đã loại: (1) quét theo cửa sổ quanh góc khớp dự đoán: sai hệ quy chiếu và sai mốc 4 s; (2) nâng `scan_lo_deg`; (3) giữ tới khi hết bộ nhớ dự đoán 8 s: trùng đúng lúc hình trở lại.
- Đánh đổi: mục tiêu hiện lại ở chỗ khác chỉ được quét tìm từ giây 12 (còn 8 s trước RTL); hình trở lại sau giây 12 có thể trễ tới gần một chu kỳ quét (đo được 0,96 s ở ca mất hình 14 s: hình trở lại ở 14,02 s, bám lại ở 14,98 s). Hệ quả nhỏ đã biết, suy từ mã và chưa chạy thử: nếu mốc quét tới lúc đang leo mà góc đang giữ thấp hơn biên dưới dải quét pha 2 (70°) thì lệnh gimbal nhảy một lần lên biên.
- Kết quả (lô `srchH1`, 20 lần, 2026-11-20; thời gian lấy lại hình = state về TRACK lần đầu sau COAST đầu, tính từ lúc bắt đầu mất hình): bổ nhào 25°, mất hình 8 s, seed 1–5: bật 8,22 / 8,16 / 8,17 / 8,18 / 8,14 s (trung bình 8,17 s), tắt 8,16 / 8,17 / 8,17 / 8,23 / 8,17 s (trung bình 8,18 s), chênh −0,006 s (mức đặt ≤ +1,0 s). Mất hình 7 s: 7,17 / 7,22 s; 9 s: 9,19 / 9,20 s. Bay thẳng 8 s bật seed 1–3: tìm lại 3/3 sau 8,16 / 8,18 / 8,20 s. Mất hình 25 s: RTL ở 20,04 s từ đầu đợt. Mất hình 14 s: quét bắt đầu ở 12,03 s. Cấu hình `search_plane_r15_climb10`, mất hình 14 s: leo bắt đầu ở 10,6 s, tăng 5,54 m tới lúc tìm lại (14,0 s); các mốc leo tính theo đồng hồ đợt, các số khác tính từ lúc bắt đầu mất hình (lệch khoảng 0,18 s); cùng cách đo, lần trước (`srchG4`, cùng script): 10,67 s / 5,24 m / 13,97 s. Bộ test `onboard`: 1412 passed, 1 xfailed.
- Hạn chế: cả 14 lần bổ nhào (7–9 s) ngắn hơn mốc 12 s nên khối quét không chạy lần nào; kết quả chứng minh "bật không còn làm chậm", KHÔNG chứng minh việc quét có ích; tới nay chưa có ca nào bật tốt hơn tắt.
- Thay thế (hai điểm của phần trên không còn đúng): (1) S-7, câu "Blackout 8 s: pha 1 chạy ≈ 3,75 s ≈ 1,1 chu kỳ quét trước khi hình trở lại" lỗi thời: nay pha 1 không quét cho tới giây 12 của đợt, nên blackout 8 s không có chu kỳ quét nào. (2) S-9, câu "Tạm ngừng quét (S-3): supervisor không gọi `planner.step`" sai: nay supervisor gọi `SearchPlanner.follow` để bộ quét theo góc khớp thực trong lúc tạm ngừng, và `step(sweep=False)` vẫn chạy ở pha 2 (chỉ tính leo; yaw giữ `yaw0`).
