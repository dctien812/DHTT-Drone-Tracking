# Checkpoint: cuối phiên 6 — giai đoạn 2 và việc B1a đã xong phần làm (2026-11-19, khoảng 20:00)

Tên dự án: Drone Tracking. Phiên sau đọc: file này, rồi cuối `.office\ledger.md` (mục "Phiên 6"). Kế hoạch đã chạy hết: `.office\plan-phase2.md` (21 bước) và `.office\plan-b1a.md` (15 bước, một vòng huấn luyện). Người dùng nghỉ tới đầu tuần; hạn mức tuần của Fable đặt lại trưa Chủ nhật, có thể trưởng phòng chạy bằng Opus 5.5.

## Lưu ý vận hành
- Đồng hồ WSL chậm 7 giờ so với giờ máy. Git chỉ chạy qua Git Bash. pytest chạy trong WSL: `~/venv-ardupilot/bin/python` cho `onboard`, `~/venv-vision/bin/python` cho `vision\tests_b1`.
- Mỗi lúc chỉ một SITL; khi SITL chạy không làm việc nặng ổ D, không huấn luyện, không chơi game trên máy (card dùng chung làm chậm và làm hỏng số đo).
- Bước bị bộ lọc an toàn dừng: báo người dùng trong chat kèm prompt để họ tự chạy ở phiên khác; không đưa vào báo cáo, không viết lại để né, không tự làm thay.
- Repo GitHub công khai. Không đưa lên: ảnh, video của người dùng (`.office/images/`) và mọi thứ sinh ra từ đó (`vision/results/b1a/realvideo1/`), `pi/pi.env`, `vision/data/`, `vision/.venv-gpu/`, `onboard/simtools/out/`, ảnh chụp thử camera (`pi/camtest_*`). `.gitignore` đã có đủ; trước mỗi lần đẩy chạy `git add -A -n` và tìm tên đăng nhập, IP, đường dẫn hồ sơ Windows. Lịch sử cũ còn IP và ảnh camera thử: người dùng quyết không viết lại lịch sử.

## Giai đoạn 2 (tìm lại mục tiêu sau khi mất hình): xong 21 bước
- Mã: `onboard\dtrack\search.py` và các phần nối; mặc định TẮT, bật qua hồ sơ `search_plane_r15`. Cơ chế "giả định mục tiêu hãm" tắt trong hồ sơ theo quyết định của người dùng.
- Test `onboard`: `1368 passed, 1 xfailed` (08 chạy 2026-11-19).
- SITL: lô `srchG3` (26 lần) và lô bù `srchG4` (8 lần). Bảng: `onboard\simtools\out\_report_srchG3\srchG3_table.md`, `out\_acceptance_srchG4_20261119_121709.txt`.
- Tiêu chí: C1 đạt · C2 chưa đủ bằng chứng · C3 đạt · C4 đạt · C5 đạt (5/5 seed, nhưng chưa chứng minh việc quét tự tìm ra mục tiêu) · C6 đạt trong cửa sổ mất hình (≥ 15,1 m) · C7 đạt (RTL 20,00–20,03 s) · C8 mới 1 lần leo thật (5,20 m tới lúc tìm lại; sau khi đóng đợt độ cao còn tăng tới +9,15 m, chưa điều tra), chưa đủ số ca · C9 đạt (3 seed mỗi ô) · C10 đạt phần chạy khô, chờ Pi.
- Rủi ro đã biết, CHƯA SỬA (ghi đủ trong `README.md` mục "Rủi ro đã biết"):
  1. Cuối bài khi mục tiêu dừng, drone mất hình lần hai và áp sát 3,9–7,9 m ở 8/13 lần bay thẳng có mục tiêu dừng cuối bài, kể cả khi tắt tìm lại; drone luôn ở trên mục tiêu 3,2–4,2 m, 3 lần gần như ngay trên đầu.
  2. Ca bổ nhào: bật tìm lại lấy lại hình chậm hơn tắt ~3 s. Nguyên nhân gốc đã rõ (10 điều tra): gimbal quét cả dải 10–110° nên chỉ lướt qua vùng có mục tiêu 0,2–0,3 s mỗi vòng 3,33 s. Hướng sửa: quét quanh góc dự đoán ±25° hoặc nâng `scan_lo_deg`; viết test trước (gợi ý trong sổ ghi), rồi chạy lại SITL bổ nhào.
  3. Mục tiêu hãm lúc mất hình (chỉ đo): gần nhất 3,2–4,2 m.
- Việc đầu tuần cho giai đoạn 2: sửa (2) rồi (1) theo vòng 07 viết test → 05 sửa → 08 rà → SITL; chạy thêm ca leo (mất hình 14 s, seed 2–3, và hồ sơ leo 20 m) cho C8; phép đo chứng minh tìm lại có ích (mục tiêu hiện lại ở chỗ khác với dự đoán).

## Việc B1a (nhận diện máy bay): xong 15 bước, một vòng huấn luyện
- Báo cáo đã rà: `vision\results\b1a\B1A_REPORT.md`.
- Huấn luyện trên card RX 9060 XT, 60 epoch mỗi lượt: EE 29,6 phút; DD 73,3 phút; final 64,4 phút (DD và final bị chậm do game dùng chung card); tổng 2 giờ 47 phút. Trọng số ở `vision\results\b1a\train\runs\b1a_{EE,DD,final}_s0\weights\best.pt` (không lên GitHub).
- Kết quả chính: model EE (học máy bay tối, kiểm máy bay trắng) kém model gốc ở góc nhìn từ trên xuống (0,129 so với 0,402) và không đạt A1, A3; model DD (học trắng, kiểm tối) hơn model gốc về phát hiện nhưng báo giả 1,80/100 ở ngưỡng tự chọn. Trên video thật 1 của người dùng: model final 561/569 so với model gốc 479/569 ở đoạn bay liên tục, nhưng 69 phát hiện giả so với 4 trên 269 khung (441 nếu phóng khung lên 2304 px).
- Kết luận: model mặc định vẫn là model gốc (yolov8n COCO, lớp airplane) ngưỡng 0,12. Model final là ứng viên vòng sau.
- Việc vòng sau (chờ người dùng gửi video quay ở sân bay): thêm mẫu nền khó (bê tông có vệt, mái nhà, cờ, cây) rồi huấn luyện và chấm lại; đặt quy tắc ngưỡng trước khi chấm, val tách theo đoạn riêng; đo model final qua bộ bám trên video thật; thử nhận thêm lớp "kite" của model gốc (~80% lần trượt là bị gọi thành lớp này); chấm chéo cùng trọng số card/CPU; xuất NCNN cho Pi.
- Môi trường card: `vision\.venv-gpu`; bắt buộc `torch.backends.cudnn.enabled = False`, `device=0`, script Windows có `if __name__ == "__main__"`.

## Trạng thái mã và git
- Xem dòng cuối sổ ghi để biết commit và push của phiên 6 đã làm chưa (người dùng đã duyệt commit và push sau bài tổng kết).

## Chờ người dùng
- Chấp nhận kết quả giai đoạn 2 và B1a (trình trong bài tổng kết tối 2026-11-19).
- Video và ảnh máy bay thật ở sân bay (để vào `.office\images\`).
- Nguồn Pi mới: việc trên Pi, kiểm `lab\Mo-man-hinh-pi.cmd`, hiệu chuẩn camera.

## Chưa kiểm chứng (chính)
- C2; C8 mới một ca; lợi ích thật của việc quét tìm lại.
- Nhiễu ×2: khoảng cách ~50 m ở đoạn giảm tốc cuối (2 lần chạy). Bộ bám mất nhiều thời gian TRACK khi có vật gây nhiễu độ tin cậy cao ở mọi khung.
- Vì sao chỉ số thời gian bám (A4) không đổi theo ngưỡng 0,065–0,25.
- Video thật: một đoạn duy nhất, trời sáng; cỡ quy đổi dùng hệ số giả định.
- Tất cả là mô phỏng và dữ liệu ghi sẵn; chưa bay thật, chưa chạy trên Pi.
