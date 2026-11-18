# V2: huan luyen lai bo nhan dien drone (ft2_v8n) - bao cao (2026-11-18)

Ket luan ngan: **ft2 KHONG dat 3/4 tieu chi; chua nen thay ft_v8n.** ft2 giam bao dong gia manh (tap sach: 32,2 -> 9,3 / 100 anh o 0,25) nhung van goi
may bay trong video la drone (74% khung o 0,25; 70% o 0,5; cu: 100% / 98%) va mat recall o muc tieu 20-40 px tren DUT (0,847 vs 0,881) va 4 khung tren 120 khung nhan tay.
Bang day du: `compare.md`. Weights: `vision/weights/ft2_v8n_best.pt` (ft_v8n_best.pt khong bi ghi de).

## 1. Du lieu
- DUT Anti-UAV (Apache-2.0): 10.000 anh RGB, 1 lop. Gop train+val+test goc roi chia lai theo nhom.
- Det-Fly (MIT, nguoi dung tai san, 14 GB): 10.001 xml, 10.339 jpg, 2 thu muc ("010": 3.088 xml / 5.091 jpg; "020": 6.913 xml / 5.248 jpg); chi **7.635 cap xml+jpg khop ten** (2.366 xml thieu jpg, 2.704 jpg thieu xml -> bo tai chua day du).
  Tat ca 3840x2160, lop 'UAV', 1 muc tieu/anh (7.634; 1 anh khong co nhan). Be rong muc tieu goc: <10: 0 ; 10-20: 25 ; 20-40: 623 ; >40: 6.986 (trung vi 139 px thu muc 010, 73 px thu muc 020). Khong co ma "canh" rieng: chi 2 thu muc la chuoi khung lien tiep.
  -> muc tieu 10-40 px duoc tao bang **thu nho anh** (be rong muc tieu logU 8..80 px, nen xam 114 neu anh < 640 giong letterbox). Day la mo phong, khong phai drone xa that.
- COCO 2017 (cocodataset.org; chu thich CC BY 4.0, anh Flickr theo giay phep tung anh): tai `annotations_trainval2017.zip` (253 MB) + 1.884 anh rieng le (1.026 airplane, 858 bird; ~264 MB) tu `images.cocodataset.org`. Chi giu anh co license id 4,5,7,8 (CC BY, CC BY-SA, no known copyright, US Gov); trong train2017 co 2.986 airplane / 3.237 bird nhung chi 1.026 / 858 qua loc giay phep -> it hon 1.500-3.000 mong muon. `data/coco-neg/manifest.csv` co license + URL tung anh. 10% giu lam val.
- Dung luong ghi them: data/coco-neg 517 MB, data/v2 792 MB, runs/ft2_v8n 921 MB.

## 2. Chia theo nhom + kiem ro ri (`split_summary.md`; phep do: tuong quan xam 32x32, nguong 0,95, cung `verify/leak_features.py`)
- DUT: nhom = thanh phan lien thong tuong quan >= 0,90 (1.645 nhom; 1 nhom khong lo 3.333 anh bi xep vao train). Test 1.500 / val 729 / train 7.771. Doi chung: chia goc cua tac gia: **67,6%** anh test co anh train gan trung (tai lap dung so cu 67,6%).
- Det-Fly: nhom = tuong quan >= 0,95 (66 nhom; 0,90 gop thanh 1 nhom khong lo); khung train/val cach khung test <= 10 so khung bi loai (592 khung). Test 1.501 / val 342 (chi thu muc 020) / train 5.200.
- Sau chia, ti le anh test co anh train gan trung: **DUT 0,00% (corr>=0,95), 0,00% (>=0,90)**; **Det-Fly 0,00% (>=0,95), 0,27% (>=0,90)**. Phep do doc lap (dHash 8x8, Hamming <= 6): DUT 11,1%, Det-Fly 3,5%; corr>=0,85: DUT 35,7%, Det-Fly 13,9% -> chi the noi "khong con anh gan trung theo 0,95", van con cung bo canh tuong tu muc thap hon. Nhom tao bang chinh phep do 0,90/0,95 nen 0% o nguong do la hien nhien.
- Cach doi chung: anh test DUT cu cung tinh la lac quan: so cu o muc 20-40 px 0,945 -> 0,881 tren test sach (cung model ft).

## 3. Tap hoc (4.200 anh trong 5.566 da dung san; chon ngau nhien hat giong 0)
Duong (2.850): DUT crop 640 goc 892 + DUT thu nho 640 canh dai 309 + DUT crop thu nho ti le 0,35-0,9: 285 ; Det-Fly 1.056 (458 ti le 0,3-1,0 ; 598 ti le 0,06-0,3) ; ghep drone len nen tu nhien 308 (be rong 8-60 px).
Am (1.350 = 32,1%): COCO may bay 219 + chim 150 nguyen anh ; ghep may bay 411 + chim 259 len nen DUT/Det-Fly (be rong 8-60 px, cung ky thuat lam mo vien nhu ghep drone) ; nen khong muc tieu: DUT 114, Det-Fly 197. (May bay tong 630, chim 409.)
Be rong muc tieu trong tap hoc: <10: 353 ; 10-20: 574 ; 20-40: 930 ; >40: 993. Val: 483 anh (338 hop).

## 4. Huan luyen
yolov8n.pt chinh thuc -> `train_v2.py`: imgsz 640, 30 epoch, batch 16, CPU (torch 7 luong + 3 worker), mosaic mac dinh (tat 3 epoch cuoi), seed 0. 13.800 s = **3,83 gio** (7,7 phut/epoch; 1,7 s/lan). Uoc luong sau 2 epoch: ~4 gio < 5 gio; ban dau thu 5.566 anh -> ~5,5 gio nen giam con 4.200 anh (ghi vao quyet dinh). Chon trong so: best.pt theo val (epoch 30). Val mAP50 0,542, P 0,888, R 0,509 (val kho: nhieu muc tieu <20 px va anh ghep). Khong dung tap test/120 khung/video de chon.

## 5. So sanh ft (cu) vs ft2 (moi) - trich (day du o compare.md)
Tap test sach (DUT 1.432 + Det-Fly 1.500 anh, 0,25): P 0,668 -> 0,879 ; R 0,649 -> 0,672 ; FP/100 anh 32,2 -> 9,3. Recall theo be rong (n): <10: 0,338 -> 0,303 (142) ; 10-20: 0,364 -> 0,367 (450) ; 20-40: 0,598 -> 0,638 (907) ; >40: 0,801 -> 0,825 (1.436). Sai so be rong trung vi 1,84 -> 2,06 px, p90 10,0 -> 11,5 px.
Tach nguon, 20-40 px: DUT 0,881 -> 0,847 (n=404) ; Det-Fly 0,370 -> 0,471 (n=503). Rieng DUT cu chua thay (n=294): 0,881 vs 0,833 (seen_by_old.csv).
120 khung nhan tay (0,25): drone bat duoc 88 -> 84 /99 ; precision 0,967 -> 0,832 ; may bay bi goi drone 20 -> 15 /20 (0,5: 19 -> 14).
Video: 114 video drone 0,25: khung co det 91,2% -> 84,2% ; video giu 1 ID 29,8% -> 21,9% ; ID TB 5,26 -> 4,76. 4 video may bay: khung co "drone" 1274/1274 -> 946/1274 (0,25) ; 1246 -> 891/1274 = 69,9% (0,5).

## 6. Tieu chi dat (d)
- Tap sach, recall >= 0,90 o 20-40 px: **KHONG** (0,638; rieng DUT 0,847).
- Tap sach, <= 20 bao dong gia / 100 anh o 0,25: **DAT** (9,28; cu 32,23).
- 4 video may bay, ti le khung bi goi drone o 0,5 < 20%: **KHONG** (69,9%).
- 120 khung nhan tay, bat duoc >= 85 (88 - 3) o 0,25: **KHONG** (84, thieu 1 khung).

## 7. Nguyen nhan quan sat va gioi han
- Chan doan (`diag_neg.csv`, val chua tung hoc): anh am ghep (may bay) bi goi drone 52,5% (cu) -> 22,5% (moi); anh COCO nguyen ban 75% -> 5%. Nhung may bay that trong video (nho 20x12 px, nen xam, video nen) van bi goi drone 70% -> mo hinh hoc duoc "COCO/ghep khong phai drone", chua chuyen sang may bay xa that. Do lech mien (anh am tong hop vs video that), khong phai thieu epoch ro rang.
- Det-Fly chi con 7.635 cap; muc tieu nho chi do bang thu nho (nen xam, goc nhin tu drone, thuong tu tren xuong) nen recall nho (<20 px: ~0,37) khong dai dien camera that 1456x1088. So 10-20 px: Det-Fly n=441, DUT n=9.
- Mot lan huan luyen, mot seed, 4.200 anh; khong biet bao nhieu chenh lech la nhieu.
- Chua kiem: video that o xa co nhan; BoT-SORT; chay tren Hailo; model cu chay lai tren video (dung lai npz cu `runs/b1_det/ft_full`, so khop B1: 1274/1274, 91,2%).
- Anh xem bang mat: `runs/v2_vis/{drone_small,airplane,drone_hand}.jpg` (6 anh chinh: 2 drone Det-Fly 11-12 px bi bo sot, 1 drone DUT 20-40 px dung conf 0,71, 3 may bay deu bi goi drone 0,60-0,73).

## 8. Tai lap
```bash
bash scripts/run_features_v2.sh ; bash scripts/run_py_v2.sh split_v2.py
bash scripts/run_download_coco_neg_v2.sh 1600 1200 ; bash scripts/run_py_v2.sh build_data_v2.py
bash scripts/run_train_v2.sh --epochs 30 --limit 4200      # ~3,8 gio CPU
bash scripts/run_eval_v2.sh ft2 /mnt/d/Personal/Drone-Tracking/vision/weights/ft2_v8n_best.pt   # (ft: weights/ft_v8n_best.pt)
bash scripts/run_video_v2.sh ft2 <weights> detect ; bash scripts/run_video_v2.sh ft <weights>
bash scripts/run_py_v2.sh summarize_v2.py ; bash scripts/run_py_v2.sh compare_v2.py ; bash scripts/run_py_v2.sh diag_neg_v2.py ; bash scripts/run_py_v2.sh seen_by_old_v2.py
```
