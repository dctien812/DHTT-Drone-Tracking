# S3 - SO SO BO, CHE DO NHE (khong ket luan dat/khong dat)
NCNN, 60 khung x 5 video = 300 khung/dong, tang tai bang taskset 1 -> 2 -> 3 nhan (khong dung 4). Chi ghi trong ~/dtrack tren Pi.
Dang tai tu pi\results\light.csv (day du cot EXT5V, nhiet, quat, co throttled), mon_light.log (2 giay/lan).
| nhan | imgsz | khung/s | e2e trung vi/p95 ms | RSS MB | EXT5V min V | nhiet max C | quat rpm max |
| 1 | 640 | 8.14 | 122.1/125.9 | 928 | 4.866 | 47.2 | 0 |
| 1 | 480 | 14.28 | 69.4/72.6 | 892 | 4.888 | 50.5 | 2585 |
| 1 | 320 | 27.94 | 35.3/37.1 | 870 | 4.887 | 50.5 | 2176 |
| 2 | 640 | 11.04 | 90.1/93.9 | 933 | 4.801 | 55.4 | 2820 |
| 2 | 480 | 19.67 | 50.4/52.9 | 896 | 4.804 | 54.3 | 2880 |
| 2 | 320 | 37.77 | 26.1/27.6 | 874 | 4.887 | 53.2 | 2920 |
| 3 | 640 | 11.47 | 86.6/89.7 | 937 | 4.726 | 57.1 | 2925 |
| 3 | 480 | 20.82 | 47.5/49.8 | 899 | 4.738 | 56.5 | 2955 |
| 3 | 320 | 41.48 | 23.7/25.2 | 877 | (>=4.726) | 55.4 | (xem csv) |
Co throttled tat ca 0x0 (khong thieu ap hien tai, khong sticky). Bo dung o 3 nhan vi EXT5V min 4.726 < 4.75. 4 nhan khong chay.
Quat: quay khi nong. fan1_input = 0 luc <50C, 2176-2985 rpm khi >=50C, cur_state=1.
Ty le co phat hien (conf 0.25): 640 0.997, 480 0.98, 320 0.90.
Lan truoc (4 nhan, from_pi_run1/run2): EXT5V min 4.657-4.80 V, co 0x5, NCNN 640 11.27, 480 22.09, 320 44.17 khung/s: danh dau thieu ap.
Ghi chu: NCNN chi tan dung ~2 nhan hieu dung (CPU 209% khi 3 nhan), nen 3 nhan ~ 2 nhan.
Chua do: 4 nhan, ONNX/OpenVINO/.pt, chay ben 30 phut, so voi .pt, mo xem anh khung bao.