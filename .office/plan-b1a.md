# Kế hoạch B1a: nhận diện máy bay mô hình (bản trình duyệt, 2026-11-19) — CHƯA DUYỆT

Lập: 02 planner (nháp `plan-b1v3-draft.md`). Phản biện: 08 checker, kết luận NÊN SỬA TRƯỚC KHI TRÌNH (6 Nghiêm trọng, 9 Quan trọng). Trưởng phòng sửa theo; phần drone tách thành B1b, làm sau bằng kế hoạch riêng.

## Mục tiêu
Có một bộ nhận diện máy bay mô hình chạy trên vùng cắt 480 px (khung quy về bề rộng 2304 của camera Wide), được đo trên các đoạn video MMFW-UAV không dùng để học và trên bộ bám thật của dự án (`onboard\dtrack\tracker.py`). Trước khi huấn luyện, đo model gốc có sẵn để biết có cần huấn luyện không.

## Tiêu chí (ngưỡng là ĐỀ XUẤT, chưa có căn cứ chặt; mọi số báo kèm khoảng dao động theo đoạn video)
| # | Tiêu chí | Mức đề xuất | Ghi chú |
|---|---|---|---|
| A1 | Tỉ lệ bắt được máy bay (IoU 0,5) trên các đoạn kiểm thử, theo cỡ | 57–200 px ≥ 0,90; 16–57 px ≥ 0,85; > 200 px chỉ báo cáo | Dao động tính bằng bootstrap theo đoạn video (chỉ 6 đoạn kiểm thử), không dùng khoảng tin cậy theo từng khung |
| A2 | Cụm mất liên tiếp, tính bằng GIÂY | Không có cụm ≥ 3 s; báo số cụm ≥ 0,25 s mỗi phút | 0,25 s và 3 s là hai ngưỡng thật của bộ bám (`tracker.py:35-36`). Tần số khung MMFW chưa biết: bước 2 tìm; không tìm được thì giả định 30 khung/giây và ghi rõ |
| A3 | Báo động giả trên vùng nền, tách nền trời và nền mặt đất | ≤ 1 trên 100 vùng nền mặt đất; quy thêm ra số lần mỗi giây | Nền cùng một khuôn viên nên chỉ là cận dưới của thực tế |
| A4 | Chạy bộ bám thật của dự án trên chuỗi phát hiện của đoạn kiểm thử | Thời gian ở trạng thái bám ≥ 0,9 × TRẦN, trong đó trần là kết quả khi đưa nhãn thật vào bộ bám ở cùng tần số khung và cùng chế độ (người dùng duyệt đổi 2026-11-19) | Trần đo được: 0,952 ở 15 khung/giây; 0,894 ở 30; 0,572 ở 60 (tần số khung MMFW chưa biết, báo ở 30 và ghi rõ). Báo cáo ghi chế độ ("mọi phát hiện" / "chỉ phát hiện tin cậy nhất") và tần số khung |
| A5 | Đo vùng cắt lệch tâm và quét toàn khung (tình huống tìm kiếm) | Chỉ báo cáo | Vùng cắt quanh nhãn thật là lạc quan |
| A6 | Ngoài miền: 20 khung máy bay nhãn tay; ảnh chụp thử từ camera Wide của dự án (không có máy bay: đếm báo động giả) | Chỉ báo cáo | n quá nhỏ để đặt ngưỡng |
| A7 | Model xuất được sang NCNN và chạy được ở 480 trên PC | Đạt/không | Tốc độ trên Pi: chờ nguồn |

## Các bước
Quy tắc: mã nào cũng 07 viết test trước → 05 viết → 08 rà. Việc nặng CPU/ổ đĩa không chạy cùng lúc với mô phỏng SITL.

| Bước | Làm gì | Vai | Chạm | Kiểm chứng | Đợt |
|---|---|---|---|---|---|
| 1 | Test trước: chia theo đoạn không rò, tạo vùng cắt 480, công thức A1–A4 | 07 test-engineer | `vision\tests_b1\` (mới) | Đỏ đúng lý do | 1 |
| 2 | Tìm trong dự án: tần số khung MMFW (trong xml/tên file), 20 khung nhãn tay, ảnh chụp thử camera Wide, script V2 dùng lại được | 04 explorer | chỉ đọc | Danh sách đường dẫn đã mở | 1 |
| 3 | Rà test bước 1 | 08 checker | chỉ đọc | Báo cáo 3 mức | 2 |
| 4 | Mã chia tập, tạo vùng cắt | 05 software-engineer | `vision\scripts\b1a\prep_*.py` | Test xanh | 3 |
| 5 | Mã chấm A1–A6, gồm giá chạy `tracker.py` trên chuỗi phát hiện | 05 (lượt khác) | `vision\scripts\b1a\eval_*.py` | Test xanh | 3 |
| 6 | Chạy chia; kiểm rò chéo D/D'/E/E' bằng `vision\verify\leak_features.py`; ghi cỡ và hướng của tập val; đóng băng danh sách kiểm thử (sha256) | 07 | `vision\data\b1a\` (mới) | 0 đoạn trùng; bảng rò chéo | 4 |
| 7 | Rà bước 4–6 (đóng băng chỉ có hiệu lực sau bước này) | 08 | chỉ đọc | Duyệt hoặc sửa | 5 |
| 8 | CỔNG G0: chấm `yolov8n.pt` gốc (lớp airplane của COCO) trên CẢ 12 đoạn (model này chưa học đoạn nào) theo A1–A6 | 07 | `vision\results\b1a\g0_*` | Bảng số | 6 |
| 9 | Đối chiếu G0: tự tính lại trên 200 vùng cắt | 08 | chỉ đọc | Khớp ±0,01 | 7 |
| 10 | Test trước cho bộ dựng tập học (học ∩ kiểm thử = ∅) và cấu hình huấn luyện | 07 | `vision\tests_b1\` | Đỏ đúng lý do | 7 |
| 11 | Mã dựng tập học và huấn luyện một lớp, imgsz 480, có tăng cường mờ chuyển động, đổi màu, đổi cỡ | 05 | `vision\scripts\b1a\` | Test xanh | 8 |
| 12 | Huấn luyện trên CPU qua WSL, 2 seed, chạy nền, có `--resume` | 07 | `vision\runs\b1a\` | Loss giảm; log lỗi rõ | 9 |
| 13 | Chấm đủ A1–A7 cho model mới, so với G0 | 07 | `vision\results\b1a\` | Bảng so | 10 |
| 14 | Rà kết quả, tính lại một ô mỗi tiêu chí | 08 | chỉ đọc | Duyệt hoặc sửa | 11 |
| 15 | Viết báo cáo `B1A_REPORT.md`; 08 rà | 05, 08 | `vision\results\b1a\` | Duyệt | 12 |

Quy tắc cổng G0 (sau bước 9): model gốc đạt cả A1, A3, A4 → KHÔNG huấn luyện, dùng model gốc, bỏ bước 10–13 (chỉ làm A7). Không đạt → huấn luyện (bước 10–13). Trưởng phòng quyết theo quy tắc này và báo người dùng.

## Chia tập
- Học: bộ D và D' (6 đoạn, 8.552 khung), lấy thưa mỗi 6 khung (~1.400 khung dương) + số vùng nền tương đương cắt từ chính các ảnh đó (mỗi ảnh đúng 1 máy bay nên vùng tránh khung là nền thật).
- Val: 15% cuối mỗi đoạn học, bỏ 60 khung đệm; chỉ dùng chọn ngưỡng và epoch.
- Kiểm thử: bộ E và E' (6 đoạn, 10.103 khung), không dùng để học hay chọn ngưỡng.
- Ảnh âm thêm: ảnh chim và nền của `vision\data\coco-neg` (bỏ phần airplane).
- Rủi ro đã biết: mẫu cho thấy cảnh của D và E khác nhau (D có nhà cao tầng ở chân trời, E nhìn xuống rừng trụi lá) nên tập kiểm có thể khó hơn tập học; bước 6 đo bằng số. Nếu rò chéo D–D' hoặc E–E' cao thì coi mỗi cặp là một đoạn khi tính dao động.

## Ước lượng
17–22 lượt gọi vai. Huấn luyện ~3 giờ mỗi seed trên CPU (suy từ lần V2: 7,7 phút/epoch ở 640), 2 seed ~6 giờ, chạy nền. Đĩa 1–2 GB.

## Rủi ro, việc khó hoàn tác, phần không đụng
- Dữ liệu chỉ từ một khuôn viên, mùa đông, ~12 đoạn video: kết quả tốt ở đây KHÔNG chứng minh model chạy tốt với ảnh thật từ camera Wide, nền ruộng/cây xanh, hình mờ khi bay nhanh, góc nhìn xuống 12°.
- Tần số khung MMFW có thể không tìm được → A2 dựa trên giả định.
- Giấy phép MMFW chưa xác minh: chỉ dùng trong lab, không phát hành lại dữ liệu hay model huấn luyện từ nó.
- Huấn luyện chạy nền vài giờ: chỉ ghi vào thư mục mới, dừng và chạy tiếp được; không chạy cùng lúc với mô phỏng.
- Việc khó hoàn tác: không có.
- Không đụng: `onboard\`, `pi\`, trọng số cũ, dữ liệu MMFW đã giải nén (chỉ đọc), kết quả V2, phần drone (B1b), GPU và cấu hình máy.

## Đã sửa theo phản biện của 08
- Tách drone (Det-Fly) ra B1b: bản nháp lặp lại công thức V2 đã thất bại và kéo theo rủi ro model học phân biệt nguồn ảnh thay vì vật thể.
- Bỏ câu "bộ bám chịu được mất 20%" (không có trong sổ ghi); ngưỡng ghi rõ là đề xuất.
- Cụm mất tính bằng giây theo ngưỡng thật của bộ bám; dao động tính theo đoạn video; đo bằng bộ bám của dự án thay ByteTrack; thêm đo vùng cắt lệch tâm; đo ngoài miền chỉ báo cáo.
- Cổng G0 chỉ chấm model gốc có lớp máy bay (hai model cũ của dự án chỉ biết "drone"), quy tắc gồm cả tỉ lệ bám.
- 08 rà test trước khi đóng băng tập kiểm; huấn luyện không chạy cùng mô phỏng; thêm seed thứ hai, tăng cường dữ liệu, kiểm rò chéo, xuất NCNN.
- KHÔNG áp dụng một đề xuất của 08 (xem sổ ghi): viết lại bản giao việc để tránh bộ lọc an toàn.

## Câu hỏi cho người dùng
1. Làm máy bay trước, drone để sau bằng kế hoạch riêng?
2. Huấn luyện bằng CPU (~6 giờ chạy nền, không đổi gì trên máy) hay thử GPU RX 9060 XT (nhanh hơn nếu chạy được, nhưng phải cài thêm và có thể đổi cấu hình máy)?
3. Chấp nhận các mức A1–A4 là mức tạm, chỉnh lại khi có video thật từ camera Wide?

## ĐIỀU CHỈNH TIÊU CHÍ (người dùng, 2026-11-19, lần 2) — THẮNG bảng tiêu chí ở trên
Lý do của người dùng: dữ liệu là ảnh trên mạng, đặt mức 90% là quá khó và không đáng cố; khi thử ngoài sân bay có video thật thì huấn luyện tiếp sẽ nhanh và đúng hơn. Mức đạt hạ xuống 55–65%.
- A1: tỉ lệ bắt được ≥ 0,60 ở mỗi dải cỡ chính (16–57 và 57–200 px). Báo riêng theo hướng nhìn; cảnh nhìn xuống (Top_Down) là số cần theo dõi nhất vì đó là góc nhìn của drone (model gốc: 0,40).
- A2: cụm mất liên tiếp: CHỈ BÁO CÁO (không còn điều kiện "không có cụm ≥ 3 s").
- A3: giữ ≤ 1 báo động giả trên 100 vùng nền mặt đất.
- A4: tỉ lệ bám của bộ bám ≥ 0,65 × trần nhãn thật (cùng tần số khung, cùng chế độ).
- A5, A6, A7: như cũ (báo cáo; xuất NCNN).
- Phạm vi công sức: MỘT vòng huấn luyện theo thiết kế đã dựng (lượt "EE", lượt "DD", model "final"), một seed mỗi lượt; KHÔNG mở vòng tinh chỉnh tham số hay thu thêm dữ liệu mạng. Việc cải thiện tiếp chờ video quay ở sân bay.
- Ghi nhận: theo mức mới, model gốc `yolov8n.pt` đã đạt A1 (0,696 / 0,763), A3 (0,14/100) và A4 (0,759); điểm yếu còn lại là cảnh nhìn xuống (0,40). Vòng huấn luyện này nhằm xem có cải thiện được cảnh nhìn xuống không; nếu không hơn model gốc thì dùng model gốc.
