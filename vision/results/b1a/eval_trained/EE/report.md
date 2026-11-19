# Cham EE (CPU, 8 luong), nguong chon tren val = 0.095 (val: 428 pos, 428 bg), test: 10103 khung pos / 10103 vung bg, 6 doan, 30 khung/giay (gia dinh)


## nguong 0.095
| dai | n | recall | lo | hi |
|---|---|---|---|---|
| 16-57 | 2605 | 0.770 | 0.381 | 0.989 |
| 57-200 | 7317 | 0.589 | 0.297 | 0.905 |
| >200 | 181 | 0.608 | n/a | n/a |
| all | 10103 | 0.636 | 0.322 | 0.931 |
- Top_Down: 16-57=0.126 (n=643), 57-200=0.132 (n=2899), >200=0.000 (n=59), all=0.129 (n=3601)
- Horizontal: 16-57=0.942 (n=640), 57-200=0.797 (n=2349), >200=0.902 (n=122), all=0.831 (n=3111)
- Bottom_Up: 16-57=1.000 (n=1322), 57-200=0.992 (n=2069), >200=n/a (n=0), all=0.995 (n=3391)
- doan E'/Bottom_Up: all=0.999 (n=1709)
- doan E'/Horizontal: all=0.871 (n=1492)
- doan E'/Top_Down: all=0.184 (n=1802)
- doan E/Bottom_Up: all=0.991 (n=1682)
- doan E/Horizontal: all=0.795 (n=1619)
- doan E/Top_Down: all=0.074 (n=1799)
A2: cum>=0.25s 69 (12.29/phut), cum>=3s 11, dai nhat 11.97s, tong 337s
A3 test_bg sky: 7/3391 vung co BDG (0.21/100)
A3 test_bg all: 83/10103 vung co BDG (0.82/100)
A3 test_bg mixed: 34/3111 vung co BDG (1.09/100)
A3 test_bg ground: 42/3601 vung co BDG (1.17/100)
A3 birds bird: 7/150 vung co BDG (4.67/100)
A3 birds all: 7/150 vung co BDG (4.67/100)
A4 fps30 all: model 0.603, tran 0.894, ti so 0.675
A4 fps30 top1: model 0.603, tran 0.894, ti so 0.675
A4 fps15 all: model 0.612, tran 0.952, ti so 0.642
A4 fps15 top1: model 0.612, tran 0.952, ti so 0.642

## nguong 0.25
| dai | n | recall | lo | hi |
|---|---|---|---|---|
| 16-57 | 2605 | 0.757 | 0.351 | 0.987 |
| 57-200 | 7317 | 0.566 | 0.273 | 0.892 |
| >200 | 181 | 0.591 | n/a | n/a |
| all | 10103 | 0.616 | 0.294 | 0.920 |
- Top_Down: 16-57=0.079 (n=643), 57-200=0.097 (n=2899), >200=0.000 (n=59), all=0.092 (n=3601)
- Horizontal: 16-57=0.938 (n=640), 57-200=0.773 (n=2349), >200=0.877 (n=122), all=0.811 (n=3111)
- Bottom_Up: 16-57=0.999 (n=1322), 57-200=0.989 (n=2069), >200=n/a (n=0), all=0.993 (n=3391)
- doan E'/Bottom_Up: all=0.997 (n=1709)
- doan E'/Horizontal: all=0.858 (n=1492)
- doan E'/Top_Down: all=0.136 (n=1802)
- doan E/Bottom_Up: all=0.989 (n=1682)
- doan E/Horizontal: all=0.767 (n=1619)
- doan E/Top_Down: all=0.049 (n=1799)
A2: cum>=0.25s 56 (9.98/phut), cum>=3s 11, dai nhat 24.47s, tong 337s
A3 test_bg sky: 2/3391 vung co BDG (0.06/100)
A3 test_bg all: 25/10103 vung co BDG (0.25/100)
A3 test_bg mixed: 7/3111 vung co BDG (0.23/100)
A3 test_bg ground: 16/3601 vung co BDG (0.44/100)
A3 birds bird: 6/150 vung co BDG (4.00/100)
A3 birds all: 6/150 vung co BDG (4.00/100)
A4 fps30 all: model 0.603, tran 0.894, ti so 0.675
A4 fps30 top1: model 0.603, tran 0.894, ti so 0.675
A4 fps15 all: model 0.612, tran 0.952, ti so 0.642
A4 fps15 top1: model 0.612, tran 0.952, ti so 0.642

Thoi gian suy luan CPU: {"val_pos": 27.93, "val_bg": 27.17, "birds": 33.09, "test_pos": 29.09, "test_bg": 29.09} (ms/o)
