# Checkpoint: tổng kết giai đoạn, dừng chờ phần cứng (2026-11-20, khoảng 11:40)

Tên dự án: Drone Tracking. Lý do ghi: người dùng yêu cầu tổng kết; phần mô phỏng DỪNG tới khi đủ phần cứng (nguồn Pi chưa về). Không phải tổng kết do hạn mức, nên không có giờ đặt lại.
Phiên sau đọc: file này, rồi cuối `.office\ledger.md` (mục "Phiên 7"). Kế hoạch đã chạy hết và đã được chấp nhận: `.office\plan-phase2.md`, `.office\plan-b1a.md`, `.office\plan-phase2b.md`. Thiết kế khối tìm lại: `.office\design-search.md` (S-1…S-16; mục sau thắng mục trước).

## Lưu ý vận hành
- Đồng hồ WSL chậm 7 giờ so với giờ máy. Luôn gọi `wsl -d Ubuntu-24.04` (distro mặc định là BambuStudio). pytest: `~/venv-ardupilot/bin/python` cho `onboard`, `~/venv-vision/bin/python` cho `vision\tests_b1`.
- Git: commit bằng Git for Windows (Git Bash); fetch/push bằng git của WSL, lệnh trơn: `wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Personal/Drone-Tracking && git push origin main"` (khóa `id_dtrack` chỉ có trong WSL; kèm tham số ghi đè khóa thì bị bộ kiểm quyền chặn).
- Một SITL mỗi lúc; khi SITL hoặc huấn luyện chạy: không việc nặng ổ D, không chơi game trên máy.
- Repo GitHub công khai. Không đưa lên: ảnh, video của người dùng (`.office/images/`) và thứ sinh ra từ đó (`vision/results/b1a/realvideo1/`), `pi/pi.env`, `vision/data/`, `vision/.venv-gpu/`, `onboard/simtools/out/`, `pi/camtest_*`. Trước mỗi lần đẩy: `git add -A -n` và tìm tên đăng nhập, IP, đường dẫn hồ sơ Windows. Không viết lại lịch sử git.
- Bước bị bộ lọc an toàn dừng: báo người dùng trong chat kèm prompt; không đưa vào báo cáo, không viết lại để né, không tự làm thay.
- Trước khi đề xuất việc gì: grep sổ ghi xem người dùng đã quyết chưa.

## Quyết định còn hiệu lực của người dùng
- Phần nhận diện giữ nguyên: model gốc yolov8n (lớp airplane) ngưỡng 0,12; huấn luyện tiếp chỉ khi có video/ảnh quay ở sân bay; mức đạt 60–70%.
- KHÔNG sửa luật hãm của drone và không bật lại cơ chế "giả định mục tiêu hãm" (quyết 11-19: hãm mạnh làm hình chập chờn, drone tụt lại). Giữ kịch bản mô phỏng (mục tiêu dừng ~7 m/s²); ra thực tế có số đo mới điều chỉnh. ĐỪNG đề xuất lại.
- Áp sát ~1 m không coi là rủi ro va chạm vì drone bay cao hơn mục tiêu.
- Khối tìm lại mặc định TẮT; bật qua hồ sơ `search_plane_r15`.
- Mật khẩu Pi không đổi. Ảnh mô phỏng trong repo giữ nguyên.

## Đã xong (kèm bằng chứng)
- Giai đoạn 1 (bám giữ 15 m, nhìn xuống 12°, gimbal 10–110°, camera Module 3 Wide trong mô phỏng): người dùng chấp nhận 11-19.
- Giai đoạn 2 (khối tìm lại sau khi mất hình): 21 bước, chấp nhận 11-19, commit `97b7f50`. SITL `srchG3` 26 lần + `srchG4` 8 lần.
- Giai đoạn 2b (S-16: giữ hướng ngắm cuối tới giây 12 rồi mới quét; điều tra áp sát cuối bài; sửa tài liệu): 9 bước, chấp nhận 11-20, commit `bf76ee0`. SITL `srchH1` 20 lần: bổ nhào bật 8,17 s so với tắt 8,18 s (trước ≈ 11 s). Test `onboard`: 1412 passed, 1 xfailed.
- B1a (nhận diện máy bay): 15 bước, một vòng huấn luyện trên card (2 giờ 47 phút), chấp nhận 11-19. Báo cáo `vision\results\b1a\B1A_REPORT.md`. Test `vision`: 177 passed.
- Dọn tên đăng nhập/IP khỏi file theo dõi, gỡ ảnh camera thử, quy trình push qua WSL. HEAD = `origin/main` (xem `git log -1`).

## Chưa xong
Đang dở: không có.
Chưa bắt đầu (chờ phần cứng hoặc dữ liệu):
- Mọi việc trên Pi 5: chạy khối nhận diện + bám trên Pi, đo tốc độ khung, xuất model NCNN, kiểm `lab\Mo-man-hinh-pi.cmd`, hiệu chuẩn camera Wide (sau đó mới đổi camera mặc định trong mã).
- Phần cứng drone: khớp gật servo thật, đấu nối FC Matek H743, cổng duyệt phần cứng B1–B6 (xem HANDOFF.md); mọi thao tác ghi lên FC cần người dùng duyệt riêng.
- Huấn luyện vòng 2 (thêm mẫu nền khó từ video sân bay; đo model final qua bộ bám).
- Việc mô phỏng đã gác, chỉ làm khi người dùng mở lại: chạy bù C8 (leo 10 m thêm 2 seed, 20 m 1 seed), trần chênh cao khi bám ở xa, ca chứng minh quét có ích, C2.
- Một câu trong ba file tài liệu công khai còn ghi "chưa quyết sửa kịch bản hay luật hãm": nay đã quyết (không sửa); sửa câu này ở lần cập nhật tài liệu kế tiếp.

## Chưa kiểm chứng
- Mọi kết quả là mô phỏng hoặc dữ liệu ghi sẵn: chưa bay thật, chưa chạy trên Pi, servo thật khác mô hình.
- Chưa có ca nào cho thấy bật tìm lại tốt hơn tắt (mục tiêu luôn tự hiện lại); C2 chưa đủ bằng chứng; C8 mới 1–2 ca leo thật.
- Áp sát cuối bài 11/19 lần (3,9–7,9 m) khi mục tiêu mô phỏng dừng gấp: rõ nguyên nhân, không sửa; chưa biết mục tiêu thật giảm tốc gấp cỡ nào.
- Nhận diện: một video thật duy nhất, trời sáng; cỡ quy đổi là giả định; chưa chấm chéo card/CPU; model final nhiều phát hiện giả (69 so với 4 trên 269 khung).
- Sau khi tìm lại ở xa, drone leo thêm tới +20,5 m (đúng thiết kế giữ góc 12°); chưa có trần.

## Bước tiếp theo (khi người dùng báo đồ về)
1. Nguồn Pi về: bật Pi, kiểm kết nối bằng `pi\pi.env`, chạy `lab\Mo-man-hinh-pi.cmd`, đo tốc độ nhận diện trên Pi với model gốc.
2. Hiệu chuẩn camera Wide thật, cập nhật thông số camera trong hồ sơ.
3. Lắp khớp gật servo, đo tốc độ và độ trễ thật, so với mô hình (300°/s, trễ 0,05 s); chỉnh `scan_start_s`, tốc độ quét nếu cần.
4. Có video sân bay: huấn luyện vòng 2 theo `B1A_REPORT.md` mục việc vòng sau.
5. Lập kế hoạch mới cho chặng phần cứng và trình người dùng duyệt trước khi làm.

## Theo từng vai (phiên 7, không vai nào đang chạy)
- 02 planner — đã xong: bản nháp kế hoạch 2b · đang dở: không · chưa làm: kế hoạch chặng phần cứng.
- 05 software-engineer — đã xong: mã S-16, tài liệu, B1A_REPORT · đang dở: không · chưa làm: sửa một câu tài liệu về quyết định luật hãm.
- 07 test-engineer — đã xong: test đỏ/xanh S-16 (41 ca), lô SITL `srchH1`, huấn luyện và chấm B1a · đang dở: không · chưa làm: đo trên Pi.
- 08 checker — đã xong: phản biện kế hoạch 2b, rà mã, đối chiếu số đo, rà tài liệu · đang dở: không.
- 09 security-auditor — đã xong: soát trước khi đẩy GitHub (11-19) · đang dở: không.
- 10 investigator — đã xong: nguyên nhân chậm 3 s, độ cao sau tìm lại, áp sát cuối bài · đang dở: không.
