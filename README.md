# Drone-Tracking: drone tự bám một drone khác

Dự án làm drone 8 inch tự bay theo một drone khác bằng camera và giữ khoảng cách an toàn. Hiện đang ở giai đoạn mô phỏng và demo trong phòng lab. **Chưa có lần bay thật nào.**

## Tóm tắt cho mọi người

Dự án nhằm làm cho một drone tự nhìn thấy một drone khác bằng camera, bám theo và giữ khoảng cách an toàn. Trước khi đưa lên trời, mọi thứ được thử trên máy tính: trong mô phỏng (không gian ảo có vật lý), trên các video đã ghi sẵn, và trên một màn hình demo trong phòng lab. Đến nay, trong mô phỏng, drone đã bám đúng một mục tiêu bay thẳng ở tốc độ 36 km/h và giữ khoảng cách 25 m trong một lần thử; các cấu hình và tốc độ khác vẫn chưa đạt. Phần nhận diện tìm được drone ở phần lớn khung hình, nhưng hay nhầm máy bay thành drone và chưa giữ được một mục tiêu liên tục. Bước tiếp theo là chạy hệ thống trên máy tính nhỏ Raspberry Pi 5 với camera thật trong phòng lab. Mọi bước gần bay thật phải được chủ dự án duyệt từng cổng. Mục tiêu thiết kế là tốc độ tối đa 400 km/h, nhưng chưa có bằng chứng nào cho con số này.

## Trạng thái hiện tại (cập nhật 2026-11-17)

Chú thích: **ĐẠT** đã kiểm và đạt tiêu chí. **ĐANG LÀM** có việc đang dở. **CHƯA LÀM** chưa bắt đầu. **CHƯA CHẠY THẬT** chưa thử trên phần cứng thật.

| Phần | Trạng thái | Nghĩa là gì |
|---|---|---|
| Mô phỏng tự bám (trên máy tính) | ĐANG LÀM | Một lần thử bay thẳng 36 km/h, giữ 25 m: đạt. Khoảng cách nhỏ nhất giữa hai drone là 9,29 m (tiêu chí tối thiểu 8 m). Các cấu hình khác chưa đạt, chưa đủ 3 lần thử |
| Nhận diện drone trên video ghi sẵn (cổng B1) | ĐẠT CÓ ĐIỀU KIỆN, chờ chủ dự án duyệt | Trên tập nhãn tay: bắt được drone ở 89 trên 99 khung có drone (88,9%). Nhầm máy bay thành drone, giữ ID kém, drone nhỏ dưới 10 px dễ sót |
| Demo màn hình lab trên PC (video ghi sẵn) | ĐẠT | Hiện khung hình, khóa mục tiêu bằng nút bấm. Không gửi lệnh tới drone hay bộ điều khiển bay nào |
| Demo trên Raspberry Pi 5 với camera thật | CHƯA CHẠY THẬT | Pi 5 chưa cài hệ điều hành, linh kiện đang về |
| Mô phỏng Gazebo | ĐẠT với một drone; CHƯA LÀM với hai drone | Camera ảo chạy khoảng 10 khung hình mỗi giây |
| Bay thật | CHƯA CHẠY THẬT | Chưa bay lần nào. Mọi thao tác ghi lên bộ điều khiển bay cần chủ dự án duyệt riêng |

## Việc kế tiếp và đang chờ

**Đang chờ chủ dự án:**

1. Duyệt cổng B1 (nhận diện trên video). Kiểm tra độc lập kết luận "đạt có điều kiện", với ba điều kiện nêu trong bảng trạng thái.
2. Báo khi bộ dữ liệu Det-Fly tải xong. Khi đó mới huấn luyện lại model, có thêm ảnh máy bay và chim làm ảnh âm.
3. Báo khi Raspberry Pi 5 lên mạng, kèm tên đăng nhập (không kèm mật khẩu).
4. Linh kiện về: camera Module 3 Wide, cáp 22→15 chân cho Pi 5, servo MG90S, bo PCA9685, dây nối, nguồn 5 V riêng cho servo. Tình trạng từng món xem trong Excel `bom/`.
5. Duyệt riêng mọi thao tác ghi lên bộ điều khiển bay (nạp firmware, đổi tham số).

**Việc kế tiếp, theo thứ tự:**

1. Hoàn tất nghiệm thu mô phỏng: 3 seed (3 lần chạy với số ngẫu nhiên khác nhau) × 2 lần ở 10 m/s, mục tiêu bay thẳng, mất hình 3 giây, giành quyền. Chạy khi chủ dự án cho phép.
2. Rà soát độc lập phần mã bám và bảo mật trang lab trước khi mở ra mạng.
3. Nhận diện: kiểm lại trên tập sạch và huấn luyện lại model sau khi có dữ liệu Det-Fly.
4. Demo lab, theo các bước dưới đây.

| Bước | Việc | Trạng thái | Điều kiện để bắt đầu |
|---|---|---|---|
| S1 | Hoàn tất cổng B1 (theo dõi ID trên video) | Xong, chờ duyệt | Không còn |
| S2 | Màn hình web hiện hình, khóa, hủy (chạy trên PC) | Xong trên PC. Chưa thử webcam, chưa thử qua mạng | Không còn |
| S3 | Đo tốc độ trên CPU Pi 5, xuất model dạng NCNN | Chưa làm | Pi 5 cài xong hệ điều hành và lên mạng |
| S4 | Mốc L0: chạy màn hình trên Pi 5 với camera thật; hiệu chuẩn camera bằng bàn cờ để tính góc | Chưa làm | Có camera và cáp; S3 xong |
| S5 | Xác minh bộ điều khiển bay ở chế độ chỉ đọc, chưa có bằng chứng bộ này đã nạp ArduCopter | Chưa làm | Bộ điều khiển nối được với máy tính. Thao tác ghi cần duyệt riêng |
| S6 | Cổng B3: nối bộ điều khiển bay, chỉ đọc dữ liệu | Chưa làm | S5 xong và cổng B3 được duyệt |
| S7 | Khớp gật một trục in 3D, điều khiển bằng servo | Đang làm: thiết kế xong, đang in | Servo, bo điều khiển, nguồn 5 V về |
| S8 | Mốc L1: thêm khớp gật do Pi điều khiển, đọc bộ điều khiển bay ở chế độ chỉ đọc, công tắc trên tay điều khiển | Chưa làm | S4, S5, S7 xong |

Các cổng duyệt B1–B6: chủ dự án duyệt từng cổng trước khi sang bước sau.

| Cổng | Nội dung bằng lời | Trạng thái |
|---|---|---|
| B1 | Nhận diện và theo dõi drone trên video ghi sẵn | Đạt có điều kiện, chờ duyệt |
| B2 | Máy tính AI và camera gắn trên bàn | Chưa. Pi 5 đã có; camera bay và AI HAT+ chưa có |
| B3 | Nối bộ điều khiển bay, chỉ đọc dữ liệu | Chưa |
| B4 | Mô phỏng và an toàn: tự bám, giữ khoảng cách | Đang làm, chỉ trong mô phỏng |
| B5 | Thử tích hợp trên mặt đất: chốt camera và khoảng cách giữ | Chưa |
| B6 | Bay quan sát có kiểm soát | Chưa. Chỉ sau B1–B5 đạt và được duyệt |

## Giải thích thuật ngữ

| Từ | Nghĩa |
|---|---|
| Quad 8 inch | Drone bốn động cơ, dùng cánh quạt đường kính 8 inch (khoảng 20 cm) |
| Bộ điều khiển bay (FC) | "Bộ não" của drone, điều khiển động cơ. Dự án dùng Matek H743-WING V3 chạy phần mềm ArduCopter |
| Mô phỏng SITL | Chạy phần mềm bay của drone trên máy tính, không cần phần cứng |
| Gazebo | Phần mềm mô phỏng thế giới 3D có vật lý và camera ảo |
| Máy đồng hành | Máy tính nhỏ gắn trên drone, xử lý hình ảnh. Dự án dùng Raspberry Pi 5 |
| Nhận diện | Tìm drone trong từng khung hình. Kết quả là một khung chữ nhật bao quanh drone |
| Khung hình | Một ảnh trong video. Video thường có khoảng 30 khung mỗi giây |
| ID (theo dõi) | Số gắn cho một vật qua nhiều khung hình. Đổi ID nghĩa là hệ thống coi như mất mục tiêu rồi gặp lại vật khác |
| Ngưỡng tin cậy (0,25, 0,5) | Mức chắc chắn tối thiểu để model báo có drone. Ngưỡng thấp bắt được nhiều hơn nhưng báo nhầm nhiều hơn |
| Recall (tỉ lệ bắt được) | Trong các khung có drone, bao nhiêu khung model thấy drone |
| Báo động giả | Model báo có drone khi không có. Đếm theo số lần trên 100 ảnh |
| px (điểm ảnh) | Đơn vị đo kích thước trong ảnh. Drone 10 px là rất nhỏ |
| Khớp gật (gimbal một trục) | Giá đỡ camera ngẩng hoặc cúi bằng servo, để giữ mục tiêu trong khung hình |
| Servo | Động cơ nhỏ quay theo góc. PCA9685 là bo mạch điều khiển nhiều servo |
| Khoảng cách giữ | Khoảng cách drone cố giữ với mục tiêu. Nghiệm thu dùng 25 m |
| Mất hình | Hệ thống không thấy mục tiêu trong một lúc |
| Giành quyền | Người điều khiển lấy lại quyền điều khiển; đo bằng thời gian ngừng gửi lệnh tự động |
| Trạm mặt đất (GCS) | Laptop theo dõi và điều khiển drone, dùng phần mềm Mission Planner |
| Kính FPV | Kính xem hình trực tiếp từ camera drone |
| Cổng duyệt | Điểm dừng bắt buộc để chủ dự án duyệt trước khi làm bước sau |
| m/s và km/h | 10 m/s bằng 36 km/h |

<details>
<summary><b>Chi tiết kỹ thuật 1: mục tiêu thiết kế và phần cứng</b></summary>

Mục tiêu thiết kế (chưa có phần cứng nào đạt các con số này):

| Hạng mục | Mục tiêu | Trạng thái |
|---|---|---|
| Tốc độ tối đa | 400 km/h (thay cho 350 km/h, chốt 2026-11-17) | CHƯA ĐẠT, chưa có bằng chứng |
| Tốc độ hành trình | 200–250 km/h | Chưa xét lại sau khi đổi tốc độ tối đa |
| Tốc độ mục tiêu bám được | khoảng 270–290 km/h | Ước tính, chưa kiểm bằng mô phỏng |
| Góc nghiêng | 65–75° khi bay 350–400 km/h | ArduCopter giới hạn 80°. Chưa tính lại cho 400 km/h |
| Điều khiển | Lệnh vận tốc NED, chế độ GUIDED, 10–20 Hz | Đang làm trong mô phỏng. Chưa chạy thật trên bộ điều khiển bay |

Phần cứng:

| Hạng mục | Lựa chọn | Trạng thái |
|---|---|---|
| Bộ điều khiển bay | Matek H743-WING V3 | Đã có |
| Máy đồng hành | Raspberry Pi 5 8 GB, có tản nhiệt | Đã có |
| Tăng tốc AI | AI HAT+ (Hailo-8, 26 TOPS) | Chưa có. Lab chạy nhận diện bằng CPU của Pi |
| Camera bay | Raspberry Pi Global Shutter (IMX296, 1456×1088), lens 6 mm hoặc 8 mm | Chưa có, khan hàng ở các nguồn đã tra |
| Camera lab | Raspberry Pi Camera Module 3 Wide | Đang mua, chưa về. Khác camera dự kiến bay |
| Khung | Apex HD 8 inch làm đế, vỏ in 3D kiểu tên lửa | Dự kiến, số liệu khung chưa xác minh |
| Động cơ | Động cơ 3110 không đủ (khoảng 0,9 kW mỗi cái). Ứng viên 3115, 3120, 3220 | Chưa chốt, sau chặng 3 |
| Radio (lab) | Radiomaster Pocket + RX XR4 | Đã có. Trong lab chỉ đọc kênh RC |
| Sạc pin | ToolkitRC M8D | Đã có |
| Trạm GCS | Mission Planner trên laptop Windows 11 | Chưa chọn máy |

Nguồn: sổ ghi `.office/ledger.md` (2026-11-17). Mua sắm chi tiết xem Excel `bom/`.

</details>

<details>
<summary><b>Chi tiết kỹ thuật 2: mô phỏng</b></summary>

Kịch bản nghiệm thu: mục tiêu bay thẳng ở 10 m/s, tăng tốc lúc đầu, phanh khoảng 8 m/s² lúc cuối. Drone bám bằng khớp gật, giữ 25 m.

Tiêu chí: sai số trung bình dưới 3 m trong cửa sổ đo 120 giây; khoảng cách thật không dưới 8 m suốt chuyến; bám ít nhất 90% thời gian; chạy 3 seed, mỗi seed 2 lần. Thêm: mất hình 3 giây (khoảng cách nhỏ nhất không dưới 8 m và bắt lại được) và giành quyền (ngừng lệnh dưới 0,1 s). Tiêu chí cũ (đổi hướng, 15 m) đã thay ngày 2026-11-17.

Kết quả, mỗi ô một lần thử, seed 1 (nguồn: file `result.txt` của từng lần chạy mô phỏng; thư mục kết quả không đưa lên GitHub):

| Cấu hình | Giữ 15 m | Giữ 25 m | Giữ 40 m |
|---|---|---|---|
| Camera cố định, lens 6 mm | CHƯA ĐẠT: sai số TB 0,32 m, nhỏ nhất 5,40 m | CHƯA ĐẠT: TB 0,43 m, nhỏ nhất 7,40 m | CHƯA ĐẠT: TB 3,46 m |
| Khớp gật (servo) | CHƯA ĐẠT: TB 0,32 m, nhỏ nhất 5,81 m | **ĐẠT** (một lần): TB 0,57 m, nhỏ nhất 9,29 m, bám 100% | CHƯA ĐẠT: TB 3,90 m |
| Lens 4 mm | — | CHƯA ĐẠT: TB 0,72 m, nhỏ nhất 7,07 m | — |

Nghĩa là gì: TB là sai số trung bình so với khoảng cách đặt (càng nhỏ càng tốt). Nhỏ nhất là khoảng cách gần nhất giữa hai drone trong suốt chuyến (không được dưới 8 m). Bám 100% nghĩa là suốt thời gian đo, hệ thống luôn ở trạng thái đang bám.

| Kiểm khác | Kết quả | Nghĩa là gì | Trạng thái |
|---|---|---|---|
| Mất hình 3 s (khớp gật, 25 m) | nhỏ nhất 11,12 m, bám 97,5% | Mất hình 3 giây, khoảng cách vẫn không dưới 8 m | ĐẠT (một lần) |
| Ca có rẽ (khớp gật, 25 m) | nhỏ nhất 8,14 m | Mục tiêu đổi hướng. Chỉ để tham khảo | Tham khảo |
| Giành quyền: ngừng gửi lệnh | 0,021 s | Ngừng lệnh nhanh hơn ngưỡng 0,1 s | ĐẠT (cấu hình trước khi chốt khớp gật) |
| Khớp gật, 20 m/s | nhỏ nhất 1,64–3,74 m khi phanh | Quá gần. Tốc độ 20 m/s đã bỏ khỏi nghiệm thu này | CHƯA ĐẠT, ngoài phạm vi |

Lần ĐẠT ở 25 m: mục tiêu ra khỏi khung hình 2 lần, tổng 5,36 giây, đều trong lúc phanh cuối. Đây là điểm cần theo dõi khi tăng tốc.

Nguyên nhân các lần chưa đạt (điều tra ngày 2026-11-17): khi mất mục tiêu, drone đứng yên thay vì bay tiếp theo vận tốc ước lượng; giới hạn phanh quá thấp; vòng giữ mục tiêu giữa khung đẩy mục tiêu ra mép; gia tốc ngang không đủ khi rẽ ở 20 m/s. Một phần đã sửa trong mã. Lần sửa bộ điều khiển trước đó (kịch bản có rẽ, chưa chạy kịch bản bay thẳng) vẫn cho khoảng cách nhỏ nhất 5,27–5,89 m khi mục tiêu phanh gấp.

Số lần kiểm: `pytest` của `onboard/` cho 205 passed (theo sổ ghi 2026-11-17). Chưa có lần nghiệm thu 3 seed × 2 lần nào hoàn tất.

Bảng khả thi tốc độ (chỉ tính toán, không mô phỏng). Nguồn: `onboard/docs/feasibility_speed.md`, tạo bởi `onboard/simtools/feasibility_table.py`. Công thức: khoảng cách an toàn = v·τ + v²/(2a_drone bám) − v²/(2a_mục tiêu) + sai số + 8 m. Giả định τ = 0,35 s và a = 4,1 m/s² lấy từ mô phỏng quad 0,8 kg, **không phải drone thật**. Số bậc FC gốc nằm trong file kết quả thử bậc của mô phỏng (không đưa lên GitHub). Số đo chỉ đến 10 m/s, phần còn lại là ngoại suy.

| Tốc độ | Khoảng cách an toàn (mục tiêu phanh 8 m/s², lens 6 mm) | Mục tiêu còn bao nhiêu px |
|---|---|---|
| 10 m/s (36 km/h) | 17,9 m | khoảng 29 px |
| 20 m/s (72 km/h) | 41,3 m | khoảng 13 px, dưới ngưỡng 20 px |
| 30 m/s (108 km/h) | 82,0 m | dưới ngưỡng 20 px |
| 111 m/s (400 km/h) | không có nghiệm | cách "bay sau, giữ khoảng cách" không còn dùng được |

Nghĩa là gì: ở tốc độ cao, drone phải giữ khoảng cách rất xa, và mục tiêu trở nên quá nhỏ trong ảnh để nhận diện. Tốc độ cao nhất mà mục tiêu còn ít nhất 20 px là khoảng 14 m/s (51 km/h). Tốc độ cao cần phương án khác, chưa chọn.

</details>

<details>
<summary><b>Chi tiết kỹ thuật 3: nhận diện drone (vision/)</b></summary>

Model `ft_v8n`: YOLOv8n tinh chỉnh trên tập DUT Anti-UAV, 20 vòng huấn luyện, chạy bằng CPU. Chưa đo trên Raspberry Pi 5 hay chip Hailo.

Nhận diện trên ảnh (tập test, nguồn `vision/results/verify/analysis_out.txt`):

| Tập | Ngưỡng | Recall | Báo động giả / 100 ảnh | Nghĩa là gì |
|---|---|---|---|---|
| Tập test đầy đủ | 0,25 | 0,93 | 16,3 | Lạc quan: 67,6% ảnh test có ảnh train gần giống cảnh |
| Tập test đầy đủ | 0,5 | 0,90 | 4,6 | Như trên |
| Tập sạch (684 ảnh, 693 mục tiêu, phần lớn trên 40 px) | 0,25 | 0,92 | 29,8 | Cứ 100 ảnh có khoảng 30 ảnh báo nhầm có drone |
| Tập sạch | 0,5 | 0,87 | 8,6 | Cứ 100 ảnh có khoảng 9 ảnh báo nhầm |

Theo cỡ mục tiêu trên tập sạch: trên 40 px, recall 0,92 (ngưỡng 0,25) và 0,87 (ngưỡng 0,5). Từ 20 đến 40 px, recall 0,93 và 0,89, nhưng chỉ có 28 ảnh, khoảng tin cậy 0,77–0,98. Từ 10 đến 20 px, không có số đáng tin (1 ảnh).

Tiêu chí của kế hoạch: recall ≥ 0,90 ở 20–40 px, và tối đa 20 báo động giả / 100 ảnh. **Chưa đạt**: 0,89 ở ngưỡng 0,5 và 29,8 báo động giả ở ngưỡng 0,25.

Kiểm tra độc lập cổng B1, nhãn tay trên 120 khung (99 có drone, 20 máy bay, 1 trống; gán bằng mắt, một người, trước khi xem kết quả model). Nguồn: `vision/results/verify_b1/c_score.md`, `vision/results/verify_b1/VERIFY_B1.md`.

| Ngưỡng | Bắt được khung có drone | Trong các phát hiện trên khung có drone, tỉ lệ đúng drone | Máy bay bị gọi là drone |
|---|---|---|---|
| 0,25 | 88/99 = 88,9% (khoảng tin cậy 81,2–93,7%) | 89/92 = 96,7% | 20/20 khung |
| 0,5 | 81/99 = 81,8% | 81/81 = 100% | 19/20 khung |
| 0,25, chỉ 65 khung chắc | 64/65 = 98,5% | 64/65 = 98,5% | — |

Nghĩa là gì: ở ngưỡng 0,25, cứ 100 khung có drone thì model thấy drone ở khoảng 89 khung. Trong các khung có drone, 96,7% số khung bao được vẽ là đúng drone. Con số 96,7% **không tính** khung máy bay, nên không được hiểu là model nhận đúng mọi thứ. Gần như mọi khung máy bay đều bị gọi là drone. Khung bỏ sót chủ yếu là drone khoảng 8 px.

Theo dõi ID trên 119 video ghi sẵn (114 video drone, 4 video máy bay, khoảng 10 giây mỗi video, không có nhãn). Ngưỡng 0,25, ByteTrack. Số do người làm, đã được tái lập độc lập. Nguồn: `vision/results/b1/B1_TABLES.md`, `vision/results/b1/B1_REPORT.md`.

| Số đo (114 video drone) | Cắt vùng 320 px quanh mục tiêu | Cả khung hình |
|---|---|---|
| Khung có phát hiện | 92,6% | 91,2% |
| Khung có đúng một mục tiêu được theo dõi | 89,7% | 82,9% |
| Video giữ được một ID suốt đoạn | 38% | 30% |
| Số ID trung bình mỗi video (lý tưởng là 1) | 3,2 | 5,3 |

Nghĩa là gì: model thấy drone ở đa số khung, nhưng cùng một drone thường bị gắn nhiều ID hơn một, nên khi ID đổi, khóa mục tiêu bị rớt. Trên 4 video máy bay (1274 khung), model báo "drone" ở 100% khung (ngưỡng 0,25). Model cũ AI-6 báo 97,7%, model AI-5 báo 1,4%. Tốc độ trên PC khoảng 26 ms mỗi khung (không phải Pi 5).

Hai model `best.pt` cũ có recall 0,38–0,46 trên tập test, không dùng. Không tải trọng số của bên thứ ba.

</details>

<details>
<summary><b>Chi tiết kỹ thuật 4: màn hình lab và Gazebo</b></summary>

Màn hình lab (`lab/`): đọc hình từ file video hoặc webcam, nhận diện và theo dõi ID bằng YOLO, phát trang web có khung và ID. Bấm vào khung để khóa, có nút Khóa và Hủy. Ảnh chụp sau khi khóa: `lab/docs/lab_sau_khoa.png`. Số đo trên PC do chương trình tự báo: 21,5 khung/giây, trễ 64 ms, chưa đo lại. Chưa thử webcam, chưa thử qua mạng, chưa có ảnh từ Pi 5.

Mở ra mạng nội bộ bắt buộc có mật khẩu (từ 8 ký tự), đặt ngoài thư mục git. Sai mật khẩu 5 lần mỗi phút từ một IP thì bị chặn 1 phút. Chưa rà soát bảo mật độc lập.

Khớp gật (`cad/`): thiết kế trong Fusion (`cad/fusion/khop_gat_lab.step`), bản CadQuery dự phòng trong `cad/tilt_mount/`. Không va chạm ở góc −60° đến +60° (kiểm trong mô hình). Kích thước linh kiện chưa đối chiếu vật thật. File in 3D: `STL/de_chu_U.stl`, `STL/gia_kep_camera.stl`. Chưa lắp.

Gazebo (`gazebo/`): Gazebo Harmonic (gz sim 8.15.0) và ardupilot_gazebo chạy trên WSL2 Ubuntu-24.04. Cần đặt biến môi trường `GALLIUM_DRIVER=d3d12` để dùng card đồ họa; nếu không, mô phỏng rơi về CPU. Camera 640×480 khoảng 10 khung/giây. Hệ số thời gian thực 1,00 khi máy nhẹ, 0,7–0,9 khi máy đang tải nặng (nghĩa là mô phỏng chậm hơn thực tế một chút). Chưa làm: hai drone, cửa sổ giao diện thật, đo độ trễ hình. Chi tiết: `gazebo/README.md`.

</details>

<details>
<summary><b>Chi tiết kỹ thuật 5: phần mềm bám (onboard/)</b></summary>

Gói `onboard/dtrack`: ghép các module qua vòng lặp chính, ra lệnh vận tốc cho drone ở chế độ GUIDED qua pymavlink. Hằng số MAVLink đã kiểm đối chiếu mã ArduPilot 4.7.2 (xem `onboard/README.md`).

```mermaid
flowchart LR
    SRC["DetectionSource (app.py)<br/>mô phỏng: simtools/sim_truth_source.py<br/>camera thật + Hailo: CHƯA viết"]
    TRK["tracker.py<br/>SingleTargetTracker (Kalman)"]
    RNG["range_estimator.py<br/>khoảng cách từ kích thước khung bao"]
    SUP["supervisor.py<br/>IDLE / SEARCH / TRACK / COAST / LOST / ABORT"]
    GUI["guidance.py<br/>lệnh vận tốc NED, giới hạn gia tốc"]
    MAV["mavlink_io.py<br/>MavlinkLink (pymavlink)"]
    FC["ArduCopter, chế độ GUIDED<br/>SITL 4.7.2 hoặc Matek H743-WING V3"]
    APP["app.py<br/>vòng lặp chính"]
    LOG["logger.py<br/>CycleLogger, ghi CSV mỗi chu kỳ"]

    SRC -->|"Detection"| TRK
    TRK -->|"TrackState"| SUP
    TRK -.->|"gồm"| RNG
    SUP -.->|"gồm"| GUI
    FC -->|"telemetry: vị trí, tư thế, chế độ"| MAV
    MAV -->|"OwnState"| TRK
    MAV -->|"tình trạng liên kết"| SUP
    SUP -->|"lệnh vận tốc"| MAV
    MAV -->|"send_velocity"| FC
    APP -->|"mỗi chu kỳ"| LOG
```

| Module | File | Vai trò |
|---|---|---|
| Hợp đồng dữ liệu | `onboard/dtrack/types.py` | Khai báo kiểu dữ liệu, hệ tọa độ NED và thân FRD |
| Hình học | `onboard/dtrack/geometry.py` | Quaternion, chiếu tia camera sang NED |
| Bám | `onboard/dtrack/tracker.py` | Bộ lọc Kalman bám một mục tiêu |
| Khoảng cách | `onboard/dtrack/range_estimator.py` | Ước lượng từ kích thước khung bao (camera đơn không đo sâu trực tiếp) |
| Điều khiển | `onboard/dtrack/guidance.py` | Lệnh vận tốc, giới hạn gia tốc |
| Giám sát | `onboard/dtrack/supervisor.py` | Máy trạng thái, dừng, ABORT |
| MAVLink | `onboard/dtrack/mavlink_io.py` | Đọc telemetry, gửi lệnh vận tốc, RTL |
| Nhật ký | `onboard/dtrack/logger.py` | Ghi CSV mỗi chu kỳ |
| Vòng lặp | `onboard/dtrack/app.py` | Ghép các module; `config.py` nạp cấu hình và hồ sơ nghiệm thu |

Hằng số cấu hình chính nằm trong `onboard/dtrack/config.py`. Hồ sơ nghiệm thu: `accept_gimbal_r25`.

</details>

<details>
<summary><b>Chi tiết kỹ thuật 6: cấu trúc thư mục, lệnh chạy, an toàn, giấy phép</b></summary>

Cấu trúc:

```
Drone-Tracking/
├── README.md, HANDOFF.md        tài liệu chính và bản bàn giao
├── .gitignore                   loại out/, *.BIN, __pycache__, dữ liệu và trọng số
├── onboard/                     phần mềm bám (Python): dtrack/, simtools/, docs/, tests/
├── sim/                         chặng 1 cũ, đã ngừng sửa (README.md)
├── lab/                         màn hình lab trên PC (README.md, labview/, tests/, run_demo.sh)
├── vision/                      nhận diện trên video (README.md, scripts/, results/)
├── gazebo/                      Gazebo + ArduPilot (README.md, scripts/, results/)
├── cad/                         khớp gật: tilt_mount/ (CadQuery), fusion/ (Fusion)
├── STL/                         file in 3D
├── gcs/                         bộ cài trạm GCS, PowerShell 5.1 (README.md)
├── bom/                         Excel linh kiện: build_bom.py, bom_data.json
└── .office/                     sổ ghi (ledger.md) và tiến trình (progress/)
```

Lệnh chạy (thay `<repo-wsl>` bằng đường dẫn WSL tới thư mục repo, dạng `/mnt/<ổ>/...`):

```powershell
# Kiểm không còn mô phỏng nào chạy (mã thoát 1 = không có)
wsl -d Ubuntu-24.04 -- pgrep arducopter

# Kiểm phần mềm bám (kỳ vọng theo sổ ghi: 205 passed)
wsl -d Ubuntu-24.04 -- bash -lc 'cd <repo-wsl>/onboard && ~/venv-ardupilot/bin/python -m pytest -q'

# Vòng kín khớp gật, giữ 25 m, bay thẳng 10 m/s, seed 1 (mã thoát 0 = đạt)
wsl -d Ubuntu-24.04 -- bash -lc 'PROFILE=accept_gimbal_r25 SEED=1 SCENARIO=none STRAIGHT=1 bash <repo-wsl>/onboard/simtools/run_closed_loop.sh 10'

# Màn hình lab trên PC với video ghi sẵn (chỉ localhost, mở http://localhost:8080/)
wsl -d Ubuntu-24.04 -- bash <repo-wsl>/lab/run_demo.sh [video] [cổng]

# Kiểm bộ cài GCS (không cần quyền admin)
powershell -ExecutionPolicy Bypass -File gcs\tests\Test-GcsLogic.ps1
```

Lệnh vòng kín trên đã đối chiếu với mã nhưng chưa chạy lại khi viết tài liệu này. Kiểm trước khi dùng. Lô nghiệm thu nhiều lần chạy bằng `onboard/simtools/run_acceptance.sh`.

Lưu ý an toàn:

- Đây là drone tốc độ cao. Phần mềm bám chưa được kiểm trên phần cứng thật. Mọi tham số là đề xuất cho đến khi có bằng chứng bay thử.
- Không bay khi chưa đi hết `gcs/config/checklist-truoc-bay.md`.
- Tham số failsafe `gcs/config/dtrack-failsafe.param` là đề xuất, chưa bay thử. Duyệt từng giá trị trước khi nạp.
- Mọi thao tác ghi lên bộ điều khiển bay (nạp firmware, đổi tham số) cần chủ dự án duyệt riêng.
- Rà soát bảo mật liên kết điều khiển là việc bắt buộc trước buổi bay thật. Hiện chưa làm.
- Bộ cài GCS (`gcs/Install-Gcs.ps1`) chỉ dành cho laptop GCS riêng, cần quyền admin. Không chạy trên máy cá nhân. Đọc `gcs/README.md` trước. Chưa chạy thật lần nào.

Giấy phép và dữ liệu:

- Ultralytics và BoxMOT dùng AGPL-3.0. Cần xem xét trước khi phân phối ra ngoài. Chưa có tư vấn pháp lý.
- DUT Anti-UAV dùng Apache-2.0. Det-Fly dùng MIT trên repo gốc, đang tải, chưa kiểm.
- Dữ liệu và trọng số của bên thứ ba không đưa vào repo.

Điều chưa chốt:

- Khoảng cách giữ chính thức (sau cổng B5).
- Cách bám ở tốc độ cao (trên khoảng 14 m/s khi mục tiêu phanh gấp).
- Tốc độ hành trình 200–250 km/h, sau khi tốc độ tối đa đổi thành 400 km/h.
- Hai chế độ vận hành (bay tay rồi khóa bám bằng công tắc trên tay điều khiển; khóa từ trạm GCS). Chưa có kế hoạch riêng.

Cách làm việc: mỗi bước xong là một commit. Sổ ghi `.office/ledger.md` chỉ ghi thêm. Mỗi kết quả có ngày, mã việc và bằng chứng. Việc chưa kiểm được ghi rõ là "chưa kiểm chứng".

</details>
