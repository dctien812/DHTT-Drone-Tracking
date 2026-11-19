# Cham DD (CPU, 8 luong), nguong chon tren val = 0.085 (val: 506 pos, 506 bg), test: 8552 khung pos / 8552 vung bg, 6 doan, 30 khung/giay (gia dinh)


## nguong 0.085
| dai | n | recall | lo | hi |
|---|---|---|---|---|
| 16-57 | 1203 | 0.830 | 0.693 | 0.989 |
| 57-200 | 6778 | 0.786 | 0.600 | 0.934 |
| >200 | 571 | 0.630 | 0.279 | 0.852 |
| all | 8552 | 0.782 | 0.623 | 0.928 |
- Top_Down: 16-57=0.943 (n=70), 57-200=0.631 (n=2519), >200=0.144 (n=132), all=0.616 (n=2721)
- Horizontal: 16-57=0.723 (n=696), 57-200=0.730 (n=1809), >200=0.654 (n=272), all=0.721 (n=2777)
- Bottom_Up: 16-57=0.984 (n=437), 57-200=0.986 (n=2450), >200=0.976 (n=167), all=0.985 (n=3054)
- doan D'/Bottom_Up: all=0.968 (n=1389)
- doan D'/Horizontal: all=0.498 (n=1352)
- doan D'/Top_Down: all=0.658 (n=1797)
- doan D/Bottom_Up: all=0.999 (n=1665)
- doan D/Horizontal: all=0.932 (n=1425)
- doan D/Top_Down: all=0.532 (n=924)
A2: cum>=0.25s 36 (7.58/phut), cum>=3s 3, dai nhat 7.03s, tong 285s
A3 test_bg sky: 47/3054 vung co BDG (1.54/100)
A3 test_bg all: 165/8552 vung co BDG (1.93/100)
A3 test_bg mixed: 69/2777 vung co BDG (2.48/100)
A3 test_bg ground: 49/2721 vung co BDG (1.80/100)
A3 birds bird: 4/150 vung co BDG (2.67/100)
A3 birds all: 4/150 vung co BDG (2.67/100)
A4 fps30 all: model 0.675, tran 0.813, ti so 0.830
A4 fps30 top1: model 0.675, tran 0.813, ti so 0.830
A4 fps15 all: model 0.731, tran 0.897, ti so 0.815
A4 fps15 top1: model 0.730, tran 0.897, ti so 0.814

## nguong 0.25
| dai | n | recall | lo | hi |
|---|---|---|---|---|
| 16-57 | 1203 | 0.824 | 0.682 | 0.989 |
| 57-200 | 6778 | 0.764 | 0.567 | 0.924 |
| >200 | 571 | 0.608 | 0.202 | 0.849 |
| all | 8552 | 0.762 | 0.588 | 0.919 |
- Top_Down: 16-57=0.929 (n=70), 57-200=0.585 (n=2519), >200=0.045 (n=132), all=0.568 (n=2721)
- Horizontal: 16-57=0.713 (n=696), 57-200=0.718 (n=1809), >200=0.654 (n=272), all=0.710 (n=2777)
- Bottom_Up: 16-57=0.984 (n=437), 57-200=0.982 (n=2450), >200=0.976 (n=167), all=0.982 (n=3054)
- doan D'/Bottom_Up: all=0.961 (n=1389)
- doan D'/Horizontal: all=0.482 (n=1352)
- doan D'/Top_Down: all=0.615 (n=1797)
- doan D/Bottom_Up: all=0.999 (n=1665)
- doan D/Horizontal: all=0.928 (n=1425)
- doan D/Top_Down: all=0.475 (n=924)
A2: cum>=0.25s 36 (7.58/phut), cum>=3s 4, dai nhat 8.03s, tong 285s
A3 test_bg sky: 4/3054 vung co BDG (0.13/100)
A3 test_bg all: 43/8552 vung co BDG (0.50/100)
A3 test_bg mixed: 23/2777 vung co BDG (0.83/100)
A3 test_bg ground: 16/2721 vung co BDG (0.59/100)
A3 birds bird: 2/150 vung co BDG (1.33/100)
A3 birds all: 2/150 vung co BDG (1.33/100)
A4 fps30 all: model 0.675, tran 0.813, ti so 0.830
A4 fps30 top1: model 0.675, tran 0.813, ti so 0.830
A4 fps15 all: model 0.731, tran 0.897, ti so 0.815
A4 fps15 top1: model 0.730, tran 0.897, ti so 0.814

Thoi gian suy luan CPU: {"val_pos": 31.68, "val_bg": 22.83, "birds": 27.64, "test_pos": 20.5, "test_bg": 20.5} (ms/o)
