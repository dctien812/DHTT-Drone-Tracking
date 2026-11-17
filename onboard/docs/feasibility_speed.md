# Bang kha thi theo toc do (CHI TINH, khong mo phong)

Tao bang `python simtools/feasibility_table.py` (tu `onboard/`). Cong thuc va gia dinh:

- `d = v*tau + v^2/(2*a_chaser) - v^2/(2*a_target) + 2*sigma_r(d) + 8 m`; cot "dung tuc thi" bo so hang tru. `sigma_r(r) = r^2*sigma_px/(f*S)` tinh tai chinh `r = d` (giai phuong trinh bac hai, lay nghiem nho; "vo nghiem" = sigma_r tang nhanh hon d).
- `tau = 0.35 s` (tre thuan FC, SITL do 0.31-0.40 s), `a_chaser = 4.1 m/s^2` (gia toc phanh TB cua chaser trong SITL do 2.1-4.2, `out/20261117_054730_fcstep`). **Day la so cua SITL (quad freestyle 0.8 kg), KHONG phai may that**; chi do o toc do <= 10 m/s, ngoai suy toi 111 m/s la gia dinh chua kiem.
- `sigma_px` hieu dung = **0.39 px**: lay tu so do B4 (khop gat, SITL): RMS sai so uoc luong khoang cach sau bo loc 0.20/0.39/1.15 m tai r = 15/25/40 m, quy ra `sigma_px = RMS*f*S/r^2` voi f = 1739 px, S = 0.30 m -> 0.46/0.33/0.37, lay trung binh. Bo phat hien cua B4 la TONG HOP (nhieu kich thuoc 1 px moi canh); bo nhan dien that chua do trong vong kin. Tham khao V1 (nhan dien tren anh, `vision/`): sai so be rong khung bao nhom 20-40 px trung vi 5.5%, phan vi 90 = 19% (lon hon nhieu so voi mo hinh tong hop), nen cot 'do nhay' ben duoi dung sigma_px = 1.0 px (khong loc) lam can tren.
- Bang 1 tinh sigma_r theo lens 6 mm (f = 1739 px, lens da do B4); cac bang anh/bang 3 dung sigma_r theo dung f cua tung lens (lens dai -> sigma_r nho hon). Cam bien 1456x1088, diem anh 3.45 um (5.02 x 3.75 mm); muc tieu 0.30 m; nguong nhan dien 20 px.

## Bang 1: khoang cach giu an toan (m), lens 6 mm

| v (m/s) | km/h | d, a_t=4 | d, a_t=8 | d, muc tieu dung tuc thi | sigma_r (a_t=8) | d, a_t=8 voi sigma_px=1.0 (can tren) |
|---|---|---|---|---|---|---|
| 10 | 36 | 11.4 | 17.9 | 24.6 | 0.24 | 18.8 |
| 20 | 72 | 14.1 | 41.3 | 71.4 | 1.27 | 47.4 |
| 30 | 108 | 16.1 | 82.0 | 172.5 | 5.00 | vo nghiem |
| 50 | 180 | 18.4 | vo nghiem | vo nghiem | - | vo nghiem |
| 70 | 252 | 18.0 | vo nghiem | vo nghiem | - | vo nghiem |
| 90 | 324 | 15.1 | vo nghiem | vo nghiem | - | vo nghiem |
| 111 | 400 | 9.4 | vo nghiem | vo nghiem | - | vo nghiem |

## Bang 2: FOV ngang x doc va tam xa nhat con >= 20 px

| lens (mm) | f (px) | FOV ngang x doc (do) | khoang cach xa nhat >= 20 px (m) |
|---|---|---|---|
| 6 | 1739 | 45.4 x 34.7 | 26.1 |
| 8 | 2319 | 34.9 x 26.4 | 34.8 |
| 12 | 3478 | 23.6 x 17.8 | 52.2 |
| 16 | 4638 | 17.8 x 13.4 | 69.6 |
| 25 | 7246 | 11.5 x 8.6 | 108.7 |

## Bang 3: be rong muc tieu 0.30 m trong anh (px) tai khoang cach an toan; dau V = >= 20 px, X = duoi nguong

### Muc tieu phanh: a_t=4 m/s^2

| v (m/s) | km/h | lens 6 mm (d m / px) | lens 8 mm (d m / px) | lens 12 mm (d m / px) | lens 16 mm (d m / px) | lens 25 mm (d m / px) |
|---|---|---|---|---|---|---|
| 10 | 36 | 11.4 / 45.8 V | 11.3 / 61.4 V | 11.3 / 92.4 V | 11.3 / 123.5 V | 11.2 / 193.4 V |
| 20 | 72 | 14.1 / 37.1 V | 14.0 / 49.7 V | 13.9 / 74.9 V | 13.9 / 100.2 V | 13.8 / 157.0 V |
| 30 | 108 | 16.1 / 32.3 V | 16.0 / 43.4 V | 15.9 / 65.4 V | 15.9 / 87.5 V | 15.8 / 137.2 V |
| 50 | 180 | 18.4 / 28.4 V | 18.2 / 38.1 V | 18.1 / 57.6 V | 18.1 / 77.0 V | 18.0 / 120.8 V |
| 70 | 252 | 18.0 / 28.9 V | 17.9 / 38.8 V | 17.8 / 58.6 V | 17.7 / 78.4 V | 17.7 / 123.0 V |
| 90 | 324 | 15.1 / 34.4 V | 15.1 / 46.2 V | 15.0 / 69.7 V | 14.9 / 93.2 V | 14.9 / 146.1 V |
| 111 | 400 | 9.4 / 55.4 V | 9.4 / 74.1 V | 9.4 / 111.6 V | 9.3 / 149.0 V | 9.3 / 233.3 V |

### Muc tieu phanh: a_t=8 m/s^2

| v (m/s) | km/h | lens 6 mm (d m / px) | lens 8 mm (d m / px) | lens 12 mm (d m / px) | lens 16 mm (d m / px) | lens 25 mm (d m / px) |
|---|---|---|---|---|---|---|
| 10 | 36 | 17.9 / 29.1 V | 17.8 / 39.1 V | 17.7 / 59.0 V | 17.6 / 79.0 V | 17.6 / 123.8 V |
| 20 | 72 | 41.3 / 12.6 X | 40.6 / 17.1 X | 40.0 / 26.1 V | 39.7 / 35.1 V | 39.3 / 55.3 V |
| 30 | 108 | 82.0 / 6.4 X | 79.0 / 8.8 X | 76.3 / 13.7 X | 75.2 / 18.5 X | 74.0 / 29.4 V |
| 50 | 180 | vo nghiem | 236.6 / 2.9 X | 205.6 / 5.1 X | 195.4 / 7.1 X | 186.6 / 11.7 X |
| 70 | 252 | vo nghiem | vo nghiem | 543.7 / 1.9 X | 424.2 / 3.3 X | 373.7 / 5.8 X |
| 90 | 324 | vo nghiem | vo nghiem | vo nghiem | vo nghiem | 692.1 / 3.1 X |
| 111 | 400 | vo nghiem | vo nghiem | vo nghiem | vo nghiem | vo nghiem |

### Muc tieu phanh: dung tuc thi

| v (m/s) | km/h | lens 6 mm (d m / px) | lens 8 mm (d m / px) | lens 12 mm (d m / px) | lens 16 mm (d m / px) | lens 25 mm (d m / px) |
|---|---|---|---|---|---|---|
| 10 | 36 | 24.6 / 21.2 V | 24.4 / 28.6 V | 24.1 / 43.2 V | 24.0 / 57.9 V | 23.9 / 91.0 V |
| 20 | 72 | 71.4 / 7.3 X | 69.1 / 10.1 X | 67.1 / 15.5 X | 66.2 / 21.0 V | 65.3 / 33.3 V |
| 30 | 108 | 172.5 / 3.0 X | 155.1 / 4.5 X | 143.6 / 7.3 X | 139.0 / 10.0 X | 134.7 / 16.1 X |
| 50 | 180 | vo nghiem | vo nghiem | 584.5 / 1.8 X | 436.8 / 3.2 X | 382.7 / 5.7 X |
| 70 | 252 | vo nghiem | vo nghiem | vo nghiem | vo nghiem | 957.2 / 2.3 X |
| 90 | 324 | vo nghiem | vo nghiem | vo nghiem | vo nghiem | vo nghiem |
| 111 | 400 | vo nghiem | vo nghiem | vo nghiem | vo nghiem | vo nghiem |

## Bang 4: toc do cao nhat ma khoang cach an toan con trong tam >= 20 px

| lens (mm) | tam xa nhat (m) | a_t=4: m/s (km/h) | a_t=8: m/s (km/h) | dung tuc thi: m/s (km/h) |
|---|---|---|---|---|
| 6 | 26.1 | 300.0 (1080) | 14.3 (51) | 10.5 (38) |
| 8 | 34.8 | 300.0 (1080) | 17.9 (65) | 13.1 (47) |
| 12 | 52.2 | 300.0 (1080) | 23.8 (86) | 17.2 (62) |
| 16 | 69.6 | 300.0 (1080) | 28.7 (103) | 20.6 (74) |
| 25 | 108.7 | 300.0 (1080) | 37.4 (135) | 26.7 (96) |

Ghi chu: ket qua la can tren ly thuyet theo mo hinh don gian (phanh deu, tre thuan co dinh, sigma_r dai dien cho sai so uoc luong khoang cach); khong xet nghieng than, FOV doc/ngang khi mat hinh, quang sai, rung camera, nhieu cua bo nhan dien that, gioi han v_max_mps = 30 cua cau hinh hien tai (`dtrack/config.py`), hay kha nang chaser tang toc duoi 111 m/s.
