# Checkpoint: cuối phiên 4 (2026-11-18, tạm dừng theo yêu cầu người dùng)

Người dùng bảo dừng hết hoạt động để chuyển sang phiên mới với bộ máy agent tinh gọn hơn.
Giờ hạn mức đặt lại: không ghi nhận (dừng theo yêu cầu, không phải do hạn mức).
Phiên sau đọc: file này, rồi phần cuối `.office\ledger.md` (từ mục "KẾ HOẠCH ĐÃ DUYỆT" ngày 2026-11-18).
`HANDOFF.md` và `README.md` ở gốc dự án CHƯA cập nhật cho ngày 18: tin file này và sổ ghi hơn.

## Việc phải làm đầu tiên ở phiên sau
- XÓA file `onboard\simtools\out\_STOP` trước khi chạy mô phỏng (trưởng phòng tạo lúc dừng; còn nó thì `run_acceptance.sh` thoát ngay).
- Kiểm `pgrep -x arducopter` trống trong WSL `Ubuntu-24.04`.
- Kiểm `git status` trong WSL: xem mục "Chưa commit" bên dưới.

## Phương án người dùng đã chốt hôm nay
- Mục tiêu: máy bay trainer cánh trên, sải 2,16 m, thân 1,50 m, bản cánh 0,32 m, thân rộng 0,18 m, cao 0,6–0,7 m (hoặc drone). Tốc độ thật tối đa 200 km/h; phương án động cơ khác 350–400 km/h.
- Kịch bản mục tiêu: chỉ bay thẳng hoặc lao xuống. Không phanh gấp, không bay lên.
- Cách bám: drone bám ở sau và CAO HƠN mục tiêu, nhìn xuống 10–15°; camera dưới bụng. Giữ 25 m (sẽ so với 15–20 m). Ngưỡng an toàn 12,5 m không hạ.
- Thân drone bám kiểu "bullet": trục thân = trục lực đẩy; cất cánh thân dựng đứng, bay nhanh thì gần nằm ngang. Khớp gật một trục, góc giữa trục camera và trục thân từ 10° đến 90° (90° lúc cất cánh). Trong hệ trục quad của mô phỏng: trục quang = (sin δ, 0, −cos δ) hệ thân, tức camera ngước lên so với trục x thân (90° − δ).
- Trình tự: cất cánh thẳng lên → bay ổn định → tìm và khóa → ngả thân đuổi theo → leo dần lên trên mục tiêu tới góc nhìn xuống 10–15°.
- Mất dấu: quét bằng khớp, có pha leo cao rồi nhìn xuống; tìm tối đa 20 s rồi mới RTL; không có trần độ cao. Nếu số liệu cho thấy leo không hơn quét tại chỗ thì pha leo để tắt mặc định, thử lại ngoài sân.
- Bậc tốc độ: 10 và 20 m/s trước (20 m/s chỉ là số đo tham khảo); 56 m/s rồi 97–111 m/s là mục tiêu riêng, mỗi cái mở đầu bằng khảo sát.
- Giá đỡ camera in 3D: để sau, làm cùng lúc vẽ vỏ bullet ráp khung Apex, chờ người dùng báo.
- Huấn luyện lại model: dừng, chờ dữ liệu quay thật ngoài sân (cần cả nền trời và nền đất). Lab dùng model cũ `vision\weights\ft_v8n_best.pt`.
- Pi: tiếp tục dùng 192.168.1.91; IP cố định người dùng tự làm; chờ nguồn 27 W rồi đo lại 4 nhân và chạy bền.
- Cách làm việc: chạy mô phỏng và đo đạc do vai kỹ sư làm, trưởng phòng không tự chạy; thay đổi mã theo thứ tự viết test fail trước → sửa → rà.

## Kế hoạch đã duyệt và vị trí hiện tại
Giai đoạn 1 (dừng báo người dùng ở cuối):
- [xong] 1 Mốc sau sửa dẫn đường: dive15 3/3 PASS (seed 2 ra khung 1,82 s, sát ngưỡng 2,0), dive25 0/3 (mất mục tiêu, chờ khớp gật), blackout kiểu phanh gấp seed 1 FAIL 7,86 m (do mục tiêu phanh −5,9 m/s², không phải do che hình).
- [xong mã, ĐANG ĐO] 1b Hình dạng mục tiêu thật: commit `2483926`, 290 test pass, 08 duyệt. Lô đo 6 lần với `PROFILE=accept_plane_r25` bị dừng giữa chừng lúc tạm dừng: xem mục "Đang dở".
- [ĐANG DỞ] 2 Hình học khớp gật: 07 đang viết test `onboard\tests\test_gimbal_geometry.py`; chưa có mã `dtrack\gimbal.py`.
- [chưa] 3 ServoModel + SimGimbalPort · 4 GimbalController · 4b chuyển tiếp sau khi khóa (điểm giữ góc nâng đi dần tới −10…−15°) · 5 nối app + log `gimbal.csv` · 6 bộ chấm đọc góc khớp thật.
- [chưa] 7 Mô phỏng: dive15/25 × 3 seed ở 10 m/s; 20 m/s tham khảo; đối chứng khớp đứng yên (phải FAIL); độ nhạy servo chậm ×2; góc giữ −10° và −15° so với +4°; khoảng cách 25 m so với 15–20 m; báo độ ngả thân, góc khớp cần theo tốc độ và số lần chạm giới hạn 10–90°.
Giai đoạn 2 (sau khi người dùng xem kết quả giai đoạn 1): 8 nhận diện theo xác suất thật, có mất theo cụm · 9 các pha tìm lại (quét khớp, leo rồi nhìn xuống, giới hạn tốc độ bay mù) · 10 so sánh không leo / leo 10 m / 20 m · 11 README + HANDOFF.

## Đã xong hôm nay (kèm bằng chứng)
- `8b1d6f1` vision: huấn luyện lại lần 2 (ft2) đạt 1/4 tiêu chí, KHÔNG dùng; `cf4b39e` thử lọc máy bay theo quỹ đạo, kết quả âm.
- `cec7a0a` lab: công cụ ghi hình `lab\tools\record_frames.py`, 55 test (lab 153 pass). Chưa thử camera thật.
- `1c7f051` onboard: bỏ phanh tự khóa khi COAST, `descend_max_mps` 4,8, `range_back_m` (mặc định 12,5; hồ sơ 15).
- `2483926` onboard: `TargetShapeConfig`, hồ sơ `accept_plane_r25`, hướng mũi mục tiêu theo vận tốc, ca soft được chấm pha cuối. onboard 290 pass.
- `pi\` (commit `c21fdda`): số đo sơ bộ NCNN 2 nhân trên Pi 5: 640 px 11,0 khung/s; 480 px 19,7; 320 px 37,8.

## Chưa kiểm chứng / giới hạn đã biết
- Hồ sơ `accept_plane_r25` và ca blackout/disengage kiểu soft chưa có kết quả SITL trọn vẹn.
- Ước lượng khoảng cách lệch theo hướng nhìn: từ sau ~0,97, ngang ~1,38 (tưởng xa hơn thật), chéo 45° ~0,84 lần.
- Mô phỏng không có nền: không kiểm được model trên nền đất, cũng không kiểm được lợi ích của leo cao.
- Mục tiêu trong mô phỏng là quad 0,8 kg thứ hai, không phải máy cánh cố định; trần lệnh bám 30 m/s; mọi lần 20 m/s cũ đều FAIL.
- Thông số servo MG90S trong thiết kế là giả định. Quan hệ ngả thân–tốc độ của quad mô phỏng khác vỏ bullet thật.
- Nhỏ, đã ghi sổ: bbox nhảy khi mục tiêu chậm qua 1 m/s; `disengage:soft` chưa được chấm pha cuối; `both_stopped` chỉ chấm ở ca cắm; `session.json` của công cụ ghi hình có thể cụt khi đĩa đầy.
- Panel `mcp__office-panel__plan` trả lỗi định dạng mỗi lần gọi: chưa hiển thị được kế hoạch.

## Đang dở lúc dừng (cập nhật ở cuối file khi các vai báo về)
- 07 test-engineer (đo mốc hồ sơ máy bay): ma trận `1:none:dive15 2:none:dive15 3:none:dive15 1:none:dive25 1:blackout:soft 1:disengage:soft`, tóm tắt ở `onboard\simtools\out\_acceptance_20261118_090641.txt`. Đã bảo dừng sau lần chạy đang dở.
- 07 test-engineer (test hình học khớp): đã bảo dừng ở điểm an toàn và báo trạng thái.

## Trạng thái cuối cùng lúc dừng (cả hai vai đã báo về; không còn agent hay mô phỏng nào chạy)
- Lô hồ sơ máy bay: xong 1/6. `out\20261118_090641_10ms_s1_none` (dive15 seed 1) PASS: pha cắm d3 25,1–29,4 m, ra khung 1,72 s (mốc cũ 1,22 s); sai số giữ 25 m TB 0,81 m; sai số ước lượng khoảng cách TB −0,75 m, RMS 0,77 m (mốc cũ TB 0,05, RMS 0,38: lệch hơn rõ, mới một mẫu, cần xem lại); kích thước mục tiêu trung vị 145,7 px; TRACK 100%. `app_cfg.json` đúng hồ sơ. `pgrep` trống.
- CHƯA chạy 5 lần: `MATRIX='2:none:dive15 3:none:dive15 1:none:dive25 1:blackout:soft 1:disengage:soft'` với `PROFILE=accept_plane_r25`. Chưa biết ca soft có được chấm pha cuối không.
- Test hình học khớp: 38 ca đã viết, fail đúng lý do (chưa có `dtrack\gimbal.py`), chưa được 08 rà. File đã đổi tên thành `onboard\tests\test_gimbal_geometry.py.wip` để bộ test dự án vẫn xanh (290 pass); đổi lại tên khi bắt đầu bước 2. Quy ước dự án: quaternion (w,x,y,z) thân FRD → NED (`dtrack\geometry.py:3-6`), pitch Euler dương = mũi lên nên "chúi θ" = pitch −θ; mã không nên dùng `euler_from_quat` để suy pitch vì suy biến ở 90°.

## Bước tiếp theo
1. Xóa `_STOP`; chạy nốt 5 lần còn thiếu của lô hồ sơ máy bay (07 chạy, 08 đối chiếu).
2. Hoàn tất test hình học khớp (bước 2) rồi viết mã, rà.
3. Đi tiếp bước 3 → 7, dừng báo người dùng ở cuối giai đoạn 1.
4. Cập nhật `HANDOFF.md`, `README.md` cho các quyết định ngày 18.
