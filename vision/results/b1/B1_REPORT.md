# B1 - nhan dien + theo doi tren video ghi san (offline)

Ngay 2026-11-17. Chi xu ly file video, khong ket noi thiet bi. Phien ban: ultralytics 8.4.215, torch 2.15.0+cpu, opencv 5.0.0.93, lap 0.5.14 (ultralytics tu cai), CPU may nay (16 loi, khong GPU). KHONG phai so cua Raspberry Pi.

## Gioi han (doc truoc)
- Khong co nhan tung khung -> so do "khong can nhan": video DRONE gia dinh 1 drone/phan lon thoi luong; "khung co det" khong dong nghia dung vi tri. Chi tu xem khung mau, khong gan nhan tay, khong co precision/recall.
- Video ngan (~10 s, ~310 khung), nen H.264 manh, ngoai troi, nen troi/cay; muc tieu nho (be rong tv 7-30 px).
- 119 file chu khong phai ~30: 114 DRONE + 4 AIRPLANE + VIDEO.MOV. Video may bay (4 file, 1274 khung) la "khong drone" theo y nguoi dung.
- Do toc do: bulk chay 4 tien trinh x 2 loi (taskset) nen ms moi khung CAO hon (~80-107 ms); so 1 tien trinh 8 loi o bang cuoi.

## a. Danh muc video (day du: catalog.csv; anh mau: runs/b1_videos/sheets/)
| nhom | so file | do phan giai | khung | fps | ghi chu sau khi xem khung giua |
|---|---|---|---|---|---|
| V_DRONE_001..114 | 114 | 640x512 | ~310/file (~10 s) | 30 | drone rat nho tren nen troi/dong; 036, 039, 016, 073, 111-114 khong thay ro drone o khung giua (co the ra/vao khung); 001 co them 1 vat the thu 2 gan mat dat; 106-110 co chim/vat the khac (nhieu muc tieu); 109 phat hien kep 82% khung (xem khung: 1 drone thay doi, khong xac nhan 2 drone) |
| V_AIRPLANE_001..004 | 4 | 640x512 | 1274 tong | 30 | may bay that (khong drone); 002 co cat canh (nen troi doi) |
| VIDEO.MOV | 1 | 464x848 (doc) | 1201 (40 s) | 30 | canh cam tay/dien thoai, 1 vat the nho tren troi; khong xem ky, gia dinh co drone |
Tat ca frames_meta = frames_read (khong sai lech so khung).
## b,c,d. Cac bang
| model | cach | tracker | conf | khung co det | dung 1 muc tieu | ID/video (TV) | video 1 ID | doi ID/video | dut/video | dut dai nhat TV/max (s) | be rong TV (px) | video 0 det |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ai5 | full | botsort | 0.25 | 34.1% | 32.8% | 2 (2.2 tb) | 19% | 1.5 | 4.7 | 0.32/7.83 | 26.4 | 19 |
| ai5 | full | botsort | 0.5 | 17.9% | 25.6% | 1 (1.3 tb) | 25% | 0.7 | 1.4 | 0.00/7.27 | 29.6 | 35 |
| ai5 | full | bytetrack | 0.25 | 34.1% | 32.7% | 2 (2.3 tb) | 19% | 1.6 | 4.9 | 0.33/7.83 | 26.8 | 19 |
| ai5 | full | bytetrack | 0.5 | 17.9% | 25.5% | 1 (1.3 tb) | 24% | 0.7 | 1.4 | 0.00/7.27 | 30.4 | 35 |
| ai6 | full | botsort | 0.25 | 67.6% | 65.1% | 2 (1.9 tb) | 38% | 1.2 | 2.1 | 0.17/7.93 | 28.6 | 6 |
| ai6 | full | botsort | 0.5 | 33.0% | 48.2% | 1 (1.0 tb) | 46% | 0.4 | 0.5 | 0.00/5.00 | 33.3 | 31 |
| ai6 | full | bytetrack | 0.25 | 67.6% | 64.8% | 2 (2.1 tb) | 33% | 1.4 | 2.4 | 0.21/7.93 | 28.7 | 6 |
| ai6 | full | bytetrack | 0.5 | 33.0% | 47.4% | 1 (1.1 tb) | 45% | 0.4 | 0.6 | 0.00/5.00 | 34.3 | 31 |
| ft | crop | botsort | 0.25 | 92.6% | 90.0% | 2 (3.1 tb) | 41% | 2.1 | 2.9 | 0.07/4.03 | 14.6 | 0 |
| ft | crop | botsort | 0.5 | 86.1% | 88.5% | 1 (2.5 tb) | 51% | 1.5 | 1.9 | 0.03/4.47 | 14.6 | 4 |
| ft | crop | bytetrack | 0.25 | 92.6% | 89.7% | 2 (3.2 tb) | 38% | 2.2 | 3.4 | 0.07/4.03 | 14.6 | 0 |
| ft | crop | bytetrack | 0.5 | 86.1% | 88.2% | 2 (2.6 tb) | 46% | 1.6 | 2.2 | 0.03/4.47 | 14.6 | 4 |
| ft | full | botsort | 0.25 | 91.2% | 83.3% | 3 (5.0 tb) | 32% | 4.1 | 4.7 | 0.10/5.13 | 15.4 | 0 |
| ft | full | botsort | 0.5 | 79.2% | 83.2% | 2 (3.5 tb) | 36% | 2.5 | 3.1 | 0.13/7.73 | 15.5 | 4 |
| ft | full | bytetrack | 0.25 | 91.2% | 82.9% | 3 (5.3 tb) | 30% | 4.4 | 5.0 | 0.10/5.13 | 15.3 | 0 |
| ft | full | bytetrack | 0.5 | 79.2% | 82.9% | 2 (3.6 tb) | 34% | 2.6 | 3.4 | 0.17/7.73 | 15.3 | 4 |

| model | cach | tracker | conf | khung may bay co det | /100 khung | track gia >0.5s | tong ID gia | ms det TV | ms tong TV | ms tong p95 | ti le quay ve quet ca khung |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ai5 | full | botsort | 0.25 | 18/1274 | 1.41 | 0 | 3 | 107.2 | 107.3 | 122.9 | 0.0 |
| ai5 | full | botsort | 0.5 | 2/1274 | 0.16 | 0 | 0 | 107.2 | 107.2 | 122.9 | 0.0 |
| ai5 | full | bytetrack | 0.25 | 18/1274 | 1.41 | 0 | 3 | 107.2 | 107.3 | 122.9 | 0.0 |
| ai5 | full | bytetrack | 0.5 | 2/1274 | 0.16 | 0 | 0 | 107.2 | 107.2 | 122.9 | 0.0 |
| ai6 | full | botsort | 0.25 | 1245/1274 | 97.72 | 6 | 6 | 94.8 | 95.1 | 105.2 | 0.0 |
| ai6 | full | botsort | 0.5 | 951/1274 | 74.65 | 5 | 5 | 94.8 | 95.0 | 105.2 | 0.0 |
| ai6 | full | bytetrack | 0.25 | 1245/1274 | 97.72 | 6 | 6 | 94.8 | 95.1 | 105.2 | 0.0 |
| ai6 | full | bytetrack | 0.5 | 951/1274 | 74.65 | 5 | 5 | 94.8 | 95.1 | 105.2 | 0.0 |
| ft | crop | botsort | 0.25 | 1274/1274 | 100.0 | 9 | 12 | 106.4 | 106.6 | 115.1 | 0.01 |
| ft | crop | botsort | 0.5 | 1177/1274 | 92.39 | 9 | 10 | 106.4 | 106.7 | 115.1 | 0.01 |
| ft | crop | bytetrack | 0.25 | 1274/1274 | 100.0 | 9 | 12 | 106.4 | 106.7 | 115.0 | 0.01 |
| ft | crop | bytetrack | 0.5 | 1177/1274 | 92.39 | 9 | 10 | 106.4 | 106.7 | 115.1 | 0.01 |
| ft | full | botsort | 0.25 | 1274/1274 | 100.0 | 7 | 8 | 77.8 | 78.1 | 91.5 | 0.0 |
| ft | full | botsort | 0.5 | 1246/1274 | 97.8 | 7 | 8 | 77.8 | 78.1 | 91.5 | 0.0 |
| ft | full | bytetrack | 0.25 | 1274/1274 | 100.0 | 7 | 8 | 77.8 | 78.1 | 91.6 | 0.0 |
| ft | full | bytetrack | 0.5 | 1246/1274 | 97.8 | 7 | 8 | 77.8 | 78.1 | 91.6 | 0.0 |

| model (1 tien trinh, 8 luong, 5 video) | video | ms det TV | ms track TV | ms tong TV | ms tong p95 | fps |
|---|---|---|---|---|---|---|
| ai5 | 5 | 35.3 | 0.15 | 35.5 | 39.6 | 28.2 |
| ai6 | 5 | 29.3 | 0.15 | 29.4 | 41.6 | 34.0 |
| ft | 5 | 26.2 | 0.17 | 26.4 | 29.2 | 37.9 |

Bang 1 (b): video DRONE (n=114), moi o la tong/trung vi tren video. "TV" = trung vi. "dut" = so doan khung lien tiep khong co track giua khung co track dau va cuoi; "doi ID" = so lan ID cua track tin cay nhat doi. Be rong = khung bao cua track chinh, trung vi cua trung vi moi video.
Bang 2 (c, d): 4 video may bay: khung co "drone" (nhan sai lop) va cac track song > 0.5 s; ms = ms/khung nhan dien+theo doi trong bulk 2 loi.
Bang 3 (d): toc do sach 1 tien trinh 8 loi, 5 video drone (001,021,045,075,100), dau vao 640x512 (letterbox 640x512), full frame, ByteTrack.

## e. Thu ca khung (640) vs cat 320x320 o do phan giai goc quanh muc tieu khung truoc (ft, conf 0.25, ByteTrack)
Luu y: khung 640x512 nho hon cua so 640x640 nen "cat 640" trung "ca khung"; thay bang cat 320x320 (phong 2x, dua vao dau vao 640). Mat muc tieu -> quet ca khung cung khung do.
| chi so | full | crop320 | chenh |
|---|---|---|---|
| khung co det | 91.2% | 92.6% | +1.4 |
| dung 1 muc tieu | 82.9% | 89.7% | +6.8 |
| ID tb/video | 5.3 | 3.2 | -2.1 |
| doi ID/video | 4.4 | 2.2 | -2.2 |
| dut/video | 5.0 | 3.4 | -1.6 |
| may bay bi nhan "drone"/100 khung | 100 | 100 | 0 |
| ti le khung phai quay ve quet ca khung (crop) | - | 1% (tb video drone) | |
Crop chi chay cho ft (ai5/ai6 crop bo vi het gio). Chi phi: crop320 lam them 1 lan suy luan khi mat muc tieu nen ms/khung tang trong bulk (78 -> 106 ms).

## Ket luan cong B1: DAT CO DIEU KIEN
- Model tot nhat: ft_v8n + crop320 + ByteTrack (BoT-SORT khong ReID cho so gan nhu bang): 92.6% khung co det, 89.7% khung dung 1 muc tieu o conf 0.25. Tu xem 3 khung/video: khung bao nam dung tren drone o DRONE_021, 075, 100, 106, 109 va may bay AIRPLANE_002 (video crop320); DRONE_001, 045 va AIRPLANE_001 xem o ban full (ft, conf 0.25) cung dung. 001/045 va AIRPLANE_001 crop320 chua mo lai anh.
- DAT o: bam duoc muc tieu rong ~15 px da so khung; toc do ~38 fps (26 ms) 1 tien trinh 8 loi tren CPU may nay.
- DIEU KIEN / CHUA DAT: (1) do on dinh ID kem: chi 38% video giu dung 1 ID; muc tieu nho (<10 px) vo ID hang chuc lan (DRONE_009: 36 ID). (2) ft nhan MAY BAY thanh drone 100% khung o conf 0.25 va 0.5 (khong phan biet drone/may bay; tracker khong giup). ai5 (40 lop, lop drone) chi 1.4 bao dong/100 khung nhung bat duoc co 34% khung drone, ai6 97.7%. (3) chua co so co nhan nen chua biet precision. De len B2 can: loc ID (tang track_buffer, hoac gan lai ID theo vi tri) va them du lieu am tinh "may bay/chim" khi tinh chinh.

## Lenh tai lap (WSL, tu PowerShell: wsl -d Ubuntu-24.04 -- bash /mnt/d/Personal/Drone-Tracking/vision/scripts/<file>.sh)
bash scripts/run_b1_detect.sh ; bash scripts/run_b1_track.sh ; python -I scripts/summarize_b1.py ; render_b1.py / grab_b1.py (xem README.md muc B1). Mo hinh: ft_v8n_best.pt (vision/weights), AI-6/best.pt (yolov8n 1 lop, huan luyen imgsz 960 nhung chay 640), AI-5/weights/best.pt (yolo12n 40 lop, drone = lop 38, imgsz 512). Tracker: ByteTrack track_buffer 30 khung, match_thresh 0.8, new_track_thresh = conf; BoT-SORT with_reid=False, gmc none (khong dung optical flow) nen khong khac nhieu ByteTrack.
Video ket qua: runs/b1_videos/best_ft_crop/*.mp4 (7 drone + 2 may bay, ft crop320, conf 0.25; codec mp4v) + check/*.jpg (3 khung/video). Video mau: D:\Personal\Drone-Tracking\vision\runs\b1_videos\best_ft_crop\V_DRONE_075_tracked.mp4 (0,8 MB).