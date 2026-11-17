# Ket luan V1 (nhan dien drone mot lop) - viet tay, so lieu lay tu cac bang ben duoi

Tap cham: DUT Anti-UAV split test, 2200 anh RGB / 2245 box, khong dung de huan luyen. Model: `old_finetune` (yolov8n 1 lop, best.pt cu), `old_ai7` (YOLOv12n 40 lop, lop 38 = drone; KHONG chay duoc tren Hailo-8), `ft_v8n` (yolov8n chinh thuc tinh chinh 20 epoch / 84 phut CPU tren crop goc DUT-train).

- Hai best.pt cu khong dung duoc cho kich ban nay: recall 0.38-0.45, mAP50 0.41-0.51 tren DUT o moi imgsz/che do; recall nhom 20-40 px goc chi 0.08-0.34.
- ft_v8n (nguong 0.25): full 640 R=0.76 mAP50=0.81; full 1280 R=0.91 mAP50=0.92; crop 640 goc R=0.93 mAP50=0.95. Cat vung 640 o do phan giai goc tot hon thu nho ca anh 640 (R 0.93 vs 0.76) va ngang thu nho 1280 voi chi phi it hon.
- Muc tieu nho nhat bat duoc >= 90% tren du lieu tu nhien (be rong goc): ft_v8n crop 640: nhom 20-40 px = 0.948 (n=667); nhom 10-20 px = 0.863 (n=51, mau nho, chua ket luan). ft_v8n full 1280: 10-20 px = 0.92 (n=51), 20-40 px = 0.895 (n=667). => nguong thuc te ~20 px (>=90%), 10-20 px chua du mau. DUT test khong co muc tieu <10 px goc.
- Phep quet tong hop (thu nho anh de muc tieu rong tw px, tren khung xam 640) KHAC va bi quan: ft_v8n 1280 chi dat recall 0.77 o 20 px, 0.84 o 30 px, 0.86 o 40 px (khong muc nao >= 0.90); 640 thap hon. Chua ro nguyen nhan (mat ngu canh khi thu nho ca anh, nen xam, khac phan bo luc huan luyen) -> coi la can duoi, chua kiem chung bang du lieu that o xa.
- Khoang cach toi da cho muc tieu 0.3 m, D = fx*0.3/w (fx=1739 px cho 6 mm; 2319 px cho 8 mm, ti le theo tieu cu): w=20 px -> 26 m (6 mm) / 35 m (8 mm); w=30 px -> 17 m / 23 m; w=40 px -> 13 m / 17 m; w=10 px -> 52 m / 70 m (recall <=0.86 o 10-20 px, chua dat 90%).
- Sai so be rong khung bao (ft_v8n, phat hien dung, nguong 0.25, crop 640): trung vi 1.6 px (5.5%) o nhom 20-40 px, p90 5.6 px (19%); o nhom >40 px trung vi 4.0%, p90 14.8%; o nhom 10-20 px trung vi 14.7% (lech +14.7%, n=44), p90 32%. Do D ti le nghich voi w nen sai so khoang cach ~ bang sai so be rong tuong doi: ky vong ~5% (trung vi) va ~19% (p90) o 20-40 px; can loc/lam muot theo thoi gian. Phan sai so do nhan DUT long hay chat chua tach duoc.
- Bao dong gia (tren 100 anh test, ft_v8n crop 640): 16.3 o nguong 0.25 (P=0.85), 4.6 o nguong 0.5 (P=0.95, R=0.90); full 1280: 37.2 o 0.25, 8.5 o 0.5 (R=0.87). Mot phan "FP" co the la drone chua gan nhan trong DUT (chua kiem).
- Toc do tham khao tren CPU may nay (6 luong, KHONG phai Pi 5/Hailo): yolov8n 640 ~27 ms/anh (pre+inf+post), 1280 ~62 ms; crop 640 ~30 ms.
- De xuat di tiep: yolov8n (Hailo-8 ho tro) do vao 640 theo cach cat 640x640 o do phan giai goc quanh muc tieu (theo `onboard`), nguong ~0.4-0.5; 1280 giup nhom 10-20 px (0.92 vs 0.67 o full 640) nhung ton ~2.3x thoi gian va gap doi FP o cung nguong.
- Han che: DUT la khung hinh video RGB (da xem 1 anh test: drone co canh quat tren nen bien/nui, quay tu xa); khong phai bo drone-nhin-drone chuan (Det-Fly khong tai tu dong duoc); anh co ve la khung lien tiep tu video, chia train/val/test la cua tac gia, CHUA kiem duoc co trung canh giua cac split khong (neu co thi so ft_v8n bi lac quan); model tinh chinh chi 20 epoch tren CPU; chua co phep do tren du lieu camera 1456x1088 that.


# Bang so lieu (tu dong sinh boi scripts/make_summary.py)

## Tap cham (DUT Anti-UAV, split test; be rong muc tieu theo px)

| split | co so px | so box | <10 | 10-20 | 20-40 | >40 | p10 | p50 | p90 | kich thuoc anh pho bien |
|---|---|---|---|---|---|---|---|---|---|---|
| train | native | 5243 | 4 | 205 | 2104 | 2930 | 24.0 | 43.0 | 169.0 | 1920x1080:4393;1280x720:664;640x360:7 |
| train | imgsz640 | 5243 | 1116 | 2491 | 753 | 883 | 8.0 | 14.3 | 80.9 | 1920x1080:4393;1280x720:664;640x360:7 |
| train | imgsz1280 | 5243 | 25 | 1091 | 2491 | 1636 | 16.0 | 28.7 | 161.8 | 1920x1080:4393;1280x720:664;640x360:7 |
| val | native | 2621 | 1 | 108 | 1095 | 1417 | 24.0 | 42.0 | 169.0 | 1920x1080:2197;1280x720:330;640x384:6 |
| val | imgsz640 | 2621 | 574 | 1238 | 350 | 459 | 8.0 | 14.0 | 83.0 | 1920x1080:2197;1280x720:330;640x384:6 |
| val | imgsz1280 | 2621 | 16 | 558 | 1238 | 809 | 16.0 | 28.0 | 166.0 | 1920x1080:2197;1280x720:330;640x384:6 |
| test | native | 2245 | 0 | 51 | 633 | 1561 | 26.0 | 55.0 | 259.6 | 1920x1080:1348;1280x720:879;960x720:8 |
| test | imgsz640 | 2245 | 309 | 813 | 334 | 789 | 9.0 | 20.0 | 130.0 | 1920x1080:1348;1280x720:879;960x720:8 |
| test | imgsz1280 | 2245 | 11 | 298 | 813 | 1123 | 18.0 | 40.0 | 260.0 | 1920x1080:1348;1280x720:879;960x720:8 |

## Chi so tong (nguong tin cay 0.25; anh/GT test; CPU)

| model | che do | imgsz | anh | GT | P | R | mAP50 | FP/100 anh | ms/anh (pre+inf+post) |
|---|---|---|---|---|---|---|---|---|---|
| old_finetune | full | 640 | 2200 | 2245 | 0.7143 | 0.3964 | 0.4090 | 16.18 | 19.5 |
| old_finetune | full | 1280 | 2200 | 2245 | 0.6678 | 0.4334 | 0.4427 | 22.00 | 51.7 |
| old_finetune | crop | 640 | 2166 | 2180 | 0.7336 | 0.4624 | 0.4743 | 16.90 | 22.8 |
| old_ai7 | full | 640 | 2200 | 2245 | 0.6382 | 0.4463 | 0.4402 | 25.82 | 26.1 |
| old_ai7 | full | 1280 | 2200 | 2245 | 0.7666 | 0.4535 | 0.5075 | 14.09 | 94.1 |
| old_ai7 | crop | 640 | 2166 | 2180 | 0.8593 | 0.3839 | 0.5013 | 6.33 | 33.1 |
| ft_v8n | full | 640 | 2200 | 2245 | 0.8021 | 0.7599 | 0.8083 | 19.14 | 27.0 |
| ft_v8n | full | 1280 | 2200 | 2245 | 0.7140 | 0.9096 | 0.9187 | 37.18 | 62.2 |
| ft_v8n | crop | 640 | 2166 | 2180 | 0.8519 | 0.9312 | 0.9463 | 16.30 | 29.6 |

## Chi so tong (nguong tin cay 0.1; anh/GT test; CPU)

| model | che do | imgsz | anh | GT | P | R | mAP50 | FP/100 anh | ms/anh (pre+inf+post) |
|---|---|---|---|---|---|---|---|---|---|
| old_finetune | full | 640 | 2200 | 2245 | 0.6174 | 0.4134 | 0.4090 | 26.14 | 19.5 |
| old_finetune | full | 1280 | 2200 | 2245 | 0.5431 | 0.4575 | 0.4427 | 39.27 | 51.7 |
| old_finetune | crop | 640 | 2166 | 2180 | 0.6409 | 0.4798 | 0.4743 | 27.05 | 22.8 |
| old_ai7 | full | 640 | 2200 | 2245 | 0.4518 | 0.4682 | 0.4402 | 57.95 | 26.1 |
| old_ai7 | full | 1280 | 2200 | 2245 | 0.5963 | 0.5198 | 0.5075 | 35.91 | 94.1 |
| old_ai7 | crop | 640 | 2166 | 2180 | 0.7628 | 0.4633 | 0.5013 | 14.50 | 33.1 |
| ft_v8n | full | 640 | 2200 | 2245 | 0.6172 | 0.8143 | 0.8083 | 51.55 | 27.0 |
| ft_v8n | full | 1280 | 2200 | 2245 | 0.4925 | 0.9332 | 0.9187 | 98.14 | 62.2 |
| ft_v8n | crop | 640 | 2166 | 2180 | 0.6972 | 0.9431 | 0.9463 | 41.23 | 29.6 |

## Recall theo nhom be rong (nguong 0.25). Co so "infer" = px sau khi dua ve imgsz; "native" = px goc

### co so infer

| model | che do | imgsz | nhom px | n GT | recall |
|---|---|---|---|---|---|
| old_finetune | full | 640 | <10 | 309 | 0.0388 |
| old_finetune | full | 640 | 10-20 | 813 | 0.2288 |
| old_finetune | full | 640 | 20-40 | 334 | 0.4611 |
| old_finetune | full | 640 | >40 | 789 | 0.6819 |
| old_finetune | full | 1280 | <10 | 15 | 0.0000 |
| old_finetune | full | 1280 | 10-20 | 294 | 0.1769 |
| old_finetune | full | 1280 | 20-40 | 813 | 0.3383 |
| old_finetune | full | 1280 | >40 | 1123 | 0.5752 |
| old_finetune | crop | 640 | <10 | 0 |  |
| old_finetune | crop | 640 | 10-20 | 51 | 0.0000 |
| old_finetune | crop | 640 | 20-40 | 667 | 0.3433 |
| old_finetune | crop | 640 | >40 | 1462 | 0.5328 |
| old_ai7 | full | 640 | <10 | 309 | 0.0000 |
| old_ai7 | full | 640 | 10-20 | 813 | 0.1611 |
| old_ai7 | full | 640 | 20-40 | 334 | 0.5389 |
| old_ai7 | full | 640 | >40 | 789 | 0.8758 |
| old_ai7 | full | 1280 | <10 | 15 | 0.0000 |
| old_ai7 | full | 1280 | 10-20 | 294 | 0.0442 |
| old_ai7 | full | 1280 | 20-40 | 813 | 0.2903 |
| old_ai7 | full | 1280 | >40 | 1123 | 0.6848 |
| old_ai7 | crop | 640 | <10 | 0 |  |
| old_ai7 | crop | 640 | 10-20 | 51 | 0.0000 |
| old_ai7 | crop | 640 | 20-40 | 667 | 0.1349 |
| old_ai7 | crop | 640 | >40 | 1462 | 0.5109 |
| ft_v8n | full | 640 | <10 | 309 | 0.6505 |
| ft_v8n | full | 640 | 10-20 | 813 | 0.6482 |
| ft_v8n | full | 640 | 20-40 | 334 | 0.8353 |
| ft_v8n | full | 640 | >40 | 789 | 0.8859 |
| ft_v8n | full | 1280 | <10 | 15 | 1.0000 |
| ft_v8n | full | 1280 | 10-20 | 294 | 0.8810 |
| ft_v8n | full | 1280 | 20-40 | 813 | 0.9102 |
| ft_v8n | full | 1280 | >40 | 1123 | 0.9154 |
| ft_v8n | crop | 640 | <10 | 0 |  |
| ft_v8n | crop | 640 | 10-20 | 51 | 0.8627 |
| ft_v8n | crop | 640 | 20-40 | 667 | 0.9475 |
| ft_v8n | crop | 640 | >40 | 1462 | 0.9261 |

### co so native

| model | che do | imgsz | nhom px | n GT | recall |
|---|---|---|---|---|---|
| old_finetune | full | 640 | <10 | 0 |  |
| old_finetune | full | 640 | 10-20 | 51 | 0.0000 |
| old_finetune | full | 640 | 20-40 | 667 | 0.1514 |
| old_finetune | full | 640 | >40 | 1527 | 0.5167 |
| old_finetune | full | 1280 | <10 | 0 |  |
| old_finetune | full | 1280 | 10-20 | 51 | 0.0000 |
| old_finetune | full | 1280 | 20-40 | 667 | 0.2849 |
| old_finetune | full | 1280 | >40 | 1527 | 0.5128 |
| old_finetune | crop | 640 | <10 | 0 |  |
| old_finetune | crop | 640 | 10-20 | 51 | 0.0000 |
| old_finetune | crop | 640 | 20-40 | 667 | 0.3433 |
| old_finetune | crop | 640 | >40 | 1462 | 0.5328 |
| old_ai7 | full | 640 | <10 | 0 |  |
| old_ai7 | full | 640 | 10-20 | 51 | 0.0000 |
| old_ai7 | full | 640 | 20-40 | 667 | 0.0780 |
| old_ai7 | full | 640 | >40 | 1527 | 0.6221 |
| old_ai7 | full | 1280 | <10 | 0 |  |
| old_ai7 | full | 1280 | 10-20 | 51 | 0.0000 |
| old_ai7 | full | 1280 | 20-40 | 667 | 0.1574 |
| old_ai7 | full | 1280 | >40 | 1527 | 0.5979 |
| old_ai7 | crop | 640 | <10 | 0 |  |
| old_ai7 | crop | 640 | 10-20 | 51 | 0.0000 |
| old_ai7 | crop | 640 | 20-40 | 667 | 0.1349 |
| old_ai7 | crop | 640 | >40 | 1462 | 0.5109 |
| ft_v8n | full | 640 | <10 | 0 |  |
| ft_v8n | full | 640 | 10-20 | 51 | 0.6667 |
| ft_v8n | full | 640 | 20-40 | 667 | 0.6477 |
| ft_v8n | full | 640 | >40 | 1527 | 0.8120 |
| ft_v8n | full | 1280 | <10 | 0 |  |
| ft_v8n | full | 1280 | 10-20 | 51 | 0.9216 |
| ft_v8n | full | 1280 | 20-40 | 667 | 0.8951 |
| ft_v8n | full | 1280 | >40 | 1527 | 0.9155 |
| ft_v8n | crop | 640 | <10 | 0 |  |
| ft_v8n | crop | 640 | 10-20 | 51 | 0.8627 |
| ft_v8n | crop | 640 | 20-40 | 667 | 0.9475 |
| ft_v8n | crop | 640 | >40 | 1462 | 0.9261 |

## Sai so be rong khung bao (phat hien dung, IoU>=0.5; nguong 0.25; px goc)

| model | che do | imgsz | nhom px goc | n | trung vi |loi| px | p90 |loi| px | trung vi |loi| % | p90 |loi| % | lech co dau % |
|---|---|---|---|---|---|---|---|---|---|
| old_finetune | full | 640 | all | 890 | 7.74 | 25.54 | 7.28 | 22.87 | 3.65 |
| old_finetune | full | 640 | 20-40 | 101 | 7.26 | 13.21 | 21.26 | 39.17 | 21.26 |
| old_finetune | full | 640 | >40 | 789 | 8.07 | 27.57 | 6.77 | 19.64 | 2.28 |
| old_finetune | full | 1280 | all | 973 | 6.77 | 21.35 | 8.44 | 25.14 | 5.68 |
| old_finetune | full | 1280 | 20-40 | 190 | 6.64 | 10.47 | 21.49 | 32.54 | 21.49 |
| old_finetune | full | 1280 | >40 | 783 | 6.94 | 24.04 | 6.36 | 19.43 | 3.40 |
| old_finetune | crop | 640 | all | 1008 | 6.37 | 21.57 | 9.73 | 25.18 | 7.45 |
| old_finetune | crop | 640 | 20-40 | 229 | 5.83 | 9.66 | 19.08 | 31.99 | 19.08 |
| old_finetune | crop | 640 | >40 | 779 | 6.61 | 24.00 | 7.19 | 19.99 | 4.09 |
| old_ai7 | full | 640 | all | 1002 | 13.26 | 32.87 | 11.57 | 26.86 | 11.07 |
| old_ai7 | full | 640 | 20-40 | 52 | 8.68 | 12.24 | 24.75 | 36.82 | 24.75 |
| old_ai7 | full | 640 | >40 | 950 | 13.87 | 33.72 | 11.11 | 25.57 | 10.42 |
| old_ai7 | full | 1280 | all | 1018 | 8.52 | 28.36 | 10.28 | 23.74 | 8.97 |
| old_ai7 | full | 1280 | 20-40 | 105 | 7.09 | 10.60 | 21.47 | 31.89 | 21.47 |
| old_ai7 | full | 1280 | >40 | 913 | 8.75 | 30.43 | 8.77 | 21.21 | 7.71 |
| old_ai7 | crop | 640 | all | 837 | 8.33 | 29.91 | 9.40 | 22.74 | 8.60 |
| old_ai7 | crop | 640 | 20-40 | 90 | 6.89 | 10.73 | 21.84 | 30.35 | 21.84 |
| old_ai7 | crop | 640 | >40 | 747 | 8.55 | 30.99 | 8.43 | 19.47 | 7.40 |
| ft_v8n | full | 640 | all | 1706 | 4.60 | 19.05 | 6.04 | 20.05 | -1.94 |
| ft_v8n | full | 640 | 10-20 | 34 | 2.33 | 5.68 | 14.25 | 40.05 | 14.25 |
| ft_v8n | full | 640 | 20-40 | 432 | 2.73 | 7.13 | 8.44 | 21.88 | -4.58 |
| ft_v8n | full | 640 | >40 | 1240 | 5.51 | 25.40 | 5.21 | 17.92 | -1.56 |
| ft_v8n | full | 1280 | all | 2042 | 2.97 | 19.08 | 4.94 | 16.81 | -1.09 |
| ft_v8n | full | 1280 | 10-20 | 47 | 1.88 | 3.53 | 10.00 | 21.70 | 7.32 |
| ft_v8n | full | 1280 | 20-40 | 597 | 1.82 | 5.29 | 5.85 | 17.13 | -0.87 |
| ft_v8n | full | 1280 | >40 | 1398 | 3.87 | 29.85 | 4.43 | 16.35 | -1.17 |
| ft_v8n | crop | 640 | all | 2030 | 2.64 | 19.10 | 4.44 | 17.45 | 0.74 |
| ft_v8n | crop | 640 | 10-20 | 44 | 2.52 | 6.01 | 14.70 | 31.61 | 14.70 |
| ft_v8n | crop | 640 | 20-40 | 632 | 1.63 | 5.63 | 5.48 | 18.91 | 1.81 |
| ft_v8n | crop | 640 | >40 | 1354 | 3.41 | 29.71 | 3.98 | 14.76 | 0.09 |

## Quet kich thuoc tong hop (thu nho anh de muc tieu rong tw px, dat tren khung 640x640 xam, nguong 0.25)

Recall (P / FP tren 100 anh) theo be rong muc tieu tw (px, o khung 640 goc truoc khi phong len imgsz).

| model | imgsz | 6px | 8px | 10px | 12px | 15px | 20px | 30px | 40px |
|---|---|---|---|---|---|---|---|---|---|
| old_finetune | 640 | 0.01 (0.0656/9.30) | 0.04 (0.3333/7.83) | 0.09 (0.4876/10.11) | 0.15 (0.5482/12.23) | 0.23 (0.7073/9.79) | 0.35 (0.8321/7.18) | 0.45 (0.8274/9.46) | 0.50 (0.8591/8.32) |
| old_finetune | 1280 | 0.05 (0.4783/5.87) | 0.09 (0.5577/7.50) | 0.16 (0.6871/7.50) | 0.23 (0.8077/5.71) | 0.33 (0.8856/4.40) | 0.39 (0.9179/3.59) | 0.45 (0.9493/2.45) | 0.47 (0.9182/4.24) |
| old_ai7 | 640 | 0.00 (0.0667/6.85) | 0.02 (0.1370/10.28) | 0.07 (0.3060/15.17) | 0.10 (0.3916/16.48) | 0.19 (0.5426/16.64) | 0.31 (0.6498/16.97) | 0.47 (0.7723/14.19) | 0.55 (0.8927/6.69) |
| old_ai7 | 1280 | 0.03 (0.4595/3.26) | 0.09 (0.6154/5.71) | 0.14 (0.7131/5.71) | 0.20 (0.7267/7.67) | 0.30 (0.8274/6.36) | 0.38 (0.8281/7.99) | 0.52 (0.8798/7.18) | 0.59 (0.8968/6.85) |
| ft_v8n | 640 | 0.07 (0.2699/19.41) | 0.16 (0.4780/17.46) | 0.22 (0.5855/15.82) | 0.30 (0.6574/16.15) | 0.41 (0.7393/14.85) | 0.56 (0.8000/14.36) | 0.75 (0.8776/10.60) | 0.83 (0.8895/10.44) |
| ft_v8n | 1280 | 0.22 (0.6798/10.60) | 0.33 (0.7753/9.79) | 0.46 (0.8286/9.79) | 0.58 (0.8599/9.62) | 0.69 (0.8832/9.30) | 0.77 (0.9127/7.50) | 0.83 (0.8693/12.72) | 0.86 (0.8510/15.33) |

Recall chi cua muc tieu chinh (nguong 0.25):

| model | imgsz | 6px | 8px | 10px | 12px | 15px | 20px | 30px | 40px |
|---|---|---|---|---|---|---|---|---|---|
| old_finetune | 640 | 0.01 (n=613) | 0.04 (n=613) | 0.09 (n=613) | 0.15 (n=613) | 0.23 (n=613) | 0.34 (n=613) | 0.45 (n=613) | 0.50 (n=613) |
| old_finetune | 1280 | 0.05 (n=613) | 0.09 (n=613) | 0.16 (n=613) | 0.23 (n=613) | 0.33 (n=613) | 0.39 (n=613) | 0.45 (n=613) | 0.47 (n=613) |
| old_ai7 | 640 | 0.00 (n=613) | 0.02 (n=613) | 0.07 (n=613) | 0.10 (n=613) | 0.19 (n=613) | 0.31 (n=613) | 0.47 (n=613) | 0.55 (n=613) |
| old_ai7 | 1280 | 0.03 (n=613) | 0.09 (n=613) | 0.14 (n=613) | 0.19 (n=613) | 0.30 (n=613) | 0.37 (n=613) | 0.52 (n=613) | 0.59 (n=613) |
| ft_v8n | 640 | 0.07 (n=613) | 0.16 (n=613) | 0.22 (n=613) | 0.31 (n=613) | 0.41 (n=613) | 0.56 (n=613) | 0.75 (n=613) | 0.83 (n=613) |
| ft_v8n | 1280 | 0.22 (n=613) | 0.33 (n=613) | 0.46 (n=613) | 0.58 (n=613) | 0.69 (n=613) | 0.77 (n=613) | 0.84 (n=613) | 0.86 (n=613) |

Be rong nho nhat co recall >= 0.90 (trong cac muc da quet; trong = khong dat o muc nao):

| model | imgsz | tw nho nhat (px) |
|---|---|---|
| old_finetune | 640 |  |
| old_finetune | 1280 |  |
| old_ai7 | 640 |  |
| old_ai7 | 1280 |  |
| ft_v8n | 640 |  |
| ft_v8n | 1280 |  |

## Sai so be rong theo tw (quet; px goc = px khung 640)

| model | imgsz | tw | n | trung vi |loi| px | p90 |loi| px | trung vi |loi| % | p90 |loi| % | lech co dau % |
|---|---|---|---|---|---|---|---|---|
| old_finetune | 640 | 6 | 4 | 1.50 | 2.50 | 24.92 | 41.70 | 24.92 |
| old_finetune | 640 | 8 | 24 | 1.76 | 2.90 | 21.97 | 32.83 | 15.28 |
| old_finetune | 640 | 10 | 59 | 1.37 | 3.16 | 13.67 | 31.64 | 9.87 |
| old_finetune | 640 | 12 | 91 | 1.71 | 4.22 | 14.23 | 33.61 | 11.49 |
| old_finetune | 640 | 15 | 145 | 1.86 | 4.46 | 12.34 | 28.60 | 11.04 |
| old_finetune | 640 | 20 | 218 | 2.14 | 5.26 | 10.64 | 26.10 | 8.38 |
| old_finetune | 640 | 30 | 278 | 2.42 | 6.05 | 8.03 | 20.15 | 4.50 |
| old_finetune | 640 | 40 | 311 | 3.25 | 7.84 | 8.12 | 19.59 | 4.56 |
| old_finetune | 1280 | 6 | 33 | 1.03 | 2.65 | 15.50 | 44.16 | 11.88 |
| old_finetune | 1280 | 8 | 58 | 1.28 | 2.61 | 15.67 | 32.58 | 11.83 |
| old_finetune | 1280 | 10 | 101 | 1.75 | 3.29 | 16.37 | 32.69 | 14.48 |
| old_finetune | 1280 | 12 | 147 | 1.56 | 3.62 | 12.83 | 30.92 | 11.57 |
| old_finetune | 1280 | 15 | 209 | 1.57 | 3.47 | 10.40 | 23.15 | 7.84 |
| old_finetune | 1280 | 20 | 246 | 1.82 | 4.01 | 8.90 | 20.06 | 5.55 |
| old_finetune | 1280 | 30 | 281 | 2.48 | 6.00 | 8.35 | 20.01 | 3.41 |
| old_finetune | 1280 | 40 | 292 | 2.71 | 7.45 | 6.77 | 18.30 | 2.58 |
| old_ai7 | 640 | 6 | 3 | 2.18 | 2.91 | 36.35 | 48.43 | 36.35 |
| old_ai7 | 640 | 8 | 10 | 1.21 | 2.12 | 15.18 | 26.45 | 15.18 |
| old_ai7 | 640 | 10 | 41 | 2.36 | 4.23 | 23.61 | 42.31 | 23.61 |
| old_ai7 | 640 | 12 | 65 | 2.84 | 5.25 | 22.90 | 43.77 | 22.90 |
| old_ai7 | 640 | 15 | 121 | 3.22 | 5.63 | 21.45 | 37.51 | 21.45 |
| old_ai7 | 640 | 20 | 193 | 3.62 | 7.31 | 18.28 | 36.55 | 18.28 |
| old_ai7 | 640 | 30 | 295 | 4.66 | 9.10 | 15.55 | 29.63 | 15.55 |
| old_ai7 | 640 | 40 | 341 | 5.09 | 10.46 | 13.03 | 25.94 | 12.68 |
| old_ai7 | 1280 | 6 | 17 | 1.06 | 2.49 | 17.71 | 41.58 | 17.71 |
| old_ai7 | 1280 | 8 | 56 | 1.80 | 2.89 | 22.42 | 36.10 | 22.42 |
| old_ai7 | 1280 | 10 | 87 | 1.78 | 3.65 | 17.09 | 36.45 | 17.09 |
| old_ai7 | 1280 | 12 | 125 | 2.07 | 4.17 | 17.23 | 34.55 | 17.23 |
| ft_v8n | 640 | 6 | 44 | 0.49 | 1.73 | 8.15 | 28.90 | 5.65 |
| ft_v8n | 640 | 8 | 98 | 0.74 | 2.06 | 9.26 | 25.81 | -2.19 |
| ft_v8n | 640 | 10 | 137 | 1.24 | 2.79 | 11.31 | 27.36 | -3.56 |
| ft_v8n | 640 | 12 | 190 | 1.29 | 3.40 | 10.63 | 27.14 | -3.86 |
| ft_v8n | 640 | 15 | 258 | 1.17 | 3.25 | 7.79 | 21.26 | -1.23 |
| ft_v8n | 640 | 20 | 352 | 1.51 | 3.92 | 7.54 | 19.33 | -2.83 |
| ft_v8n | 640 | 30 | 466 | 1.62 | 5.02 | 5.38 | 16.55 | -1.40 |
| old_ai7 | 1280 | 15 | 187 | 2.41 | 4.95 | 15.96 | 31.64 | 15.96 |
| ft_v8n | 640 | 40 | 515 | 1.98 | 6.64 | 4.95 | 16.42 | -0.08 |
| ft_v8n | 1280 | 6 | 138 | 0.63 | 1.64 | 10.58 | 26.14 | -5.80 |
| ft_v8n | 1280 | 8 | 207 | 0.66 | 1.96 | 8.20 | 24.45 | -3.86 |
| ft_v8n | 1280 | 10 | 290 | 0.81 | 2.24 | 8.14 | 22.27 | -4.11 |
| ft_v8n | 1280 | 12 | 362 | 0.92 | 2.58 | 7.67 | 21.47 | -3.60 |
| old_ai7 | 1280 | 20 | 236 | 2.81 | 5.85 | 13.86 | 29.25 | 13.62 |
| ft_v8n | 1280 | 15 | 431 | 1.07 | 2.86 | 7.11 | 19.04 | -2.80 |
| ft_v8n | 1280 | 20 | 481 | 1.12 | 3.54 | 5.72 | 17.71 | -1.81 |
| ft_v8n | 1280 | 30 | 519 | 1.39 | 4.13 | 4.65 | 13.78 | -0.34 |
| ft_v8n | 1280 | 40 | 537 | 1.60 | 5.48 | 4.00 | 14.04 | -0.63 |
| old_ai7 | 1280 | 30 | 322 | 3.92 | 7.09 | 13.12 | 23.62 | 12.95 |
| old_ai7 | 1280 | 40 | 365 | 4.03 | 8.81 | 10.07 | 22.02 | 9.71 |
