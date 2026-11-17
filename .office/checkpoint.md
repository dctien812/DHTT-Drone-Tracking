# Checkpoint: cuối phiên 3 (2026-11-17, kết thúc theo yêu cầu người dùng)

Người dùng bảo dừng làm việc cho hôm nay. Không còn agent, mô phỏng hay máy chủ nào chạy.
Giờ hạn mức đặt lại: không ghi nhận (phiên dừng theo yêu cầu, không phải do hạn mức).
Phiên sau đọc: `HANDOFF.md`, rồi phần cuối `.office\ledger.md` (từ dòng "P3").

## Đã xong (kèm bằng chứng)
- Repo private GitHub, mỗi bước một commit; README và HANDOFF cập nhật cuối ngày.
- Mô phỏng bám: sửa 5 lỗi khối nhận biết, sửa bộ điều khiển, đo camera × khoảng cách giữ; khớp gật + giữ 25 m đạt một lần (`onboard\simtools\out\20261117_051353*`); pytest `onboard` 205 passed.
- Nhận diện: model `ft_v8n`; kiểm độc lập hai lần (`vision\results\verify\`, `vision\results\verify_b1\`); cổng B1 "đạt có điều kiện".
- Màn hình lab trên PC (`lab\`, 45 test); Gazebo một máy bay (`gazebo\`); khớp gật trong Fusion, file in ở `STL\`.
- Excel linh kiện: giá Taobao + VND cho đồ lab (`bom\`).

## Chưa xong
- Đang dở: nghiệm thu mô phỏng 3 seed × 2 lần (`run_acceptance.sh`, chưa lần nào hoàn tất); rà soát độc lập mã `onboard\`.
- Chưa bắt đầu: rà bảo mật trang web lab; sửa giữ ID trong màn hình lab; huấn luyện lại model (ảnh âm, chia theo video, Det-Fly); các bước demo S3–S8.

## Chưa kiểm chứng
- Kích thước khớp gật so với servo và camera thật (khe 9 mm, rãnh cánh tay servo).
- Tốc độ nhận diện trên CPU Raspberry Pi 5.
- FC Matek đã nạp ArduCopter hay chưa; cổng MAVLink của bản V3.
- Nhận diện mục tiêu 10–40 px trên cảnh lạ.
- Màn hình lab: webcam, chế độ mạng, trên Pi.

## Bước tiếp theo (đều chờ người dùng)
1. Người dùng duyệt cổng B1 (đạt có điều kiện).
2. Người dùng báo Det-Fly đã tải đủ → chạy huấn luyện lại.
3. Người dùng báo Pi 5 lên mạng + tên đăng nhập → S3.
4. Linh kiện về (camera, cáp 22→15 pin, servo, PCA9685, dây, nguồn 5 V) → S4, S7.
5. Mọi thao tác ghi lên FC: trình người dùng duyệt riêng.

## Theo từng vai (phiên này)
- 02 planner: đã xong: 2 kế hoạch (chặng 1; giai đoạn kế) · đang dở: không · chưa làm: không.
- 03 challenger: đã xong: 5 lượt phản biện · đang dở: không · chưa làm: không.
- 10 investigator: đã xong: nguyên nhân gốc FAIL vòng kín · đang dở: không · chưa làm: không.
- 05 software-engineer: đã xong: Excel CNY, T9d, sửa điều khiển, đo camera/khoảng cách, nhận diện V1, màn hình lab, B1 trên video, bản CadQuery khớp gật · đang dở: nghiệm thu 3 seed (bị dừng) · chưa làm: huấn luyện lại, sửa giữ ID, nguồn hình Pi, điều khiển servo.
- 06 infrastructure-engineer: đã xong: thử Gazebo · đang dở: không · chưa làm: cài Pi 5, xác minh FC.
- 07 test-engineer: đã xong: kiểm độc lập V1 và B1 · đang dở: không · chưa làm: nghiệm thu demo L0/L1.
- 08 checker: đã xong: không · đang dở: không · chưa làm: rà mã `onboard\` (CHƯA từng chạy trong phiên này).
- 09 security-auditor: đã xong: không · đang dở: không · chưa làm: rà trang web lab.
- 11 researcher: đã xong: 2 lượt khảo sát GitHub · đang dở: không · chưa làm: không.
- 12 secretary: đã xong: README (3 lượt), HANDOFF · đang dở: không · chưa làm: không.
