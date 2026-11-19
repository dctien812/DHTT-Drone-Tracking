# Drone Tracking: drone tự bám một mục tiêu bay

Dự án làm mô hình thử nghiệm trong phòng lab: một drone 8 inch tự bay theo một mục tiêu bay bằng camera và giữ khoảng cách an toàn. Mục tiêu là máy bay mô hình trainer cánh trên (sải 2,16 m) hoặc một drone. Drone bám bay cao hơn mục tiêu và nhìn xuống. Tự bay bám chỉ làm trong mô phỏng. **Chưa có lần bay thật nào.**

## Tóm tắt cho mọi người

Dự án nhằm làm cho một drone tự nhìn thấy một mục tiêu bay bằng camera, bám theo và giữ khoảng cách an toàn. Đây là mô hình thử nghiệm trong phòng lab, không phải sản phẩm. Trước khi đưa lên trời, mọi thứ được thử trên máy tính: trong mô phỏng (không gian ảo có vật lý), trên các video đã ghi sẵn, và trên một màn hình demo trong phòng lab.

Đến ngày 2026-11-19, giai đoạn 1 đã xong phần làm. Giai đoạn 1 là thêm cho camera một khớp gật (giá đỡ ngẩng hoặc cúi bằng servo) để giữ mục tiêu trong khung hình, và thử trong mô phỏng. Kết quả: ở tốc độ 36 km/h, drone đạt 14/14 lần của "đợt D" (đợt thử thứ tư, 6 lần giữ 25 m và 8 lần giữ 15 m, mỗi cấu hình ba "seed", tức ba số ngẫu nhiên khác nhau). Ở 15 m, khoảng cách nhỏ nhất giữa hai máy bay là 11,16 m (mức an toàn tối thiểu đặt là 6 m). Mục tiêu bay ra khỏi khung hình 0 giây trong các lần có chấm điểm. Các biến thể sau đó (servo chậm, đổi góc nhìn, giữ 20 m, camera "Wide" là camera góc rộng) phần lớn chỉ thử một lần mỗi ô, nên chưa phải kết luận chắc chắn. Chủ dự án đã chấp nhận giai đoạn 1 (sổ ghi dòng 521).

Giai đoạn 2 (tìm lại mục tiêu sau khi mất hình) đã có mã và đã chạy thử trong mô phỏng: khối tìm lại mặc định TẮT, bật bằng hồ sơ `search_plane_r15`. Khi mất hình drone không còn leo cao (lô `srchG3`: leo tối đa 0,00–0,06 m). Kết quả và đặc biệt mục "Rủi ro đã biết" nằm ở phần dưới; giai đoạn 2 chưa được chủ dự án nghiệm thu.

Còn nhiều việc chưa xong. Phần nhận diện trên video phải làm lại, vì mục tiêu đã đổi từ drone sang máy bay trainer hoặc drone. Máy tính nhỏ Raspberry Pi 5 đã gắn camera thật nhưng đang chờ nguồn điện mới. Mọi bước gần bay thật phải được chủ dự án duyệt từng cổng. Mục tiêu thiết kế là tốc độ tối đa 400 km/h, nhưng chưa có bằng chứng nào cho con số này.

## Trạng thái hiện tại (cập nhật 2026-11-19)

Chú thích: **ĐẠT** đã kiểm và đạt tiêu chí. **ĐANG LÀM** có việc đang dở. **CHƯA LÀM** chưa bắt đầu. **CHƯA CHẠY THẬT** chưa thử trên phần cứng thật.

| Phần | Trạng thái | Nghĩa là gì |
|---|---|---|
| Mô phỏng tự bám với khớp gật camera (giai đoạn 1) | ĐẠT trong mô phỏng, chủ dự án đã chấp nhận (sổ ghi dòng 521) | Khớp gật dải 10°–110°. Đợt D ở 10 m/s: đạt 14/14 lần (6 lần giữ 25 m, 8 lần giữ 15 m); ở 15 m khoảng cách nhỏ nhất 11,16 m (sàn chấm 6 m). Camera Wide (số danh định): 5 trên 5 lần đạt. Phần lớn ô chỉ thử một lần |
| Tự leo cao khi mất hình | ĐÃ SỬA trong mô phỏng | Lô `srchG3`: leo tối đa khi mù 0,00–0,06 m. Pha leo cao chủ động (tắt mặc định) đã kích hoạt 1 lần ở lô bù `srchG4`, chưa đủ ca |
| Tìm lại mục tiêu khi mất (giai đoạn 2) | ĐẠT MỘT PHẦN trong mô phỏng, có rủi ro đã biết | Mã có, mặc định TẮT. Lô `srchG3` (26 lần): tìm lại 4/4 bay thẳng (5/5 sau lô bù `srchG4`), 5/5 bổ nhào, RTL ở 20,03 s khi mất 25 s. Còn lỗ hổng, xem mục "Giai đoạn 2: tìm lại mục tiêu" và "Rủi ro đã biết" |
| Nhận diện mục tiêu trên video ghi sẵn (cổng B1) | PHẢI LÀM LẠI | Kết quả cũ chấm cho "drone", nay mục tiêu là máy bay trainer hoặc drone. Kế hoạch mới chưa được duyệt. Dữ liệu Det-Fly coi là đủ (7.635 cặp ảnh-nhãn khớp). Phần nhận diện máy bay (B1a, `vision/`) đang làm dở: xem `vision/README.md` hoặc báo cáo B1a khi có |
| Demo màn hình lab trên PC (video ghi sẵn) | ĐẠT | Hiện khung hình, khóa mục tiêu bằng nút bấm. Không gửi lệnh tới drone hay bộ điều khiển bay nào |
| Demo trên Raspberry Pi 5 với camera thật | ĐANG LÀM, chờ nguồn | Pi 5 đã cài hệ điều hành, camera Wide đã gắn và chụp thử được. Chạy màn hình lab thì Pi bị sụt nguồn, chưa có số đo. Chờ nguồn mới |
| Mô phỏng Gazebo | ĐẠT với một drone; CHƯA LÀM với hai drone | Camera ảo chạy khoảng 10 khung hình mỗi giây |
| Báo cáo hình cho mô phỏng | ĐẠT (hình tĩnh) | Hình tĩnh đã duyệt. Video chỉ làm khi chủ dự án duyệt riêng |
| Bay thật | CHƯA CHẠY THẬT | Chưa bay lần nào. Mọi thao tác ghi lên bộ điều khiển bay cần chủ dự án duyệt riêng |

## Việc kế tiếp và đang chờ

**Đang chờ chủ dự án:**

1. (Đã xong) Giai đoạn 1 và các mặc định đề nghị (giữ 15 m, đường ngắm hướng xuống 12°, khớp gật 10°–110°, camera Wide) đã được chủ dự án chấp nhận, sổ ghi dòng 521.
2. Xem kết quả giai đoạn 2 và các rủi ro đã biết (mục "Rủi ro đã biết"), quyết định có sửa rủi ro (a) và (c) trước không.
3. Duyệt kế hoạch làm lại cổng B1 (nhận diện theo mục tiêu mới). Cần thêm ảnh hoặc video máy bay: bộ MMFW-UAV (140 GB, chủ dự án tự tải khi ngồi máy) hoặc video tự quay.
4. Duyệt làm video báo cáo (hình tĩnh đã duyệt).
5. Nguồn điện mới cho Raspberry Pi 5.
6. Linh kiện còn thiếu: servo MG90S, bo PCA9685, dây nối, nguồn 5 V riêng cho servo. Tình trạng từng món xem trong Excel `bom/`.
7. Duyệt riêng mọi thao tác ghi lên bộ điều khiển bay (nạp firmware, đổi tham số).

**Việc kế tiếp, theo thứ tự:**

1. Giai đoạn 2, phần còn lại: xử lý đợt COAST thứ hai cuối bài (rủi ro a), sửa dải quét gimbal ở pha 1 vì bật tìm lại lấy lại hình chậm hơn tắt ở ca bổ nhào (rủi ro c), thêm ca cho pha leo cao và thêm seed bay thẳng (rủi ro d).
2. Làm lại cổng B1 theo mục tiêu mới, trên camera Wide, sau khi kế hoạch được duyệt.
3. Đổi camera mặc định trong mã sang Wide và hiệu chuẩn trên Pi (việc riêng, chưa có kế hoạch).
4. Rà soát độc lập phần mã bám và bảo mật trang lab trước khi mở ra mạng.
5. Demo lab, theo các bước dưới đây.

| Bước | Việc | Trạng thái | Điều kiện để bắt đầu |
|---|---|---|---|
| S1 | Cổng B1 (theo dõi và nhận diện trên video) | Phải làm lại theo mục tiêu mới | Kế hoạch mới được duyệt |
| S2 | Màn hình web hiện hình, khóa, hủy (chạy trên PC) | Xong trên PC. Chưa thử qua mạng | Không còn |
| S3 | Đo tốc độ trên CPU Pi 5, xuất model dạng NCNN | Chưa làm | Pi 5 có nguồn đủ |
| S4 | Mốc L0: chạy màn hình trên Pi 5 với camera thật; hiệu chuẩn camera bằng bàn cờ để tính góc | Đang dở: camera đã gắn, chưa có số đo vì sụt nguồn | Nguồn Pi 5 mới |
| S5 | Xác minh bộ điều khiển bay ở chế độ chỉ đọc, chưa có bằng chứng bộ này đã nạp ArduCopter | Chưa làm | Bộ điều khiển nối được với máy tính. Thao tác ghi cần duyệt riêng |
| S6 | Cổng B3: nối bộ điều khiển bay, chỉ đọc dữ liệu | Chưa làm | S5 xong và cổng B3 được duyệt |
| S7 | Khớp gật một trục in 3D, điều khiển bằng servo | Theo sổ ngày 11-17: thiết kế xong, đang in. Chưa có tin mới | Servo, bo điều khiển, nguồn 5 V về |
| S8 | Mốc L1: thêm khớp gật do Pi điều khiển, đọc bộ điều khiển bay ở chế độ chỉ đọc, công tắc trên tay điều khiển | Chưa làm | S4, S5, S7 xong |

Các cổng duyệt B1–B6: chủ dự án duyệt từng cổng trước khi sang bước sau.

| Cổng | Nội dung bằng lời | Trạng thái |
|---|---|---|
| B1 | Nhận diện và theo dõi mục tiêu (máy bay trainer hoặc drone) trên video ghi sẵn | Phải làm lại theo mục tiêu mới. Kế hoạch chưa duyệt |
| B2 | Máy tính AI và camera gắn trên bàn | Chưa. Pi 5 và camera Wide đã có, camera đã gắn lên Pi; AI HAT+ chưa có; Pi chờ nguồn mới |
| B3 | Nối bộ điều khiển bay, chỉ đọc dữ liệu | Chưa |
| B4 | Mô phỏng và an toàn: tự bám, giữ khoảng cách | Giai đoạn 1 (khớp gật) đạt trong mô phỏng, chủ dự án đã chấp nhận. Giai đoạn 2 (tìm lại) chạy thử trong mô phỏng, còn rủi ro đã biết |
| B5 | Thử tích hợp trên mặt đất: chốt camera và khoảng cách giữ | Chưa. Đề nghị đang dùng: camera Wide, giữ 15 m |
| B6 | Bay quan sát có kiểm soát | Chưa. Chỉ sau B1–B5 đạt và được duyệt |

## Giai đoạn 2: tìm lại mục tiêu sau khi mất hình (cập nhật 2026-11-19)

Tất cả số dưới đây là mô phỏng SITL, chưa bay thật, chưa chạy trên Raspberry Pi.

**Hành vi hiện tại.** Khối tìm lại nằm ở `onboard/dtrack/search.py`, cấu hình `SearchConfig` trong `onboard/dtrack/config.py`. Mặc định TẮT (`search.enabled` là `False`, khi đó không có đợt tìm, RTL sau `supervisor.lost_rtl_s` = 10 s như cũ; lệnh bay lúc COAST và bộ bám đã đổi theo C1/C2, nên không hoàn toàn giống giai đoạn 1). Bật bằng hồ sơ `search_plane_r15` (giữ 15 m, khớp gật kiểu mới `gimbal.enabled`, camera Wide danh định fx 933, 2304×1296). Một "đợt" tìm kéo dài `search.total_s` = 20 s, tính từ lần COAST đầu:

| Pha | Việc drone làm |
|---|---|
| 0 (tối đa 4 s, `supervisor.coast_follow_s`) | Bay tiếp theo dự đoán vận tốc mục tiêu nhớ được |
| 1 | Treo tại chỗ (tốc độ ngang ≤ 0,3 m/s). Khớp gật quét 60°/s (`scan_rate_dps`) trong dải 10°–110°; yaw quét ±45° (`yaw_amp_deg`) quanh hướng lúc vào pha 1. Khi tracker báo TRACK lại thì khớp ngừng quét và bám mục tiêu |
| 2 (leo cao) | Mặc định TẮT (`climb_m` = 0). Khi bật, leo thêm `climb_m` từ giây `climb_start_s` |
| Hết 20 s | Yêu cầu RTL một lần |

"Tìm lại" nghĩa là TRACK liên tục từ 1,0 s trở lên (`reacquire_hold_s`); lúc đó đợt đóng và quyền điều khiển trả về luật bám bình thường. Khi mất hình drone không leo cao (C1). Cơ chế "giả định mục tiêu hãm" khi bay mù vẫn còn trong mã nhưng TẮT trong hồ sơ (`blind_floor_m` = 0, `blind_v_cap_mps` = 0) theo quyết định của chủ dự án; hệ quả là rủi ro (b) bên dưới.

**Cách chạy một ca** (WSL, mô phỏng thật tốn khoảng 2,5–4,5 phút mỗi lần; thêm `DRY_RUN=1` để chỉ in dòng lệnh rồi thoát, không khởi động gì). Biến riêng của ca tìm lại, chỉ đi với `SCENARIO=blackout`: `EVENT_AT` (giây kể từ `t_ws`, lúc bắt đầu cửa sổ đo khi khoảng cách đạt mức đặt; mặc định 40), `BLACKOUT_S` (độ dài mất hình, mặc định 3), `POST_S` (giây quan sát sau khi hết mất hình, mặc định 15), `BLACKOUT_BRAKE` (m/s², mục tiêu hãm đúng lúc mất hình), `MEASURE_ONLY=1` (tiêu chí khoảng cách chỉ in để đo, không chấm). `PROFILE` và `CONFIG` loại trừ nhau.

```bash
# mục tiêu bay thẳng, mất hình 8 s, seed 1 (hồ sơ bật tìm lại)
PROFILE=search_plane_r15 SEED=1 SCENARIO=blackout BLACKOUT_S=8 bash <repo-wsl>/onboard/simtools/run_closed_loop.sh 10

# mất hình 25 s: kỳ vọng không tìm lại, RTL ở khoảng 20 s
PROFILE=search_plane_r15 SEED=1 SCENARIO=blackout BLACKOUT_S=25 bash <repo-wsl>/onboard/simtools/run_closed_loop.sh 10

# mất hình 14 s, cấu hình có pha leo 10 m (file JSON, không phải hồ sơ trong PROFILES; EVENT_AT=30 như lô srchG4)
CONFIG=<repo-wsl>/onboard/simtools/configs/search_plane_r15_climb10.json SEED=1 SCENARIO=blackout BLACKOUT_S=14 EVENT_AT=30 bash <repo-wsl>/onboard/simtools/run_closed_loop.sh 10

# mục tiêu hãm 3 m/s² đúng lúc mất hình, chỉ đo
PROFILE=search_plane_r15 SEED=1 SCENARIO=blackout BLACKOUT_BRAKE=3 MEASURE_ONLY=1 bash <repo-wsl>/onboard/simtools/run_closed_loop.sh 10
```

Ba dòng lệnh này đã được in ra bằng `DRY_RUN=1` và khớp `run_closed_loop.sh`; chưa chạy thật khi viết tài liệu, và chưa xác nhận là đúng từng dòng lệnh của lô `srchG3`. Ca bổ nhào lúc mất hình dùng thêm `DIVE_DEG=25 ALT=70`; lô `srchG3` còn đặt `EVENT_AT=30`. Hồ sơ tương đương dạng file: `onboard/simtools/configs/search_plane_r15.json` (bản tắt tìm lại để đối chứng: `search_plane_r15_off.json`).

**Kết quả lô `srchG3`** (26 lần, 2026-11-19; bảng gốc `onboard/simtools/out/_report_srchG3/srchG3_table.md`, thư mục `out/` không đưa lên GitHub):

| Ca | Kết quả |
|---|---|
| Mục tiêu bay thẳng, mất hình 8 s, bật tìm lại | Tìm lại 5/5 seed (4 seed ở `srchG3`, thêm seed 1 ở lô bù `srchG4` lúc 8,03 s), sau 7,97–8,13 s. Cả 5 lần đều bắt lại đúng lúc hình trở lại, nên chưa chứng minh việc quét tự tìm ra mục tiêu |
| Mất hình 14 s, cấu hình leo `search_plane_r15_climb10.json`, seed 1 (`srchG4`) | Pha leo đã kích hoạt: pha leo vào khoảng 10,2 s sau lúc mất hình, độ cao tăng rõ sau khoảng 11,2 s; leo 5,20 m tính từ độ cao thấp nhất trong cửa sổ mất hình (4,86 m tính từ lúc bắt đầu mất hình) tới lúc tìm lại (mức cho phép 10 + 1 m); tìm lại sau 13,97 s, không RTL; sau khi đóng đợt độ cao còn lên tới +9,15 m (khoảng 17 s sau lúc mất hình), vẫn trong mức 11 m, nguyên nhân chưa điều tra; d3 nhỏ nhất trong cửa sổ mất hình 15,59 m, cả chuyến 15,31 m (tính từ lúc bắt đầu bám). Mới 1 lần (kế hoạch: 10 m × 3 seed, 20 m × 1 seed) |
| Bổ nhào 25°, bật tìm lại | Tìm lại 5/5 seed, sau 10,97–11,07 s |
| Mất hình 25 s | Không tìm lại; RTL ở 20,03 s |
| Khoảng cách 3D nhỏ nhất trong cửa sổ mất hình, mục tiêu bay đều | 15,13–15,89 m (mức yêu cầu 8 m) |
| Leo tối đa khi mù | 0,00–0,06 m (ở các ca có đo) |
| Mục tiêu hãm lúc mất hình 1,5 / 3 / 8 m/s² (chỉ đo) | Gần nhất cả chuyến 4,23 / 3,24 / 3,38 m (trong cửa sổ mất hình 4,25 / 3,24 / 3,40 m). Ca 1,5 m/s² tìm lại ở 17,90 s |
| Ba ô bám không sự kiện (lần 13–15 của `srchG3`) | Đạt: khoảng cách nhỏ nhất 11,28 / 11,93 / 11,40 m, ra khung 0 s; mỗi ô 1 seed |
| Lô bù `srchG4`: ba ô bám, seed 2 và 3 | Đạt cả 6 lần: bổ nhào 15° 11,59 / 12,22 m; bổ nhào 25° 11,10 / 11,24 m; mục tiêu hãm 1,5 m/s² (mất hình 3 s) 13,12 / 11,56 m; ra khung 0 s; TRACK 100 / 100 / 100 / 100 / 97,4 / 97,5%. Cùng lô cũ: mỗi ô 3 seed, tiêu chí C9 đạt |

7 lần công cụ báo không đạt, 07 và 08 đều kết luận không lần nào do khối tìm lại: 4 lần do sàn 6 m áp cho cả chuyến (xem rủi ro a), 3 lần do cổng "TRACK ≥ 90%" với nguồn phát hiện theo cụm (86,2–88,7%; ô này theo kế hoạch chỉ báo cáo, không dùng làm cổng).

### Rủi ro đã biết

Viết thẳng, chưa sửa trừ khi ghi khác:

- **(a) Áp sát cuối bài.** Khi mục tiêu dừng ở cuối bài, drone vào một đợt COAST thứ hai và áp sát 3,89–7,87 m ở 8/13 lần (mẫu số = tất cả lần bay thẳng có mục tiêu dừng cuối bài, không tính ca mất hình 25 s và ca hãm 3 / 8 m/s²: `srchG3` lần 1–5, 15, 23–26 và `srchG4` lần 2, 7, 8; 8 lần dưới 8 m là `srchG3` lần 1–5, 24, 26 và `srchG4` lần 2, với 5,21 m ngoài cửa sổ mất hình, trong cửa sổ 15,72 m; lúc gần nhất lần này drone cao hơn mục tiêu 4,00 m, góc nâng 50,1°), kể cả khi tắt tìm lại (nên không phải lỗi của khối tìm lại). Lúc gần nhất drone ở TRÊN mục tiêu 3,3–4,2 m, góc nâng 27–75°; "gần như trên đầu" chỉ hợp 3 lần trên 65° (66,7–75°). Bám bình thường khoảng 11–13° ở ba lần được tính lại (báo cáo đo ghi 11–19° cho lần 6–11, 13–19). Cùng lúc đó mục tiêu ra khỏi khung 1,56–3,88 s (lần 1, 5, 24, 26) và khoảng cách lớn nhất tới 57 m. Chưa sửa. Đây là nguyên nhân 5 trong 8 lần công cụ báo không đạt của hai lô `srchG3` + `srchG4` (riêng `srchG3`: 4 trong 7).
- **(b) Mục tiêu hãm khi drone mù** (1,5 / 3 / 8 m/s², chỉ đo, không tính đạt hay không): gần nhất cả chuyến 4,23 / 3,24 / 3,38 m, drone ở trên 3,2–3,3 m (góc nâng 51,6° / 85,7° / 78,5°). Ca 1,5 m/s² tìm lại ở 17,90 s; ca 3 và 8 m/s² không tìm lại, RTL ở 20 s. Đây là cái giá của việc tắt cơ chế giả định mục tiêu hãm (chủ dự án chấp nhận vì bật thì drone tụt lại xa khi hình chập chờn); thiết kế còn ghi thêm rủi ro mục tiêu phanh rồi quay đầu lao lại lúc drone mù (bản cài thử đo khoảng 1,0 m), không có mô hình nào bao được.
- **(c) Ca bổ nhào, bật tìm lại lấy lại hình CHẬM hơn tắt khoảng 3 s** (≈ 11,0 s so với ≈ 8,0 s; 5 seed bật, 1 seed tắt, cùng cách đo). Nguyên nhân đã điều tra xong: khi bật, pha 1 quét góc gimbal cả dải 10°–110° (chu kỳ 3,33 s). Mục tiêu bổ nhào nằm thấp (góc ngẩng khoảng −42° lúc 8 s) nên chỉ lọt khung khi góc gimbal từ khoảng 97–100° trở lên, tức 0,2–0,3 s mỗi chu kỳ. Ở cả 5 seed, lượt quét qua vùng đó kết thúc đúng lúc hết mất hình (8,0 s), nên phải chờ lượt sau (khoảng 11,0 s). Khi tắt, gimbal giữ 104°–110° nên thấy lại ngay. Bay thẳng không bị vì mục tiêu ở khoảng −4,5°, nhìn thấy được nửa chu kỳ. Con số 3 s là do trùng pha với độ dài mất hình 8 s; độ trễ thật nằm trong 0–3,3 s tùy pha, chưa đo. Chưa sửa; hướng sửa dự kiến: quét quanh góc dự đoán (khoảng ±25°) hoặc nâng `scan_lo_deg`. Lô này cũng chưa chứng minh bật tìm lại tốt hơn tắt, vì mục tiêu tự hiện lại sau khi hết mất hình.
- **(d) Bằng chứng còn thiếu.** C8 (pha leo cao) mới có 1 lần leo thật, đạt (5,20 m từ độ cao thấp nhất trong cửa sổ mất hình, mức cho phép 11 m; sau khi đóng đợt độ cao còn lên tới +9,15 m, chưa điều tra), chưa đủ so với kế hoạch (10 m × 3 seed, 20 m × 1 seed). C5 đạt 5/5 seed bay thẳng, nhưng cả 5 lần đều bắt lại đúng lúc hình trở lại nên chưa chứng minh quét tự tìm ra mục tiêu. C9 đạt (3 seed mỗi ô). C2 (phát hiện giả khi COAST không kéo khớp nhảy) vẫn chưa chứng minh trực tiếp.
- **(e) Bộ bám** mất thời gian TRACK khi có vật gây nhiễu độ tin cậy cao ở mọi khung: 20–29 điểm phần trăm theo 07, khoảng 42–46 điểm theo 08 (còn 327–350/600 khung TRACK); hai cách đo chưa thống nhất. Để sau.
- **(f) Nhiễu đo gấp đôi:** có 2 lần khoảng cách khoảng 50 m ở đoạn giảm tốc cuối, chưa rõ nguyên nhân.
- **(g) Tất cả là mô phỏng.** Chưa bay thật, chưa chạy trên Raspberry Pi. Nguồn phát hiện là tổng hợp (có tham số giả định), không phải detector thật.

## Giải thích thuật ngữ

| Từ | Nghĩa |
|---|---|
| Quad 8 inch | Drone bốn động cơ, dùng cánh quạt đường kính 8 inch (khoảng 20 cm) |
| Bộ điều khiển bay (FC) | "Bộ não" của drone, điều khiển động cơ. Dự án dùng Matek H743-WING V3 chạy phần mềm ArduCopter |
| Mô phỏng SITL | Chạy phần mềm bay của drone trên máy tính, không cần phần cứng |
| Gazebo | Phần mềm mô phỏng thế giới 3D có vật lý và camera ảo |
| Máy đồng hành | Máy tính nhỏ gắn trên drone, xử lý hình ảnh. Dự án dùng Raspberry Pi 5 |
| Mục tiêu | Vật bay mà drone bám theo: máy bay mô hình trainer cánh trên (sải 2,16 m) hoặc một drone |
| Nhận diện | Tìm mục tiêu trong từng khung hình. Kết quả là một khung chữ nhật bao quanh mục tiêu |
| Khung hình | Một ảnh trong video. Video thường có khoảng 30 khung mỗi giây |
| ID (theo dõi) | Số gắn cho một vật qua nhiều khung hình. Đổi ID nghĩa là hệ thống coi như mất mục tiêu rồi gặp lại vật khác |
| Ngưỡng tin cậy (0,25, 0,5) | Mức chắc chắn tối thiểu để model báo có drone. Ngưỡng thấp bắt được nhiều hơn nhưng báo nhầm nhiều hơn |
| Recall (tỉ lệ bắt được) | Trong các khung có drone, bao nhiêu khung model thấy drone |
| Báo động giả | Model báo có drone khi không có. Đếm theo số lần trên 100 ảnh |
| px (điểm ảnh) | Đơn vị đo kích thước trong ảnh. Drone 10 px là rất nhỏ |
| Khớp gật (gimbal một trục) | Giá đỡ camera ngẩng hoặc cúi bằng servo, để giữ mục tiêu trong khung hình. Dải góc 10°–110° so với trục lực đẩy của drone |
| Servo | Động cơ nhỏ quay theo góc. PCA9685 là bo mạch điều khiển nhiều servo |
| Khoảng cách giữ | Khoảng cách drone cố giữ với mục tiêu. Chuẩn hiện nay là 15 m |
| Sàn chấm | Khoảng cách tối thiểu giữa hai máy bay mà một lần thử phải luôn giữ. Hiện là 6 m |
| Ra khung | Mục tiêu nằm ngoài khung hình camera. Tiêu chí: mỗi pha không quá 2,0 giây |
| Camera Wide | Raspberry Pi Camera Module 3 Wide, góc nhìn rộng. Là camera bay đã chốt (thay Global Shutter) |
| Mô phỏng danh định | Thông số lấy từ số của nhà sản xuất, chưa đo trên máy thật |
| Seed | Số ngẫu nhiên khởi đầu của một lần mô phỏng. Đổi seed là có lần thử khác |
| Giai đoạn 1, giai đoạn 2 | Giai đoạn 1: khớp gật camera trong mô phỏng (đã xong phần làm). Giai đoạn 2: tìm lại mục tiêu khi mất (đã có mã và lô mô phỏng, còn rủi ro đã biết) |
| Mất hình | Hệ thống không thấy mục tiêu trong một lúc |
| COAST | Trạng thái bay tiếp theo vận tốc mục tiêu nhớ được, ngay sau khi mất hình, tối đa 4 s |
| RTL | Lệnh cho drone tự quay về điểm cất cánh |
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
| Khoảng cách giữ | 15 m (lùi 10 m, lùi khẩn 8 m, sàn chấm 6 m) | Đã đo trong mô phỏng ở 10 m/s. Chốt chính thức ở cổng B5 |
| Khớp gật camera | Một trục, dải 10°–110°, cất cánh ở 90° | Mã đã có, đã thử trong mô phỏng. Chưa đo trên phần cứng; ở 110° camera có thể bị thân hoặc càng che |

Phần cứng:

| Hạng mục | Lựa chọn | Trạng thái |
|---|---|---|
| Bộ điều khiển bay | Matek H743-WING V3 | Đã có |
| Máy đồng hành | Raspberry Pi 5 8 GB, có tản nhiệt | Đã có |
| Tăng tốc AI | AI HAT+ (Hailo-8, 26 TOPS) | Chưa có. Lab chạy nhận diện bằng CPU của Pi |
| Camera bay | Raspberry Pi Camera Module 3 Wide (chốt 2026-11-19; bỏ Global Shutter vì không mua được) | Đã có, đã gắn lên Pi 5, chụp thử được. Thông số Wide trong mô phỏng là danh định (fx 933 px ở 2304×1296), chưa hiệu chuẩn. Mặc định trong mã vẫn là camera cũ (fx 1739 px, 1456×1088, lens 6 mm) |
| Camera lab | Raspberry Pi Camera Module 3 Wide (cùng loại camera bay) | Đã có, đã gắn lên Pi 5 |
| Khung | Apex HD 8 inch làm đế, vỏ in 3D kiểu tên lửa | Dự kiến, số liệu khung chưa xác minh |
| Động cơ | Động cơ 3110 không đủ (khoảng 0,9 kW mỗi cái). Ứng viên 3115, 3120, 3220 | Chưa chốt, sau chặng 3 |
| Radio (lab) | Radiomaster Pocket + RX XR4 | Đã có. Trong lab chỉ đọc kênh RC |
| Sạc pin | ToolkitRC M8D | Đã có |
| Trạm GCS | Mission Planner trên laptop Windows 11 | Chưa chọn máy |

Nguồn: sổ ghi `.office/ledger.md` (2026-11-17). Mua sắm chi tiết xem Excel `bom/`.

</details>

<details>
<summary><b>Chi tiết kỹ thuật 2: mô phỏng</b></summary>

**Giai đoạn 1: khớp gật camera chủ động (bước 7, cập nhật 2026-11-19)**

Kịch bản: mục tiêu bay thẳng ở 10 m/s, tăng tốc lúc đầu, rồi cắm xuống (15° hoặc 25°), cuối chuyến giảm tốc. Mục tiêu là máy bay trainer cánh trên (sải 2,16 m, thân 1,50 m, cao khoảng 0,65 m). Drone bám bay cao hơn, đường ngắm hướng xuống 12°, giữ 15 m (hồ sơ `accept_plane_r15`: lùi 10 m, lùi khẩn 8 m, sàn chấm 6 m). Khớp gật chạy một trục, dải 10°–110°, cất cánh ở 90°. Giá trị servo trong mô phỏng là giả định (300°/s, trễ 0,05 s, chết 0,02 s, bước 0,1°).

Tiêu chí chính của mỗi lần chạy: khoảng cách thật không dưới sàn chấm; mục tiêu ra khỏi khung hình không quá 2,0 giây mỗi pha (pha cắm, bay bằng, giảm tốc cuối); khoảng cách xa nhất không quá 40 m; sai số giữ cách trung bình dưới 3 m; bám ít nhất 90% thời gian.

Mã khớp gật nằm ở `onboard/dtrack/gimbal.py`, `onboard/dtrack/gimbal_control.py`, `onboard/dtrack/elev_ramp.py`, `onboard/simtools/servo_model.py`. Mỗi lần chạy ghi thêm `gimbal.csv` (góc khớp theo thời gian); bộ chấm `onboard/simtools/analyze_closed_loop.py` đọc góc khớp thật từ file này, thiếu file thì lần chạy bị chấm FAIL.

Kết quả (nguồn: các bảng `onboard/simtools/out/_summary_gimbalD_all.txt`, `_summary_gimbalE_all.txt`, `_summary_gimbalF_all.txt`; thư mục kết quả không đưa lên GitHub):

| Đợt | Cấu hình | Kết quả | Số chính |
|---|---|---|---|
| D | Camera hẹp (fx 1739), góc khớp 10°–110°, giữ 25 m và 15 m, cắm 15° và 25°, 3 seed, thêm mất hình (blackout) và người điều khiển giành quyền (disengage) | 14/14 ĐẠT | Ra khung 0,00 s ở mọi pha có chấm. Khoảng cách nhỏ nhất 11,16 m khi giữ 15 m (sàn 6 m) và 20,83 m khi giữ 25 m (sàn 8 m) |
| E | Biến thể, mỗi ô 1 seed: khớp đứng yên (đối chứng) | CHƯA ĐẠT, đúng yêu cầu | Ra khung 4,26 s ở pha cắm. Bản chủ động cùng kịch bản: 0 s |
| E | Servo chậm gấp 2; góc đường ngắm +4° và −15°; giữ 20 m; 20 m/s (giữ 25 m) | 5/5 ĐẠT | Ra khung 0 s |
| E | Giữ 12 m (hai kịch bản) | CHƯA ĐẠT, sát ngưỡng | Ra khung 2,14 s và 2,04 s ở giảm tốc cuối (ngưỡng 2,0 s). Nên 15 m là mức thấp nhất đạt đủ |
| F | Camera Wide danh định (fx 933, 2304×1296), giữ 15 m | 5/5 ĐẠT | Ra khung 0 s. Khoảng cách nhỏ nhất 11,27 m. Mục tiêu cách mép khung 28–33° (camera hẹp: 9–16°) |

Nguyên nhân hai đợt trước (B, C) chưa đạt: giới hạn cũ của khớp là 90°. Lúc giảm tốc cuối drone ngẩng mũi, cần góc khớp trên 90° (ví dụ 109,6°) mà khớp bị kẹt ở 90°, nên mục tiêu rời khung hình 7–12 giây. Đã chứng minh bằng thử đổi giới hạn trong tính toán: cho phép ≥ 110° thì ra khung 0 s ở 5 trên 6 lần. Chủ dự án quyết nới dải thành 10°–110°. Đợt A và B: 6 lần, đều chưa đạt ở giảm tốc cuối. Đợt C: 2 trên 14 lần đạt.

Lưu ý khi đọc: lô "mốc" bước 1b (hồ sơ `accept_plane_r25`) dùng mô hình khớp kiểu cũ (camera ngước 15°, ổn định lý tưởng), không phải camera cố định. Đối chứng "không có khớp chủ động" đúng nghĩa là các lần khớp đứng yên.

Chưa kiểm chứng: thông số Wide là danh định, chưa hiệu chuẩn; nhiễu pixel mô phỏng chưa đổi theo Wide; sai số ước lượng khoảng cách không tăng như dự đoán, chưa giải thích; các biến thể đợt E, F chỉ một lần mỗi ô.

Hình kết quả: công cụ `onboard/simtools/report_run.py` đọc log và vẽ quỹ đạo, khoảng cách, vị trí mục tiêu trong khung, góc khớp và bảng PASS/FAIL. Lệnh (trong WSL, từ thư mục `onboard`): `~/venv-ardupilot/bin/python -m simtools.report_run <thư mục lần chạy>... --batch-html <file.html>`. Hình các đợt đã dựng ở `onboard/simtools/out/_report/index.html` (không đưa lên git). Hình tĩnh đã duyệt; video chờ duyệt riêng.

Tồn đọng của mô phỏng ở thời điểm cuối giai đoạn 1 (cập nhật giai đoạn 2: xem mục "Giai đoạn 2" ở trên): (1) khi mất hình, drone tự leo cao ngoài ý muốn (do vận tốc đứng nhớ bị nhiễm, giữ mục tiêu giữa khung theo đường ngắm ngoại suy, và lùi dọc đường ngắm); đã sửa ở giai đoạn 2, lô `srchG3` đo leo tối đa 0,00–0,06 m; (2) phát hiện giả lọt vào bộ bám lúc mất hình (`onboard/dtrack/tracker.py:252-272`), từng kéo khớp về 10° trong đợt B; tiêu chí C2 chưa chứng minh trực tiếp ở giai đoạn 2; (3) khoảng cách xa nhất lên 44,7–51,6 m ở pha tăng tốc của hồ sơ giữ 25 m (ngoài cửa sổ chấm 40 m).

**Kết quả cũ (2026-11-17, trước khi có khớp chủ động, giữ 25 m làm chuẩn)**

Tiêu chí lúc đó: sai số trung bình dưới 3 m trong cửa sổ đo 120 giây; khoảng cách thật không dưới 8 m suốt chuyến; bám ít nhất 90% thời gian. Thêm: mất hình 3 giây và giành quyền (ngừng lệnh dưới 0,1 s). Mỗi ô một lần thử, seed 1 (nguồn: file `result.txt` của từng lần chạy):

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

Số lần kiểm: `pytest` của `onboard/` cho 1368 passed, 1 xfailed (sau khi thêm khối tìm lại, sổ ghi ngày 2026-11-19; xfailed là ca mục tiêu phanh rồi quay đầu lao lại lúc drone mù, xem rủi ro b; số 810 là của cuối giai đoạn 1). Lô nghiệm thu 3 seed × 2 lần theo kế hoạch cũ (B6b) chưa chạy; đợt D chạy 3 seed × 1 lần.

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

**Lưu ý 2026-11-19:** các số dưới đây chấm cho mục tiêu "drone" và là kết quả lịch sử. Mục tiêu nay là máy bay trainer cánh trên hoặc drone, camera bay là Wide, nên cổng B1 phải làm lại. Kế hoạch làm lại (bản nháp bị phản biện) chưa được duyệt: nhận diện sẽ chạy trên vùng cắt quanh mục tiêu từ khung độ phân giải cao, tách drone và máy bay. Dữ liệu Det-Fly trong `vision/data/det-fly/` coi là đủ: 7.635 cặp ảnh-nhãn khớp tên (10.339 ảnh, 10.001 nhãn). Chưa có bộ ảnh máy bay mô hình đã xác minh; bộ MMFW-UAV chủ dự án tự tải, giấy phép và dung lượng thật chưa kiểm. Lần huấn luyện trước (V2: DUT + Det-Fly + ảnh âm COCO) đã thất bại một lần, không lặp lại nguyên công thức.

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

Màn hình lab (`lab/`): đọc hình từ file video hoặc webcam, nhận diện và theo dõi ID bằng YOLO, phát trang web có khung và ID. Bấm vào khung để khóa, có nút Khóa và Hủy. Ảnh chụp sau khi khóa: `lab/docs/lab_sau_khoa.png`. Số đo trên PC do chương trình tự báo: 21,5 khung/giây, trễ 64 ms, chưa đo lại. Chưa thử webcam, chưa thử qua mạng, chưa có ảnh trang lab chạy trên Pi 5.

Mở ra mạng nội bộ bắt buộc có mật khẩu (từ 12 ký tự), đặt ngoài thư mục git. Sai mật khẩu 5 lần mỗi phút từ một IP thì bị chặn 1 phút. Chưa rà soát bảo mật độc lập.

Khớp gật (`cad/`): thiết kế trong Fusion (`cad/fusion/khop_gat_lab.step`), bản CadQuery dự phòng trong `cad/tilt_mount/`. Không va chạm ở góc −60° đến +60° (kiểm trong mô hình). Kích thước linh kiện chưa đối chiếu vật thật. File in 3D: `STL/de_chu_U.stl`, `STL/gia_kep_camera.stl`. Chưa lắp. Lưu ý: dải 10°–110° của khớp gật trong mô phỏng (đo so với trục lực đẩy) chưa được đối chiếu với thiết kế cơ khí này; ở 110° camera có thể bị thân hoặc càng che.

Raspberry Pi 5 (lab): đã cài hệ điều hành, SSH được, camera Module 3 Wide đã gắn và chụp thử được (1536×864; chế độ 2304×1296 cho tối đa 56 khung/giây theo danh sách chế độ của camera; chưa đo tốc độ thật). Chạy màn hình lab với nguồn `picamera2` thì trang trả lời sau 4 giây rồi Pi sụt nguồn; chưa có số đo. Chưa có servo. Ghi chú về Pi: `pi/README.md`.

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
| Tìm lại (giai đoạn 2) | `onboard/dtrack/search.py` | Đợt tìm 20 s sau khi mất hình: `SearchEpisode` (đồng hồ, pha), `SearchPlanner` (quét khớp và yaw). Mặc định TẮT; bật bằng hồ sơ `search_plane_r15` |

Module khớp gật (giai đoạn 1, đã nối vào `app.py` và ghi `gimbal.csv` qua `GimbalLogger` trong `logger.py`):

| Module | File | Vai trò |
|---|---|---|
| Hình học khớp | `onboard/dtrack/gimbal.py` | Dải 10°–110°; tính góc khớp cần để đường ngắm đạt góc nâng mong muốn; tư thế camera từ tư thế thân và góc khớp |
| Điều khiển khớp | `onboard/dtrack/gimbal_control.py` | Đặt góc khớp theo đường ngắm tới mục tiêu; mất mục tiêu thì giữ hướng nhìn cũ |
| Dốc góc nâng | `onboard/dtrack/elev_ramp.py` | Sau khi khóa, đưa góc nâng giữ từ giá trị đo về −12° với tốc độ giới hạn |
| Mô hình servo | `onboard/simtools/servo_model.py` | Giới hạn tốc độ, trễ, thời gian chết, lượng tử góc (giả định MG90S) |

Hằng số cấu hình chính nằm trong `onboard/dtrack/config.py`. Hồ sơ giữ 15 m: `accept_plane_r15`. Khớp chủ động bật bằng `gimbal.enabled` trong cấu hình; cờ này không dùng cùng `camera.gimbal_enabled` (mô hình khớp kiểu cũ, các hồ sơ `accept_*` cũ vẫn dùng). Camera mặc định trong cấu hình vẫn là camera cũ (fx 1739 px); cấu hình camera Wide danh định là `onboard/simtools/configs/plane_r15_gimbal_e12_wide.json`.

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

# Kiểm phần mềm bám (kỳ vọng theo sổ ghi 2026-11-19: 1368 passed, 1 xfailed)
wsl -d Ubuntu-24.04 -- bash -lc 'cd <repo-wsl>/onboard && ~/venv-ardupilot/bin/python -m pytest -q'

# Vòng kín khớp chủ động, giữ 15 m, mục tiêu cắm 15°, 10 m/s, seed 1 (mã thoát 0 = đạt)
wsl -d Ubuntu-24.04 -- bash -lc 'CONFIG=<repo-wsl>/onboard/simtools/configs/plane_r15_gimbal_e12.json SEED=1 SCENARIO=none DIVE_DEG=15 bash <repo-wsl>/onboard/simtools/run_closed_loop.sh 10'

# Hình báo cáo từ thư mục các lần chạy (chỉ đọc log; kết quả mở bằng trình duyệt)
wsl -d Ubuntu-24.04 -- bash -lc 'cd <repo-wsl>/onboard && ~/venv-ardupilot/bin/python -m simtools.report_run <thư mục lần chạy>... --batch-html <file.html>'

# Màn hình lab trên PC với video ghi sẵn (chỉ localhost, mở http://localhost:8080/)
wsl -d Ubuntu-24.04 -- bash <repo-wsl>/lab/run_demo.sh [video] [cổng]

# Kiểm bộ cài GCS (không cần quyền admin)
powershell -ExecutionPolicy Bypass -File gcs\tests\Test-GcsLogic.ps1
```

Lệnh vòng kín và lệnh hình đã đối chiếu với mã (`run_closed_loop.sh` nhận `CONFIG`, `PROFILE`, `DIVE_DEG`; `report_run.py` nhận `--batch-html`) nhưng chưa chạy lại khi viết tài liệu này. Kiểm trước khi dùng. Đợt D–F không đặt `PROFILE`: đặt `PROFILE` thì `CONFIG` bị bỏ qua không báo lỗi, và `PROFILE=accept_plane_r15` chạy mô hình khớp kiểu cũ, không phải khớp chủ động. Camera Wide dùng `plane_r15_gimbal_e12_wide.json`. Lô nhiều lần chạy bằng `onboard/simtools/run_acceptance.sh`. Ca tìm lại: xem mục "Giai đoạn 2". Git chạy bằng Git for Windows (Git Bash), không chạy trong WSL. Kiểm thử phần nhận diện: `~/venv-vision/bin/python -m pytest tests_b1` trong thư mục `vision` (177 passed theo sổ ghi 2026-11-19). Thông tin đăng nhập Pi nằm ở `pi/pi.env` (không theo dõi bằng git; mẫu `pi/pi.env.example`).

Lưu ý an toàn:

- Đây là drone tốc độ cao. Phần mềm bám chưa được kiểm trên phần cứng thật. Mọi tham số là đề xuất cho đến khi có bằng chứng bay thử.
- Không bay khi chưa đi hết `gcs/config/checklist-truoc-bay.md`.
- Tham số failsafe `gcs/config/dtrack-failsafe.param` là đề xuất, chưa bay thử. Duyệt từng giá trị trước khi nạp.
- Mọi thao tác ghi lên bộ điều khiển bay (nạp firmware, đổi tham số) cần chủ dự án duyệt riêng.
- Rà soát bảo mật liên kết điều khiển là việc bắt buộc trước buổi bay thật. Hiện chưa làm.
- Bộ cài GCS (`gcs/Install-Gcs.ps1`) chỉ dành cho laptop GCS riêng, cần quyền admin. Không chạy trên máy cá nhân. Đọc `gcs/README.md` trước. Chưa chạy thật lần nào.

Giấy phép và dữ liệu:

- Ultralytics và BoxMOT dùng AGPL-3.0. Cần xem xét trước khi phân phối ra ngoài. Chưa có tư vấn pháp lý.
- DUT Anti-UAV dùng Apache-2.0. Det-Fly dùng MIT trên repo gốc (chỉ kiểm trên repo gốc); đã tải, coi là đủ 7.635 cặp ảnh-nhãn. MMFW-UAV: giấy phép chưa xác minh.
- Dữ liệu và trọng số của bên thứ ba không đưa vào repo.

Điều chưa chốt:

- Khoảng cách giữ chính thức (sau cổng B5). Hiện dùng 15 m.
- Đổi camera mặc định trong mã sang Wide và hiệu chuẩn trên Pi (chưa có kế hoạch).
- Có nhận giai đoạn 2 với các rủi ro đã biết hay sửa tiếp (rủi ro a, c) trước: chờ chủ dự án.
- Cách bám ở tốc độ cao (trên khoảng 14 m/s khi mục tiêu phanh gấp).
- Tốc độ hành trình 200–250 km/h, sau khi tốc độ tối đa đổi thành 400 km/h.
- Hai chế độ vận hành (bay tay rồi khóa bám bằng công tắc trên tay điều khiển; khóa từ trạm GCS). Chưa có kế hoạch riêng.

Cách làm việc: mỗi bước xong là một commit. Sổ ghi `.office/ledger.md` chỉ ghi thêm. Mỗi kết quả có ngày, mã việc và bằng chứng. Việc chưa kiểm được ghi rõ là "chưa kiểm chứng".

</details>
