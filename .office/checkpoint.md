# Checkpoint: phiên 5, cuối giai đoạn 1 (2026-11-19, khoảng 02:00)

Tên dự án: Drone Tracking. Giờ hạn mức đặt lại: không ghi nhận.
Phiên sau đọc: file này, rồi cuối `.office\ledger.md` từ mục "CHẠY TIẾP (người dùng nói "chạy tiếp")". Thiết kế bước 3–6: `.office\design-gimbal-steps-3-6.md`.

## Trạng thái
GIAI ĐOẠN 1 (khớp gật camera, bước 1–7) ĐÃ XONG PHẦN LÀM; đã trình báo cáo cuối giai đoạn, ĐANG CHỜ NGƯỜI DÙNG xem và quyết trước khi sang giai đoạn 2. Không còn mô phỏng hay agent nào chạy (kiểm lại `pgrep -x arducopter` và `git status` trong WSL `Ubuntu-24.04` đầu phiên sau). Không có cờ `_STOP`.

## Quyết định của người dùng (còn hiệu lực)
- Giữ 15 m (hồ sơ `accept_plane_r15`: lùi 10, lùi khẩn 8, sàn chấm 6 m). Dải khớp gật 10°–110°, cất cánh ở 90°.
- 2026-11-19: camera BAY là Camera Module 3 Wide (bỏ Global Shutter). Cổng B1 phải làm lại theo mục tiêu mới (máy bay trainer hoặc drone). Det-Fly trong `vision\data\det-fly\` coi là đủ (7.635 cặp khớp).
- Báo cáo hình: đã duyệt hình tĩnh; VIDEO chỉ làm khi người dùng duyệt riêng.
- Pi: chờ nguồn mới. Bộ MMFW-UAV (140 GB) người dùng tự tải khi ngồi máy.

## Kết quả bước 7 (chi tiết và bằng chứng trong sổ ghi; bảng ở `onboard\simtools\out\_summary_gimbal{D,E,F}_all.txt`)
- Đợt D (δ 10–110°, camera hẹp): 14/14 PASS; giữ 25 m và 15 m, cắm 15°/25° × 3 seed, blackout, disengage; ra khung 0 s; d3 min 11,16 m (sàn 6) và 20,83 m (sàn 8).
- Đợt E (biến thể, 1 seed): đối chứng khớp đứng yên FAIL đúng yêu cầu (4,26 s ở pha cắm); servo chậm ×2 PASS; góc +4° / −15° PASS; giữ 20 m PASS; giữ 12 m FAIL sát ngưỡng (2,04–2,14 s so với 2,0); 20 m/s PASS.
- Đợt F (camera Wide danh định fx 933, 2304×1296, giữ 15 m): 5/5 PASS; lề trong khung 28–33° (hẹp: 9–16°); d3 min 11,27 m.
- Đợt B, C (giới hạn cũ 90°): FAIL ở giảm tốc cuối do δ_max 90° (nguyên nhân gốc đã chứng minh).
- Lô "mốc" bước 1b dùng mô hình khớp kiểu cũ (`camera.gimbal_enabled`), KHÔNG phải camera cố định (đính chính 11-19).

## Báo cáo hình
- Công cụ `onboard\simtools\report_run.py` + 112 ca test (commit `64b7704`), 08 duyệt. Lệnh: `cd onboard && ~/venv-ardupilot/bin/python -m simtools.report_run <run_dir>... --batch-html <file.html>`.
- Hình các đợt: `onboard\simtools\out\_report\index.html` (không vào git).

## Tồn đọng, chờ người dùng quyết
1. Chấp nhận giai đoạn 1 và mặc định đề nghị (giữ 15 m, nhìn xuống −12°, khớp 10–110°, camera Wide)?
2. Drone tự leo cao khi COAST (nguyên nhân đã tìm: `guidance.py:124-188,310-334`); đề nghị sửa đầu giai đoạn 2 (test hồi quy LOS chéo xuống trước).
3. Phát hiện giả lọt tracker khi COAST (`tracker.py:252-272`): giai đoạn 2.
4. Kế hoạch B1 làm lại: bản nháp bị 08 phản biện, chưa trình; cần viết lại theo Wide + nhận diện trên vùng cắt, tách drone / máy bay; chờ dữ liệu máy bay (MMFW-UAV hoặc video tự quay).
5. Đổi mặc định camera trong `config.py` sang Wide + hiệu chuẩn fx trên Pi: việc riêng, chưa có kế hoạch.
6. Video báo cáo: chờ duyệt.
7. Pi: nguồn mới → đọc `~/dtrack/tmp/labview.log`, chạy labview 2 luồng, đo 60 s, kiểm đường hầm (cổng 8080 WSL đang bị demo cũ chiếm).

## Chưa kiểm chứng
- Thông số Wide chưa hiệu chuẩn; nhiễu pixel mô phỏng chưa đổi theo Wide; sai số ước lượng khoảng cách không tăng như dự đoán, chưa giải thích.
- Các biến thể đợt E và đợt F: mỗi ô 1 lần chạy.
- Ở δ = 110° camera có thể bị thân/càng che (phần cứng).
- Trang HTML báo cáo chưa ai mở bằng trình duyệt ngoài người dùng.
- d3 tới 44,7–51,6 m ở pha tăng tốc của hồ sơ giữ 25 m (ngoài cửa sổ chấm 40 m).

## Việc khác
- Panel "Văn phòng" vẫn lỗi; đề xuất ở `~\.claude\office\proposals\2026-11-18-08-panel-plan-loi-dinh-dang-ket-qua.md`.
- Mật khẩu Pi người dùng đã gõ vào cuộc trò chuyện: không dùng, không lưu; nên đổi.
- `HANDOFF.md`, `README.md` gốc: đang cho 05 cập nhật (xem cuối sổ ghi đã xong chưa).
