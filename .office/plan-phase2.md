# Kế hoạch giai đoạn 2 (bản trình duyệt, 2026-11-19) — CHƯA DUYỆT

Lập: 02 planner (nháp ở `plan-phase2-draft.md`). Phản biện: 08 checker, kết luận NÊN SỬA TRƯỚC KHI TRÌNH (3 Nghiêm trọng, 10 Quan trọng). Trưởng phòng sửa theo, ghi ở mục "Đã sửa theo phản biện".

## Mục tiêu
Trong mô phỏng: drone không tự leo khi mất hình tạm thời, không bị phát hiện giả kéo lệch, và khi mất mục tiêu thì chủ động tìm lại trong tối đa 20 s rồi mới RTL. Kết quả chỉ chứng minh logic và an toàn trong mô phỏng, không chứng minh hiệu quả tìm lại ngoài thực tế (mô phỏng không có nền, xác suất phát hiện là số giả định).

## Tiêu chí nghiệm thu
| # | Tiêu chí | Cách kiểm |
|---|---|---|
| C1 | Leo khi COAST: tích phân lệnh lên ≤ 1,0 m mỗi lần COAST khi giữ khoảng cách bình thường; nếu lúc mất hình đang có lệnh lên sẵn v0 thì ≤ 1,0 m + v0²/(2·a_max_z) (quãng hãm, không nhảy bậc lệnh; người dùng duyệt đổi 2026-11-19). Lệnh leo tránh đất được ưu tiên. (Hiện 4,0–9,5 m) | Test LOS chéo xuống đỏ → xanh; chạy lại `dtrack` trên 3 log cũ; blackout:soft |
| C2 | Một phát hiện giả khi COAST không kéo khớp nhảy quá ngưỡng (10 chốt con số ở bước 2, trước khi chạy SITL) | Test dựng lại ca 134109; `gimbal.csv` |
| C3 | Pytest `onboard` ≥ 810 passed, 0 failed | Cùng lệnh trước và sau |
| C4 | Bám không hỏng sau khi sửa: ô đối chứng (Wide, nguồn phát hiện cũ) dive15 + dive25 đạt đủ tiêu chí giai đoạn 1 (ra khung ≤ 2,0 s, d3 min ≥ 6 m). FAIL thì dừng báo. Các ô nguồn theo cụm báo riêng theo tham số, không dùng làm cổng | `_summary_*.txt`, `report_run` |
| C5 | Tìm lại, ô không leo, 5 seed mỗi kịch bản: báo số lần bắt lại trước RTL và thời gian bắt lại theo từng kịch bản. Mức đạt: ≥ 4/5 ở kịch bản mục tiêu bay thẳng; không tuyên bố thống kê | Bộ đo mới (bước 13, 16) |
| C6 | Khi bay mù (người dùng đổi lần 2, 2026-11-19, sau bảng đo đánh đổi): mục tiêu bay đều → d3 min ≥ 8 m; mục tiêu hãm lúc drone mất hình (1,5; 3; 8 m/s²) → CHỈ ĐO và ghi số, không tính đạt/không đạt; không có khoảng cách hợp lệ thì không bay mù. Cơ chế "giả định mục tiêu hãm" TẮT trong hồ sơ tìm lại (`blind_floor_m` 0). Rủi ro đã chấp nhận: mục tiêu giảm tốc đúng lúc drone mù thì drone có thể áp sát ~1 m (số mô hình); mục tiêu quay đầu lao lại | Test đơn vị + log |
| C7 | RTL ở 20 ± 0,5 s tính từ lần COAST đầu của đợt mất, không bị một phát hiện giả đặt lại; có ca không tìm lại được | Test supervisor + log |
| C8 | Pha leo (tắt mặc định): độ cao tăng ≤ mức đặt + 1 m, d3 min ≥ 8 m | Leo 10 m × 3 seed, 20 m × 1 seed |
| C9 | Bám vẫn đạt sau khi thêm mã tìm lại: 3 ô bám Wide chạy lại ở bước 18 | Bộ chấm |
| C10 | `git grep` tên đăng nhập và IP nội bộ trong `pi/`, `lab/` ra 0 dòng; script vẫn chạy khô được | `git grep`, `bash -n`, chạy với lệnh `echo`; chạy thật khi Pi có nguồn |

## Các bước
Quy tắc: mã nào cũng 07 viết test fail trước → 05 sửa → 08 rà. Không sửa mã khi SITL đang chạy; một bước SITL tại một thời điểm; mỗi đợt chỉ một bước chạm `config.py`.

| Bước | Làm gì | Vai | Chạm | Kiểm chứng | Đợt |
|---|---|---|---|---|---|
| 1 | Thiết kế chi tiết khối tìm lại: các pha, giao diện supervisor–guidance–gimbal, khóa cấu hình, đồng hồ 20 s tuyệt đối, kịch bản mất hình (mục tiêu bay thẳng / cắm / không trở lại), bộ đo | 02 planner | chỉ đọc; ra `.office\design-search.md` do trưởng phòng lưu | 08 rà ở bước 9 | 1 |
| 2 | Điều tra vì sao phát hiện giả lọt tracker; ca 134109 lệch 0,8 m/s; vì sao bbox chạm mép sinh los_rate giả; chốt ngưỡng C2 | 10 investigator | chỉ đọc log và mã | Chạy lại `tracker` trên đầu vào trong log | 1 |
| 3 | Test đỏ: không leo khi COAST với LOS chéo xuống | 07 test-engineer | `tests\test_guidance_coast_vertical.py` (mới) | Đỏ đúng lý do | 1 |
| 4 | Test đỏ: nguồn phát hiện theo xác suất, mất theo cụm | 07 | `tests\test_synthetic_realdet.py` (mới) | Đỏ đúng lý do | 1 |
| 5 | Dọn tên đăng nhập + IP: script đọc từ `pi\pi.env` (không lên git) kèm `pi.env.example`; file `.cmd` đọc biến môi trường | 05 software-engineer | `pi\README.md`, 8 script `pi\scripts\*.sh`, `lab\Mo-man-hinh-pi.cmd`, `lab\README.md:20`, `.gitignore` | C10 | 1 |
| 6 | Sửa leo cao: kẹp z của hold, tắt `vc` khi COAST, chiếu ngang phần lùi | 05 | `dtrack\guidance.py` | Test bước 3 xanh; C3 | 2 |
| 7 | Mã nguồn phát hiện theo cụm + hồ sơ `realdet` (camera Wide ghi tường minh, tham số là giả định, có quét độ dài cụm) | 05 | `dtrack\synthetic.py`, `dtrack\config.py` | Test bước 4 xanh | 2 |
| 8 | Test đỏ cho phát hiện giả, theo kết quả bước 2 | 07 | `tests\test_tracker_coast_false.py` (mới) | Đỏ đúng lý do | 2 |
| 9 | Rà bước 5: 09 soát lộ thông tin; 07 chạy khô script | 09 security-auditor, 07 | chỉ đọc | Báo cáo; `bash -n` | 2 |
| 10 | Sửa phát hiện giả | 05 | `dtrack\tracker.py` | Test bước 8 xanh | 3 |
| 11 | Rà bước 6, 7 và thiết kế bước 1 | 08 checker | chỉ đọc | Tự chạy pytest | 3 |
| 12 | Rà bước 10 | 08 | chỉ đọc | Tự chạy pytest | 4 |
| 13 | Test đỏ: bộ đo tìm lại (thời điểm bắt lại, thời điểm RTL, d3 lúc mù) và khối tìm lại (pha, đồng hồ tuyệt đối, khớp quét, mục tiêu tiến gần lúc mù) | 07 | `tests\test_search*.py`, `tests\test_analyze_reacq.py` (mới) | Đỏ đúng lý do | 4 |
| 14 | SITL hồi quy, khoảng 11 lần, camera Wide: đối chứng nguồn cũ dive15 + dive25; nguồn theo cụm dive15/dive25 × 3 seed; blackout:soft; nhiễu pixel ×2; kèm số sai số khoảng cách Wide | 07 | `simtools\out\` | C1, C2, C4 | 5 |
| 15 | Đối chiếu bước 14 với đợt D, F; tự tính lại từ csv. CỔNG: C4 FAIL thì dừng báo | 08 | chỉ đọc | Bảng số | 5 |
| 16 | Mã tìm lại + bộ đo + cửa sổ chạy đủ dài cho ca 20 s | 05 | `dtrack\search.py` (mới), `supervisor.py`, `gimbal_control.py`, `guidance.py`, `config.py`, `simtools\analyze_closed_loop.py`, `simtools\sim_helper.py` | Test bước 13 xanh; C3 | 6 |
| 17 | Rà mã tìm lại | 08 | chỉ đọc | Tự chạy pytest | 7 |
| 18 | SITL tìm lại, khoảng 17 lần: không leo × 5 seed × 2 kịch bản; leo 10 m × 3; leo 20 m × 1; ca không trở lại (RTL ở 20 s); ca không có khoảng cách hợp lệ; 3 ô bám chạy lại; hình tĩnh bằng `report_run` | 07 | `simtools\out\` | C5–C9 | 8 |
| 19 | Đối chiếu bước 18 với từng tiêu chí, xếp mức vấn đề | 08 | chỉ đọc | Tính lại từ csv | 9 |
| 20 | Cập nhật README, HANDOFF | 05 | `README.md`, `HANDOFF.md` | Bước 21 | 9 |
| 21 | Rà tài liệu, đối chiếu toàn bộ bằng chứng với C1–C10 | 08 | chỉ đọc | Báo cáo cuối | 10 |

Ước lượng: 24 lượt chính + 8–12 lượt vòng sửa = 32–36 lượt gọi vai; khoảng 28 lần chạy SITL (mỗi lần ~4 phút). Vượt 1,5 lần thì dừng báo.

## Tồn đọng: đề xuất xử lý
| Việc | Đề xuất |
|---|---|
| Leo cao khi COAST | Trong giai đoạn 2: bước 3, 6, 11 |
| Phát hiện giả lọt tracker | Trong giai đoạn 2: bước 2, 8, 10, 12 |
| B1 (nhận diện) | Hoãn tới khi tải xong phần D, D', E, E' của MMFW-UAV. Khi có: 02 viết lại kế hoạch B1 (tách drone / máy bay, vùng cắt, cổng quyết định trước khi huấn luyện), trình riêng. Không làm gì cho B1 trong giai đoạn 2 |
| Đổi mặc định camera sang Wide trong `config.py` | Hoãn tới khi hiệu chuẩn fx thật trên Pi, đổi một lần bằng số thật. Lý do: 08 phát hiện bộ chấm và `report_run` rơi về số camera cũ khi cấu hình không ghi camera, đổi mặc định bây giờ làm bộ chấm sai mà vẫn in PASS/FAIL. Giai đoạn 2 ghi camera Wide tường minh trong hồ sơ như đợt F. Khi làm: sửa bộ chấm đọc camera hiệu lực trước |
| Việc trên Pi | Chờ nguồn. Khi về: 06 đọc `labview.log`, chạy labview 2 luồng, đo 60 s, kiểm đường hầm và cổng 8080; 07 kiểm; chạy thật các script đã dọn ở bước 5; hiệu chuẩn fx |
| Sai số khoảng cách Wide không tăng như dự đoán | Lấy số ở bước 14 (có ô nhiễu ×2); không điều tra riêng |
| Lần 134109 lệch 0,8 m/s | Bước 2 |
| d3 44,7–51,6 m ở pha tăng tốc | Đóng: chỉ có ở hồ sơ 25 m, mặc định nay 15 m (tối đa 33,5 m) |
| Giữ 12 m sát ngưỡng | Đóng: không dùng 12 m |
| Mỗi ô 1 seed | Bước 14 và 18 chạy 3–5 seed |
| Nhiễu pixel thật của Wide | Chờ Pi; tạm thời có ô nhiễu ×2 |
| Che khuất ở δ 110° | Chờ lắp vật thật |
| Tên đăng nhập, IP | File: bước 5, 9. Lịch sử git và sổ ghi: xem câu hỏi 1 |
| Panel "Văn phòng" lỗi | Đề xuất đã nằm ở `~\.claude\office\proposals\`, chờ người dùng duyệt |
| Mục Nhỏ của `report_run.py` | Hoãn, không ảnh hưởng số đo |
| Video báo cáo | Hoãn theo quyết định của người dùng |
| Mật khẩu Pi | Đóng: không đổi |

## Rủi ro, việc khó hoàn tác, phần không đụng
- Sửa leo cao có thể làm lệch hành vi bám: bước 15 là cổng dừng.
- Nguyên nhân phát hiện giả có thể không gọn trong một chỗ sửa: bước 2 báo trước khi viết test.
- Xác suất phát hiện là số tự đặt; kết quả tìm lại báo theo tham số.
- Lợi ích của pha leo không đo được trong mô phỏng: chỉ kiểm an toàn, để tắt mặc định.
- Việc khó hoàn tác: không có trong 21 bước. Viết lại lịch sử git + đẩy đè KHÔNG nằm trong kế hoạch, chỉ làm nếu người dùng yêu cầu riêng.
- Không đụng: FC và phần cứng bay, huấn luyện model, `vision\`, `cad\`, thiết bị Pi (chỉ sửa script trong `pi\`), mặc định camera, video.

## Đã sửa theo phản biện của 08
- Bỏ khỏi giai đoạn 2: chuẩn bị B1, sửa `report_run.py`, đổi mặc định camera, điều tra riêng sai số khoảng cách.
- Thêm bộ đo "bắt lại trước RTL" (trước đó không có cách đo C5, C7) và kịch bản mất hình; `sim_helper` hiện cắt lần chạy trước 20 s.
- Đồng hồ 20 s tuyệt đối từ lần COAST đầu (hiện `supervisor.py:136-140` đặt lại mỗi lần TRACK).
- C1 nới từ 0,5 lên 1,0 m (phần dư đo được 0,47 m); bỏ ngưỡng ±0,3 m; C4 có ô đối chứng nguồn cũ; C5 bỏ tuyên bố thống kê; thêm ô bám sau khi thêm mã tìm lại; test mục tiêu tiến gần lúc mù.
- Tách rà và sửa thành bước riêng; bước dọn thêm chạy khô script và `lab\README.md:20`.
- Không áp dụng: worktree riêng để viết mã song song với SITL (02 đề xuất, 08 không khuyên).

## Câu hỏi cho người dùng
1. Repo GitHub đang private hay public? Tên đăng nhập Pi trùng tên tài khoản GitHub nên vốn đã nằm trong địa chỉ repo và tác giả commit; thứ thật sự riêng tư chỉ là IP nội bộ (không truy cập được từ ngoài). Khuyến nghị: dọn file, KHÔNG viết lại lịch sử, giữ nguyên sổ ghi.
2. Sàn khoảng cách khi bay mù 8 m (thay 12,5 m của hồ sơ 25 m cũ)?
