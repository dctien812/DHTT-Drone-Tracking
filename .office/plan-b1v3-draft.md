# NHÁP kế hoạch cổng B1 làm lại (b1v3) — 02 planner, 2026-11-19 — chưa phản biện, chưa duyệt

02 CHƯA mở: `pi/README.md`, `compare.md` của V2, mã `onboard/`, 4 video máy bay và 20 khung nhãn tay. Nhiều số là suy ra, chưa đo.

## 1. Mục tiêu và tiêu chí
Mục tiêu: một bộ nhận diện chạy trên vùng cắt 480 px từ khung đã quy về bề rộng 2304, hai lớp `airplane` và `drone`. Đo trên dữ liệu đúng cỡ và vùng cắt, rồi đối chiếu với nhu cầu của bộ bám.

Căn cứ chung cho ngưỡng: lô mô phỏng `regrG2` (sổ ghi): cụm mất 15 khung với tỉ lệ mất 12–14% thì an toàn đạt (chỉ TRACK 86–89% < 90%); cụm 45 khung thì drone bị bỏ lại xa (d3 max 119 m).

| # | Tiêu chí (trên tập kiểm đóng băng) | Ngưỡng | Căn cứ |
|---|---|---|---|
| C1 | Recall máy bay ở IoU 0,5, ngưỡng conf chốt trên val | 57–200 px ≥ 0,90; 16–57 px ≥ 0,80; > 200 px chỉ báo cáo | Mất 11–14% thì TRACK < 90%; mất 20% là mức bộ bám chịu được |
| C2 | Mất liên tiếp trên chuỗi khung liên tục | 0 cụm ≥ 45 khung; số cụm ≥ 15 khung báo cáo, đề xuất ≤ 1 cụm/1.000 khung | Lô `regrG2`. Chưa quy ra giây: cần tần số khung MMFW |
| C3 | Báo động giả trên crop nền (nền MMFW kiểm thử, nền Det-Fly kiểm thử) | ≤ 2/100 crop | Đề xuất, chưa có căn cứ từ bộ bám; mốc V2 là 9,3/100 |
| C4 | Recall drone trên khối Det-Fly kiểm thử, quy cỡ 20–57 px | ≥ 0,80 (mục tiêu 0,90); 16–20 px báo cáo riêng | V2 đạt 0,638 |
| C5 | Nhầm lớp | ≤ 5% | Đề xuất; V2 nhầm 70% |
| C6 | Giữ ID trên 6 chuỗi kiểm thử ở tốc độ khung gốc (ByteTrack như B1) | ≥ 90% khung mang đúng 1 ID | Đề xuất; mốc cũ 29,8% video giữ 1 ID |
| C7 | Đối chứng ngoài miền: 4 video và 20 khung nhãn tay | máy bay được gọi đúng lớp ≥ 80%, báo theo cỡ | Mốc cũ: 100% bị gọi "drone" |
| C8 | Tốc độ trên Pi 5 | Chưa đo được (Pi chờ nguồn) | yolov8n imgsz 480 NCNN: 14,28 khung/giây (1 nhân), 19,67 (2 nhân) (`pi/results/S3_REPORT.md:6,9`) |

C1, C3, C4 báo theo cỡ (16–57, 57–200, > 200 px) và theo hướng (Top_Down, Horizontal, Bottom_Up), kèm n và khoảng tin cậy Wilson; ô n < 30 ghi "không kết luận".

## 2. Các bước
| ID | Làm gì | Vai | Chạm | Kiểm chứng | Đợt |
|---|---|---|---|---|---|
| S1 | Test trước: chia không rò, tạo crop 480 quy 2304, công thức recall / cụm mất / ID | 07 | `vision\tests_b1\*` (mới) | Đỏ đúng lý do | 1 |
| S2 | Tra: vị trí 4 video và 20 khung nhãn, danh sách khối Det-Fly, tần số khung và giấy phép MMFW, `coco-neg` còn không | 04 (đọc, không web) | chỉ đọc | Danh sách đường dẫn đã mở | 1 |
| S3 | Mã chia tập và tạo crop | 05 | `vision\scripts\b1v3\prep_*.py` | Test S1 xanh | 2 |
| S4 | Mã chấm: recall theo cỡ/hướng, FP, cụm mất, ID | 05 (lượt khác) | `vision\scripts\b1v3\eval_*.py` | Test S1 xanh | 2 |
| S5 | Chạy chia, đóng băng danh sách kiểm thử (sha256), kiểm rò | 07 | `vision\data\b1v3\` (mới) | 0 chuỗi/khối trùng; `vision\verify\leak_features.py`; xem bằng mắt 60 crop nền | 3 |
| S6 | Rà S1–S5 | 08 | đọc | Báo cáo 3 mức | 4 |
| S7 | CỔNG G0: chấm `ft_v8n_best.pt`, `ft2_v8n_best.pt`, `yolov8n.pt` (lớp airplane COCO) trên tập kiểm | 07 | `vision\results\b1v3\g0_*` | Bảng C1, C3, C4, C5 | 5 |
| S9 | Test trước cho bộ dựng tập học và cấu hình huấn luyện (học ∩ kiểm thử = ∅) | 07 | `vision\tests_b1\` | Đỏ đúng lý do | 5 |
| S8 | Đối chiếu G0: tự tính lại 1 model trên 200 crop | 08 | đọc | Khớp ±0,01 | 6 |
| S10 | `build_train_v3.py`, `train_v3.py` (từ `train_v2.py`, imgsz 480, 2 lớp) | 05 | `vision\scripts\b1v3\` | S9 xanh | 6 |
| S11 | Dựng tập học, huấn luyện CPU qua WSL, chạy nền | 07 | `vision\runs\b1v3\` | Loss giảm sau 2 epoch; test không lẫn học | 7 |
| S12 | Chấm đủ C1–C7, gồm bám chuỗi | 07 | `vision\results\b1v3\` | Bảng so với G0 | 8 |
| S13 | Rà kết quả, tính lại 1 ô mỗi tiêu chí | 08 | đọc | Duyệt hoặc sửa | 9 |
| S14 | Viết `B1_V3_REPORT.md` | 05 | `vision\results\b1v3\` | S15 | 10 |
| S15 | Rà báo cáo | 08 | đọc | Duyệt hoặc sửa | 11 |

Cổng G0 sau S8, phiên chính quyết: COCO airplane hoặc model cũ đạt C1 và C3 cho máy bay thì không huấn luyện lớp máy bay, chỉ phần drone; không đạt thì huấn luyện hai lớp.

## 3. Chia tập (ảnh Wide, quy về 2304, crop 480)
- Kiểm thử MMFW: cả E và E' (6 chuỗi, 10.103 khung): đủ 3 hướng, nhiều khung nhỏ (E' Bottom_Up 57,6% trong 16–57 px); chưa biết ký hiệu ' có cùng chuyến bay không nên giữ cả cặp ra ngoài.
- Học MMFW: D và D' (6 chuỗi, 8.552 khung), lấy thưa mỗi 6 khung → ~1.200 khung dương + ~1.200 crop nền.
- Val: 15% khung cuối mỗi chuỗi học, bỏ 60 khung đệm; chỉ dùng chọn ngưỡng và epoch.
- Det-Fly: chia theo khối nguyên; kiểm thử 3 khối (ít nhất 1 khối 010 và 1 khối 020), val 1 khối, học phần còn lại lấy thưa mỗi 4 khung (~1.300 khung).
- Ngoài miền: 4 video máy bay (`D:\Personal\DHTT-TRACKING-TEST\AI-6\video`, chưa mở) + 20 khung nhãn tay: chỉ kiểm.

## 4. Thiếu ảnh âm, nền kém đa dạng
- Nền cùng ảnh: crop tránh khung (mỗi ảnh đúng 1 khung) là nền thật.
- Nền chéo bộ: crop nền Det-Fly làm âm cho cả hai lớp; ảnh máy bay là âm cho drone và ngược lại.
- Chim: ảnh chim COCO nếu `data/coco-neg` còn; bỏ COCO airplane khỏi tập âm.
- Đổi cỡ: thu nhỏ khung trước khi crop (hệ số tối thiểu ~0,37).
- Loại: dán máy bay tổng hợp lên nền khác (V2 đã thất bại vì lệch miền).
- Giới hạn còn lại: nền máy bay chỉ là một khuôn viên mùa đông.

## 5. Một model hai lớp (có nhánh lùi)
Hai model thì gần nửa tốc độ Pi. Rủi ro: lớp bị gắn với bộ dữ liệu (nền mùa đông = máy bay, nền Det-Fly = drone); C3, C5 để bắt. Nhánh lùi: C5 không đạt thì tách hai model đơn lớp (+1 lần huấn luyện ~3 giờ).

## 6. Ước lượng
20–24 lượt gọi vai. Huấn luyện: lần trước CPU 7 luồng qua WSL, 3,83 giờ cho 4.200 ảnh ở 640; với 480, ~4.500 crop, 40 epoch → ước 3–4 giờ (suy ra). Đĩa 1–2 GB. GPU RX 9060 XT: chưa kiểm dùng được cho PyTorch, mặc định CPU.

## 7. Rủi ro, hoàn tác, không đụng
Val và test cùng một khuôn viên → số đo lạc quan; tần số khung MMFW chưa biết; một seed (thêm seed 1 nếu sát ngưỡng ±0,03); giấy phép MMFW chưa xác minh (lab, không phát hành lại). Không có việc khó hoàn tác (chỉ ghi vào thư mục mới `vision\data\b1v3`, `vision\runs\b1v3`, `vision\results\b1v3`). Không đụng: `onboard\`, `pi\`, trọng số cũ, dữ liệu MMFW giải nén, kết quả V2.

## 8. Không chứng minh được
Ảnh thật từ Camera Module 3 Wide (màu, nhiễu, lấy nét), nền ruộng/cây xanh, mờ chuyển động, góc nhìn xuống 12°, chim, tốc độ trên Pi; chưa chắc bộ bám trong `onboard/` nhận được đầu ra này (C6 đo bằng ByteTrack). Việc bù nhỏ nhất: người dùng quay 3–5 phút video 2304×1296 bằng camera Wide (máy bay trên nền đất/cây + 1 phút nền trống) → ~100 khung gán nhãn để đo lại C1, C7.

## 9. Câu hỏi cho người dùng
1. Thử GPU (RX 9060 XT) hay giữ CPU 3–4 giờ?
2. Trang tải MMFW có ghi tần số khung và giấy phép không?
3. B1 đạt chỉ trên MMFW + Det-Fly thì đóng cổng tạm hay chờ video quay thật?
4. Chấp nhận các ngưỡng C1, C3, C5, C6 không?
