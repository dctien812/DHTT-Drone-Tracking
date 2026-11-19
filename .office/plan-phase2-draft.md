# NHÁP kế hoạch giai đoạn 2 (02 planner, 2026-11-19) — chưa duyệt

02 đã mở: `guidance.py:100-349`, `tracker.py:225-320`, `supervisor.py:120-189`, `gimbal_control.py:40-82`, `config.py:64-133`, `synthetic.py:15-55`, `test_guidance.py:320-360`, checkpoint, sổ ghi 251-266 và 404-528, HANDOFF mục 5-6.
02 CHƯA mở: `app.py`, `onboard\simtools\*` (kể cả cách tạo blackout), `design-gimbal-steps-3-6.md`, `report_run.py`.

## 1. Thiết kế: đổi so với 11-18
- Bỏ "khớp quét ±50°": khớp nay 10-110°, quét tới 150°/s.
- Hiện giám sát chỉ bay mù trong `coast_follow_s` = 4 s (`supervisor.py:144,151-155`), sau đó LOST phanh về 0 (`:173-177`), RTL ở `lost_rtl_s` = 10 s (`config.py:69`, `supervisor.py:182-185`). Đổi sang tổng 20 s: `lost_rtl_s` = 16 s nếu tính từ lúc mất hình (giả định G1).
- Khối mới `onboard\dtrack\search.py`: pha 0 COAST bay mù có giới hạn tốc độ; pha 1 treo, khớp quét 10→110°, yaw quét; pha 2 (tùy chọn) leo `search_climb_m` rồi nhìn xuống quét.
- Mặc định `search_climb_m` = 0 (pha leo tắt): mô phỏng không có nền nên không đo được lợi ích của leo, chỉ kiểm an toàn.
- "Không có trần độ cao" và lỗi tự leo: sau khi sửa (a) không còn leo ngoài ý; độ cao chỉ tăng ở pha 2, tối đa `search_climb_m` tính từ độ cao lúc mất.
- Mô phỏng thêm nguồn phát hiện theo xác suất thật (theo cỡ pixel, mất theo cụm). Hiện `p_miss` độc lập từng khung (`synthetic.py:27`).
- Sàn bay mù 8 m (`range_min_m` = lùi khẩn của hồ sơ 15 m; sàn cũ 12,5 m viết cho hồ sơ 25 m). Sàn chấm 6 m giữ cho pha bám. Ghi thêm số lần d3 < 10 m.
- Thứ tự: (a) trước tìm lại; (b) cần 10 điều tra nguyên nhân gốc trước (lớp kiểm bắt lại chỉ xét góc và thời gian, `tracker.py:265-270`); (a) và (b) khác file nên song song; xây nguồn theo cụm trước khi chạy mô phỏng hồi quy.

## 2. Mục tiêu và tiêu chí
Mục tiêu: trong mô phỏng, drone không tự leo khi COAST, không bị phát hiện giả kéo lệch, và tìm lại mục tiêu trong tối đa 20 s.

| # | Tiêu chí | Cách kiểm |
|---|---|---|
| C1 | Leo khi COAST: tích phân lệnh lên ≤ 0,5 m mỗi lần COAST (hiện −9,54 / −4,18 / −4,01 m) | Test LOS chéo xuống đỏ → xanh; chạy lại `dtrack` trên log; blackout:soft |
| C2 | Một phát hiện giả khi COAST không làm elev_los lệch, khớp không nhảy quá ngưỡng (chốt ở bước 2) | Test dựng lại ca 134109; gimbal.csv |
| C3 | Pytest `onboard` không giảm so với 810 passed | Cùng lệnh trước và sau |
| C4 | Đo lại mốc bám với Wide + nguồn theo cụm: ra khung ≤ 2,0 s, d3 min ≥ 6 m, không ô nào xấu hơn đợt F; ô đợt F PASS mà nay FAIL thì dừng báo | `_summary_*.txt` + `report_run` |
| C5 | Tìm lại: bắt lại trước RTL ≥ 80% lần chạy (≥ 5 seed mỗi ô, tức 4/5) | Bộ chấm + log supervisor |
| C6 | Bay mù: d3 min ≥ 8 m mọi lần; không có khoảng cách hợp lệ thì không bay mù | Test đơn vị mở rộng `test_guidance.py:352-354`; log |
| C7 | RTL đúng 20 ± 0,5 s sau mất hình; có ca không tìm lại được | Log supervisor |
| C8 | Leo: độ cao tăng ≤ `search_climb_m` + 1 m, d3 không giảm | Leo 10 m × 3 seed, 20 m × 1 seed |
| C9 | Mặc định camera Wide (fx 933, 2304×1296), cấu hình đợt F cho kết quả tương đương | Test mặc định; chạy lại 1 ô đợt F, d3 min 11,27 ± 0,3 m |
| C10 | Hết tên đăng nhập và IP khỏi file đang theo dõi, trừ sổ ghi | `git grep` 0 dòng; 09 xác nhận |

## 3. Các bước
Quy tắc: không sửa mã khi SITL đang chạy; một bước dùng SITL tại một thời điểm; `config.py` chỉ một bước chạm mỗi đợt.

| ID | Làm gì | Vai | Chạm | Kiểm chứng | Đợt |
|---|---|---|---|---|---|
| 1 | Thiết kế chi tiết khối tìm lại (pha, giao diện supervisor-guidance-gimbal, tên khóa config) | 02 | chỉ đọc | 08 đọc ở bước 13 | 1 |
| 2 | Điều tra (b): vì sao phát hiện giả lọt; ca 134109 lệch 0,8 m/s; vì sao bbox chạm mép sinh los_rate giả; chốt ngưỡng C2 | 10 | chỉ đọc log | Chạy lại `tracker` trên đầu vào log | 1 |
| 3 | Test đỏ cho (a) | 07 | `tests\test_guidance_coast_vertical.py` (mới) | Đỏ đúng lý do | 1 |
| 4 | Chuẩn bị B1: chấm model cũ và yolov8n COCO trên Det-Fly ở vùng cắt 480; chỉ báo số, không huấn luyện | 07 | `vision\results\b1_prep\` (mới) | Bảng recall / báo động giả theo cỡ px | 1 |
| 5 | Dọn tên đăng nhập và IP: đọc từ biến môi trường hoặc `pi\pi.env` (vào .gitignore) kèm `pi.env.example` | 05 | `pi\README.md:3`, 9 script `pi\scripts\*.sh`, `lab\Mo-man-hinh-pi.cmd:9`, `.gitignore` | `git grep` = 0 | 1 |
| 6 | Test đỏ cho nguồn phát hiện theo xác suất và cụm | 07 | `tests\test_synthetic_realdet.py` (mới) | Đỏ đúng lý do | 1 |
| 7 | Phân tích log cũ: sai số khoảng cách Wide không tăng ~1,86 lần | 10 | chỉ đọc | Số so cùng cửa sổ chấm | 1 |
| 8 | Sửa (a): kẹp z của hold, tắt `vc` khi COAST (`guidance.py:186-188`), chiếu ngang phần lùi (`:144,147-150`) | 05 | `guidance.py` | Test bước 3 xanh; pytest ≥ 810 | 2 |
| 9 | Test đỏ cho (b) theo kết quả bước 2 | 07 | `tests\test_tracker_coast_false.py` (mới) | Đỏ đúng lý do | 2 |
| 10 | Mã nguồn phát hiện theo cụm và hồ sơ `realdet` | 05 | `synthetic.py`, `config.py` (PROFILES) | Test bước 6 xanh | 2 |
| 11 | Rà bảo mật việc dọn ở bước 5 | 09 | chỉ đọc | Báo cáo | 2 |
| 12 | Sửa (b) | 05 | `tracker.py` | Test bước 9 xanh | 3 |
| 13 | Rà (a) và nguồn theo cụm, kèm thiết kế bước 1 | 08 | chỉ đọc | Tự chạy pytest | 3 |
| 14 | Test đỏ: đổi mặc định camera sang Wide | 07 | `tests\test_camera_default_wide.py` (mới) | Đỏ | 3 |
| 15 | Mức Nhỏ của `report_run.py` (giới hạn suy từ sat; hàng lỗi dựng hình có huy hiệu): 07 test trước, 05 sửa ở đợt 4 | 07 | `tests\test_report_run.py` | Đỏ | 3 |
| 16 | 08 rà (b); 05 đổi mặc định camera và sửa `report_run.py` | 08, 05 | `tracker.py`, `config.py:99-102`, `report_run.py` | Test xanh, 08 DUYỆT | 4 |
| 17 | Test đỏ cho tìm lại (search, supervisor, gimbal) | 07 | `tests\test_search*.py` | Đỏ | 4 |
| 18 | SITL hồi quy (~12 lần): Wide + `realdet`, dive15/dive25 × 3 seed, blackout:soft, nhiễu pixel ×2, 1 ô đợt F cũ | 07 | `simtools\out\` | C1, C2, C4, C9 | 5 |
| 19 | Đối chiếu bước 18 với đợt D/F; C4 xấu đi thì dừng báo | 08 | chỉ đọc | Tự tính lại từ csv | 5 |
| 20 | Mã tìm lại: `search.py` (mới) + `supervisor.py`, `gimbal_control.py`, `guidance.py`, `config.py`; thêm blackout cứng nếu cần | 05 | các file trên | Test bước 17 xanh | 6 |
| 21 | Rà mã tìm lại | 08 | chỉ đọc | Chạy pytest | 7 |
| 22 | SITL tìm lại (~12 lần): không leo × 5 seed; leo 10 m × 3; leo 20 m × 1; ca không tìm lại được; ca không có khoảng cách hợp lệ | 07 | `out\` | C5-C8 | 8 |
| 23 | Đối chiếu bước 22, xếp mức vấn đề | 08 | chỉ đọc | Tính lại từ csv | 9 |
| 24 | Cập nhật README, HANDOFF | 05 | `HANDOFF.md`, `README.md` | 08 rà ở bước 25 | 9 |
| 25 | Rà tài liệu | 08 | chỉ đọc | Đối chiếu số với bước 22 | 9 |

## 4. Tồn đọng
| Mục | Đề xuất |
|---|---|
| (a) leo cao khi COAST | Trong giai đoạn 2: bước 3, 8, 13. Kiểm bằng C1 |
| (b) phát hiện giả lọt tracker | Trong giai đoạn 2: bước 2, 9, 12, 16. Kiểm bằng C2 |
| (c) B1 | Hoãn tới khi có ảnh máy bay. Làm trước: bước 4. Có dữ liệu thì 02 viết lại kế hoạch, không lặp công thức V2 |
| (d) camera Wide | Đổi mặc định: bước 14, 16. Hiệu chuẩn fx trên Pi: hoãn tới khi nguồn về |
| (e) Pi | Hoãn tới khi có nguồn; 06 làm, 07 kiểm; ngoài giai đoạn 2 |
| (f) chưa kiểm chứng | Khoảng cách Wide: bước 7. Lệch 0,8 m/s: bước 2. d3 44,7-51,6 m: đóng (hồ sơ 15 m tối đa 33,5 m). Giữ 12 m: bỏ. 1 seed mỗi ô: bước 18 phủ 3 seed. Nhiễu pixel Wide: bước 18 độ nhạy ×2, số thật chờ Pi. Che khuất δ 110°: hoãn tới khi đo vật thật |
| (g) tên đăng nhập, IP | Bước 5, 11. Sổ ghi: trưởng phòng dọn nếu người dùng cho ngoại lệ. Viết lại lịch sử + force push: người dùng quyết; lệnh đề xuất `git filter-repo --replace-text` (chưa kiểm đã cài chưa) |
| (h) panel | Chỉ nhắc, đề xuất đã có ở `proposals\` |
| (i) mục Nhỏ `report_run.py` | Hai mục ở bước 15; còn lại hoãn |

## 5. Rủi ro, hoàn tác, phạm vi
- Rủi ro: sửa (a) làm lệch hành vi bám (bước 19 chặn); nguyên nhân (b) có thể phức tạp hơn một chỗ sửa; mô phỏng không đo được lợi ích của leo; đổi camera mặc định có thể vỡ nhiều test; bước 4 chiếm CPU nên chỉ chạy ở đợt 1-3.
- Khó hoàn tác: chỉ có viết lại lịch sử git + force push.
- Không đụng: FC và phần cứng bay thật, huấn luyện model, video, Pi, `cad\`, mật khẩu Pi.
- Ước lượng: 35-40 lượt gọi vai (27 chính + 8-12 vòng sửa); ~24 lần chạy SITL, mỗi lần ~4 phút.
- Giả định: G1 20 s tính từ COAST đầu tiên; G2 sàn bay mù 8 m; G3 leo mặc định tắt.

## 6. Câu hỏi cho người dùng
1. Repo GitHub private hay public? (quyết có viết lại lịch sử không)
2. Sàn bay mù 8 m thay 12,5 m cũ?
3. Khi nào có dữ liệu máy bay để mở lại B1?
4. Đổi mặc định camera sang Wide ngay trong mã, hay chờ hiệu chuẩn trên Pi?

## Đề xuất của 02
- Sổ ghi chỉ ghi thêm, dọn dòng 79/149/151/187 cần người dùng cho ngoại lệ.
- Worktree riêng để 05 viết mã tìm lại trong lúc 07 chạy SITL bước 18.
- Chốt ngưỡng C2 trước khi chạy SITL.
