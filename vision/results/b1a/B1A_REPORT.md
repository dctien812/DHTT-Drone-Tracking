# B1a: nhận diện máy bay cánh bằng (drone bám mục tiêu) - báo cáo

Ngày 2026-11-19. Người đọc: chủ dự án và phiên làm việc sau. Mọi số lấy từ file kết quả trong thư mục này (nguồn ghi dưới mỗi bảng). "Gốc" = `yolov8n.pt` chính thức, chỉ dùng lớp `airplane` của COCO, không huấn luyện thêm.

## Tóm tắt
1. Huấn luyện thêm (một vòng, một seed, không tinh chỉnh) KHÔNG cho model tốt hơn model gốc một cách ổn định trên tập kiểm chéo; nhưng model final bắt máy bay trên video thật 1 tốt hơn gốc ở đoạn liên tục và máy bay xa (98,6% so với 84,2%), không hơn ở khung rải (69,4% so với 71,8%; đất xa 3/33 so với 14/33), với giá báo động giả gấp ~17 lần (fin1: 69 so với 4 phát hiện giả; fin2: 441, ~110 lần).
2. Lượt EE (học máy bay tối, kiểm máy bay trắng): ở cảnh nhìn từ trên xuống (góc drone sẽ nhìn) bắt được 0,129 so với 0,402 của model gốc; báo động giả trên nền mặt đất 1,17/100 so với 0,14/100.
3. Lượt DD (học máy bay trắng, kiểm máy bay tối): bắt tốt hơn model gốc ở cỡ nhỏ (0,830 so với 0,550) nhưng báo động giả 1,80/100 so với 0,59/100 và kém hẳn ở máy bay lớn (>200 px).
4. Video thật 1 (quét cả khung, ngưỡng 0,12): gốc bắt 84,2% (đoạn liên tục), 71,8% (khung rải); final bắt 98,6% và 69,4% (khung nguyên) hoặc 81,5% (khung phóng lên); phát hiện giả trên 269 khung liên tục: gốc 4, final fin1 69, fin2 441.
5. Khuyến nghị: model mặc định vẫn là gốc ngưỡng 0,12 cho tới khi xử lý được báo động giả; final là ứng viên chính cho vòng sau (thêm nền khó làm mẫu âm). Chưa có model nào được kiểm trên đúng máy bay mục tiêu (xám/cam) nhìn từ trên xuống.

## Dữ liệu và cách chia
- Ảnh trên mạng, chia thành 4 bộ: D, D' (máy bay tối) và E, E' (máy bay trắng); mỗi cặp 6 đoạn video. Tổng 18.655 khung. Cảnh khác nhau: D có nhà cao tầng ở chân trời, E nhìn xuống rừng trụi lá.
- Kiểm chéo theo máy bay: lượt EE học trên D, D' và kiểm trên E + E' (10.103 khung); lượt DD học trên E, E' và kiểm trên D + D' (8.552 khung). Model chưa từng thấy máy bay của tập kiểm.
- Học: lấy thưa mỗi 6 khung, cắt vùng 480x480 có máy bay + vùng nền cùng số lượng + 708 ảnh chim (làm ảnh âm). EE: 1.153 khung học / 428 khung val (3.014 / 856 ảnh). DD: 1.375 / 506 (3.458 / 1.012 ảnh). Val = 15% cuối mỗi đoạn, chỉ dùng chọn ngưỡng.
- Model final học cả 4 bộ (2.528 khung học / 934 val, 5.764 ảnh), không có tập kiểm; chỉ để chấm trên video thật 1.
- Kiểm tra chống rò: 0 khung của tập kiểm nằm trong tập học/val; tập kiểm đóng băng, sha256 trước/sau trùng (`train\build_report.json`).
- Cặp anh em giống nhau (tương quan D-D' 0,91; E-E' 0,83), nên số mẫu độc lập thực chất là 6 đoạn chứ không phải 10.103 khung.

## Cách đo (A1-A4, mức hiện hành)
- A1 (tỉ lệ bắt được): khung bao đúng (IoU >= 0,5) trên vùng cắt có máy bay; cần >= 0,60 ở mỗi dải cỡ 16-57 px và 57-200 px. Báo riêng theo hướng nhìn; Top_Down (nhìn xuống) là số cần theo dõi nhất.
- A2 (cụm mất liên tiếp): chỉ báo cáo, không có ngưỡng đạt/không đạt. Cụm mất tính bằng giây ở 30 khung/s (GIẢ ĐỊNH, chưa biết tần số khung thật của dữ liệu).
- A3 (báo động giả): <= 1 báo động giả trên 100 vùng nền mặt đất (các bảng dùng dòng "ground").
- A4 (tỉ lệ bám): tỉ lệ khung bộ bám giữ đúng mục tiêu chia cho trần nhãn thật (cùng tần số khung); cần >= 0,65.
- Ngưỡng tin cậy chọn trên val (quy tắc: báo động giả val <= 1/100). Khoảng dao động (lo-hi) lấy theo đoạn video.

## Kết quả
Bảng 1: kiểm trên E + E' (10.103 khung, 6 đoạn). Gốc ngưỡng 0,12; EE ngưỡng 0,095 (chọn trên val).

| Chỉ số | Gốc | EE | Mức |
|---|---|---|---|
| A1 16-57 px | 0,763 | 0,770 | >= 0,60 |
| A1 57-200 px | 0,696 | 0,589 (dao động 0,297-0,905) | >= 0,60 |
| A1 >200 px (n=181) | 0,840 | 0,608 | chỉ tham khảo |
| Top_Down (n=3.601) | 0,402 | 0,129 | theo dõi |
| Horizontal / Bottom_Up | 0,791 / 0,980 | 0,831 / 0,995 | |
| A2 cụm >= 3 s / dài nhất | 1 / 10,50 s | 11 / 11,97 s | chỉ báo cáo |
| A3 nền mặt đất (/100) | 0,14 | 1,17 | <= 1 |
| A4 tỉ số, 30 / 15 khung/s | 0,759 / 0,718 | 0,675 / 0,642 | >= 0,65 |
| Đạt A1 / A3 / A4 | đạt / đạt / đạt | không (0,589) / không / đạt | |

Nguồn: gốc `g0\g0_report.md` (mục Ngưỡng 0,12: dòng 12-60); EE `eval_trained\EE\report.md` (mục ngưỡng 0,095: dòng 6-29).

Bảng 2: kiểm trên D + D' (8.552 khung, 6 đoạn). Gốc ngưỡng 0,12 (chọn trên val cũ của G0, `g0\g0_report.md` dòng 5: đuôi các đoạn D/D', nằm trong tập kiểm DD; dùng chung vì đơn giản); DD ngưỡng 0,085 (chọn trên val); cột cuối là DD ngưỡng 0,25 CHỈ THAM KHẢO (chọn sau khi đã thấy tập kiểm).

| Chỉ số | Gốc | DD @0,085 | DD @0,25 (tham khảo) |
|---|---|---|---|
| A1 16-57 px | 0,550 | 0,830 | 0,824 |
| A1 57-200 px | 0,728 | 0,786 | 0,764 |
| A1 >200 px (n=571) | 0,839 | 0,630 | 0,608 |
| Top_Down (n=2.721) | 0,584 | 0,616 | 0,568 |
| Top_Down >200 px (n=132) | 0,803 | 0,144 | 0,045 |
| Horizontal / Bottom_Up | 0,656 / 0,873 | 0,721 / 0,985 | 0,710 / 0,982 |
| A2 cụm >= 3 s / dài nhất | 1 / 5,03 s | 3 / 7,03 s | 4 / 8,03 s |
| A3 nền mặt đất (/100) | 0,59 | 1,80 | 0,59 |
| A4 tỉ số, 30 / 15 khung/s | 0,796 / 0,748 | 0,830 / 0,815 | 0,830 / 0,815 |
| Đạt A1 / A3 / A4 | không (0,550) / đạt / đạt | đạt / không / đạt | đạt / đạt / đạt |

Lưu ý về cột "Gốc": 0,12 không chọn theo quy tắc val của lượt DD. Theo quy tắc đó (val = đuôi các đoạn D/D', nằm trong chính tập kiểm DD) ngưỡng của gốc là 0,065, và khi đó A3 mặt đất là 1,91/100 (không đạt) và A1 16-57 px là 0,561 (`eval_trained\orig_DD\report.md` dòng 4-24). Câu "gốc đạt A3" chỉ đúng ở ngưỡng 0,12.

Nguồn: gốc `eval_trained\orig_DD\report.md` (mục ngưỡng 0,12: dòng 60-86); DD `eval_trained\DD\report.md` (dòng 4-30 và 32-58). Gốc chạy lại trên CPU khớp từng phát hiện với G0 (trên mẫu E + E': 1.800 vùng có máy bay và 1.011 vùng nền; lệch 0,0; `eval_trained\verify_orig\verify.json`).

Đọc hai bảng: tập kiểm khác nhau nên KHÔNG so số giữa bảng 1 và bảng 2. Trong từng bảng: model huấn luyện chỉ hơn khi nhìn lại đúng loại máy bay nó đã học một phần (DD ở cỡ nhỏ), và thua hẳn khi gặp màu/góc chưa thấy (EE ở Top_Down). Cả hai đều báo động giả nhiều hơn model gốc ở ngưỡng chọn trên val.

## Model final
Model final học cả 4 bộ, không có tập kiểm chéo, nên chỉ chấm được trên video thật 1 (ngưỡng 0,12, quét cả khung, IoU >= 0,5; 569 nhãn liên tục + 124 nhãn rải). "fin1" = khung nguyên 1080 px; "fin2" = khung phóng lên 2304 px (đúng thang huấn luyện, phóng bằng nội suy).

| Chỉ số | Gốc | fin1 | fin2 |
|---|---|---|---|
| Bắt được, liên tục | 479/569 (84,2%) | 561/569 (98,6%) | 560/569 (98,4%) |
| 16-57 px (liên tục) | 375/459 | 454 | 453 |
| 57-200 px (liên tục) | 96/96 | 96 | 96 |
| Bắt được, rải | 89/124 (71,8%) | 86 (69,4%) | 101 (81,5%) |
| Đất xa (rải) | 14/33 | 3 | 16 |
| Bay gần (rải) | 12/12 | 12 | 12 |
| Bay xa (rải) | 35/48 | 43 | 48 |
| Bay xa (liên tục) | 327/412 | 404 | 404 |
| Cụm mất >= 0,25 s (đoạn liên tục; máy bay M1; M2) | 1; 1 | 0; 0 | 0; 0 |
| Cụm dài nhất (đoạn liên tục; M1; M2) | 0,27 s; 0,47 s | 0 s; 0,23 s | 0 s; 0,23 s |
| Số phát hiện giả (đếm theo phát hiện, không theo khung) @0,12: liên tục (269 khung) / rải (60) / đất xa (31) | 4 / 0 / 0 | 69 / 24 / 27 | 441 / 88 / 39 |
| Phát hiện giả @0,25 | 1 / 0 / 0 | 44 / 16 / 12 | 234 / 51 / 26 |
| Phát hiện giả @0,085 | 8 / 0 / 0 | 93 / 34 / 36 | 556 / 109 / 51 |
| Bắt được liên tục @0,25 | 453 | 559 | 560 |

Đọc: final bắt tốt hơn ở đoạn liên tục và máy bay xa (bay xa rải 43 và 48 so với 35 trên 48) và không còn cụm mất >= 0,25 s, nhưng KHÔNG hơn ở khung rải với fin1 (86 so với 89; đất xa 3 so với 14 trên 33; fin2 101 và 16). Phát hiện giả nhiều hơn: ở ngưỡng 0,12 fin1 69 so với 4 (~17 lần), fin2 441 (~110 lần), trên 269 khung; ở 0,25 fin1 44, fin2 234 so với 1. Số so sánh chính dùng fin1 (khung nguyên), fin2 ghi kèm. Phát hiện giả của final (độ tin cậy tới 0,87) chủ yếu là: vệt trắng/mảnh vụn trên bê tông, mái nhà có cờ đỏ, bình nước mái nhà xa, ngọn cây; 3 trong 20 cái cao nhất nằm trên chính máy bay (có thể do nhãn lệch, chưa đối chiếu).
Chưa kiểm chứng: một video duy nhất, trời sáng; đường băng (rải, quét cả khung): gốc 27/30, fin1 27/30, fin2 24/30; fin2 mới xem 12/20 phát hiện giả; số phát hiện giả đếm theo phát hiện (file tổng hợp ghi "N FA / M khung"), nên một khung có thể góp nhiều. Nguồn: số do người giao việc cung cấp từ kết quả `realvideo1` (thư mục không lên GitHub), đã được lần rà độc lập đối chiếu với các file tổng hợp, khớp.

## Video thật 1 (phép đo và số của model gốc; số model final ở mục trên)
Video điện thoại quay từ mặt đất trên đường băng, 75,6 s, 30 khung/s; 392 khung có nhãn (300 khung liên tục + 112 khung rải). Quét cả khung, ngưỡng 0,12, IoU >= 0,5, lớp airplane.
- Bắt được: đoạn liên tục 84,2% (16-57 px: 82%; 57-200 px: 100%); khung rải 71,8% (đất xa 14/33, đường băng 27/30, bay gần 12/12, bay xa 35/48).
- Cụm mất dài nhất (đoạn liên tục): máy bay M1 0,27 s, M2 0,47 s; không cụm >= 3 s. Đoạn rải không có phép đo cụm mất. Phát hiện giả: 4 trên 269 khung (mái nhà xa).
- Khi trượt airplane: khoảng 80% (95/120) là bị gọi thành "kite" (quét, ngưỡng 0,10). Trên E + E' lớp "kite" trùng máy bay ở 523/10.103 khung (ngưỡng 0,12; `g0\g0_report.md` dòng 408).
- Dải cỡ px đã quy đổi bằng hệ số 0,673 (giả định: điện thoại 26 mm, chưa đo). Góc quay từ mặt đất, camera điện thoại: không phải góc và camera thật của drone.
- Nguồn: `realvideo1\README.md` (mô tả phép đo) và ghi chép nội bộ, không công khai; thư mục `realvideo1` không đưa lên GitHub.

## Thời gian huấn luyện (card AMD RX 9060 XT, YOLOv8n 1 lớp, 60 epoch, ảnh 480, batch 16, seed 0, patience 15, khởi đầu từ yolov8n COCO)
| Lượt | Ảnh học / val | Thời gian | Mỗi epoch | mAP50 val cuối |
|---|---|---|---|---|
| EE | 3.014 / 856 | 1.774,6 s (~29,6 phút) | 29,58 s | 0,995 |
| DD | 3.458 / 1.012 | 4.396,1 s (~73,3 phút) | 73,27 s | 0,995 |
| final | 5.764 / 1.868 | 3.866,4 s (~64,4 phút) | 64,44 s | 0,995 |
Tổng 10.037,1 s (2 giờ 47 phút). Lượt DD (và có thể một phần final) bị chậm vì một ứng dụng khác dùng chung card trong lúc huấn luyện (epoch 1-20 của DD ~30 s, sau đó 80-118 s); chỉ số của EE là gần sạch. mAP50 val ~0,995 ở cả ba lượt KHÔNG nói lên chất lượng: val cùng đoạn với tập học. Chấm trên CPU mất 20-33 ms mỗi ô 480 px (8 luồng). Nguồn: `train\EE_summary.json`, `train\DD_summary.json`, `report.md` các lượt.

## Hạn chế và điều chưa kiểm chứng
- Lần rà độc lập: số liệu được tự tính lại từ file thô và khớp (ví dụ EE 57-200 px: 4310/7317 = 0,589; DD nền mặt đất 49/2721 = 1,80).
- Top_Down 0,129 của EE là thật, không phải lỗi đo: model hầu như không đưa ra phát hiện (hạ ngưỡng xuống 0,01 chỉ lên 0,208; model gốc cùng vùng cắt 0,477 và 0,327). Nguyên nhân: lệch miền (học máy bay tối, kiểm máy bay trắng nhìn từ trên).
- Quy tắc chọn ngưỡng trên val bị bão hòa: val là đuôi của chính đoạn đã học nên recall val = 1,0. Vì vậy A3 "không đạt" của DD là do ngưỡng 0,085. Ngưỡng 0,25 cho DD đạt cả ba tiêu chí nhưng chỉ tham khảo vì chọn sau khi đã nhìn tập kiểm; không được coi là kết quả đạt.
- EE 0,589 so với mức 0,60 không có ý nghĩa thống kê (dao động theo đoạn 0,297-0,905). A4 của EE là 0,675 ở 30 khung/s nhưng 0,642 ở 15 khung/s (dưới 0,65); tần số khung của dữ liệu là giả định.
- Chưa giải thích vì sao A4 không đổi khi đổi ngưỡng trong khoảng 0,065-0,25. A4 dùng phát hiện trong vùng cắt quanh nhãn nên lạc quan.
- Val chỉ còn 428 vùng nền (EE): mỗi báo động giả = 0,23/100. Top_Down 16-57 px của DD chỉ n=70; dải >200 px của EE chỉ n=181 (3 đoạn).
- Chưa chấm chéo cùng trọng số trên card và CPU; chưa thử xuất NCNN (cho Raspberry Pi); A5, A6, A7 chưa làm cho model huấn luyện, trừ phần video thật 1 (model gốc và final).
- Dữ liệu từ một khuôn viên, mùa đông, ~12 đoạn: kết quả ở đây không chứng minh chạy tốt với camera Wide, nền ruộng/cây xanh, hình mờ khi bay nhanh. Giấy phép dữ liệu nguồn chưa xác minh: chỉ dùng trong phòng thí nghiệm, không phát hành lại dữ liệu hay model huấn luyện từ đó.

## Khuyến nghị
1. Model mặc định trên máy vẫn là model gốc, lớp airplane, ngưỡng 0,12, cho tới khi xử lý được báo động giả. Lý do: trên tập kiểm chéo, học máy bay trắng thì nhận máy bay tối tốt hơn gốc, học máy bay tối thì nhận máy bay trắng nhìn từ trên kém hẳn (0,129 so với 0,402); cả hai vượt mức báo động giả ở ngưỡng chọn trên val (1,17 và 1,80 so với 0,14 và 0,59 trên 100 vùng nền).
2. Model final (nói chung, cả fin1 và fin2) là ứng viên chính cho vòng sau: trên video thật 1, đoạn liên tục bắt 98,6% (gốc 84,2%), không còn cụm mất >= 0,25 s, nhưng khung rải không hơn (fin1 69,4% so với 71,8%) và phát hiện giả gấp ~17 lần (fin1) đến ~110 lần (fin2). Việc cần làm: thêm nền khó (bê tông có vệt, mái nhà, cờ, cây) từ video sân bay làm mẫu âm rồi chấm lại.
3. Dùng final sớm hơn (chấp nhận báo động giả, dựa vào bộ bám lọc) là đánh đổi của chủ dự án; CHƯA đo qua bộ bám trên video thật.
4. Hướng rẻ đáng thử song song: nhận thêm lớp "kite" của model gốc (80% lần trượt trên video thật 1 là "kite"). Chưa đo cái giá là báo động giả tăng bao nhiêu.

## Việc vòng sau
- Quay video ở sân bay với đúng máy bay mục tiêu (xám/cam), từ góc drone nhìn; dùng làm dữ liệu học và kiểm chính.
- Đặt trước quy tắc chọn ngưỡng (không chọn trên val bão hòa); tách val theo đoạn riêng (không lấy đuôi đoạn đã học).
- Lấy Top_Down làm số chính khi chấm.
- Đo model final qua bộ bám trên video thật (chưa có); thêm mẫu âm nền khó rồi chấm lại.
- Chấm chéo cùng trọng số trên card và CPU; xuất NCNN cho Pi và đo tốc độ.
- Giải thích vì sao A4 không đổi theo ngưỡng; đo A4 trên toàn khung thay vì vùng cắt quanh nhãn.

## Cách chạy lại
Chạy từ thư mục `vision`. Script ở `vision\scripts\b1a\`. Cần dữ liệu gốc tải riêng (không nằm trong repo). Tập kiểm đóng băng dựng ở bước 6; không chạy lại mà không có lý do.
```bash
# WSL (CPU), dựng vùng cắt và chấm model gốc (G0)
~/venv-vision/bin/python scripts/b1a/run_step6.py all
~/venv-vision/bin/python scripts/b1a/run_g0.py infer ; ~/venv-vision/bin/python scripts/b1a/run_g0.py score
```
```powershell
# Windows, môi trường card (vision\.venv-gpu): dựng tập huấn luyện rồi huấn luyện EE, DD, final lần lượt
.\.venv-gpu\Scripts\python.exe scripts\b1a\run_build.py
powershell -File scripts\b1a\run_train_chain.ps1        # hoặc: python scripts\b1a\run_train.py <EE|DD|final>, rồi: ... run_train.py collect
```
```bash
# WSL (CPU), chấm model đã huấn luyện và model gốc trên D + D'
~/venv-vision/bin/python -I scripts/b1a/run_eval_trained.py infer EE ; ~/venv-vision/bin/python -I scripts/b1a/run_eval_trained.py score EE
~/venv-vision/bin/python -I scripts/b1a/run_eval_trained.py infer DD ; ~/venv-vision/bin/python -I scripts/b1a/run_eval_trained.py score DD
~/venv-vision/bin/python -I scripts/b1a/run_eval_trained.py infer ORIG_DD ; ~/venv-vision/bin/python -I scripts/b1a/run_eval_trained.py score ORIG_DD
~/venv-vision/bin/python -I scripts/b1a/run_eval_trained.py verify     # model gốc chạy lại khớp G0
```
Chấm video thật 1: `scripts\b1a\realvideo_eval.py` (cần video và nhãn của chủ dự án, không nằm trong repo; chưa kiểm chứng việc chạy lại từ đầu trong phiên này).
