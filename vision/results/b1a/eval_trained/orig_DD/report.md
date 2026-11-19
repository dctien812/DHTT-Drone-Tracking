# Cham ORIG_DD (CPU, 8 luong), nguong chon tren val = 0.065 (val: 506 pos, 506 bg), test: 8552 khung pos / 8552 vung bg, 6 doan, 30 khung/giay (gia dinh)


## nguong 0.065
| dai | n | recall | lo | hi |
|---|---|---|---|---|
| 16-57 | 1203 | 0.561 | 0.513 | 0.699 |
| 57-200 | 6778 | 0.756 | 0.590 | 0.899 |
| >200 | 571 | 0.855 | 0.801 | 0.905 |
| all | 8552 | 0.735 | 0.594 | 0.868 |
- Top_Down: 16-57=0.886 (n=70), 57-200=0.613 (n=2519), >200=0.841 (n=132), all=0.631 (n=2721)
- Horizontal: 16-57=0.536 (n=696), 57-200=0.706 (n=1809), >200=0.849 (n=272), all=0.678 (n=2777)
- Bottom_Up: 16-57=0.549 (n=437), 57-200=0.939 (n=2450), >200=0.874 (n=167), all=0.880 (n=3054)
- doan D'/Bottom_Up: all=0.736 (n=1389)
- doan D'/Horizontal: all=0.503 (n=1352)
- doan D'/Top_Down: all=0.695 (n=1797)
- doan D/Bottom_Up: all=1.000 (n=1665)
- doan D/Horizontal: all=0.844 (n=1425)
- doan D/Top_Down: all=0.508 (n=924)
A2: cum>=0.25s 68 (14.31/phut), cum>=3s 1, dai nhat 3.97s, tong 285s
A3 test_bg sky: 25/3054 vung co BDG (0.82/100)
A3 test_bg all: 154/8552 vung co BDG (1.80/100)
A3 test_bg mixed: 77/2777 vung co BDG (2.77/100)
A3 test_bg ground: 52/2721 vung co BDG (1.91/100)
A3 birds bird: 6/150 vung co BDG (4.00/100)
A3 birds all: 6/150 vung co BDG (4.00/100)
A4 fps30 all: model 0.647, tran 0.813, ti so 0.796
A4 fps30 top1: model 0.647, tran 0.813, ti so 0.796
A4 fps15 all: model 0.671, tran 0.897, ti so 0.748
A4 fps15 top1: model 0.670, tran 0.897, ti so 0.747

## nguong 0.25
| dai | n | recall | lo | hi |
|---|---|---|---|---|
| 16-57 | 1203 | 0.529 | 0.488 | 0.654 |
| 57-200 | 6778 | 0.692 | 0.488 | 0.873 |
| >200 | 571 | 0.793 | 0.682 | 0.874 |
| all | 8552 | 0.676 | 0.505 | 0.850 |
- Top_Down: 16-57=0.814 (n=70), 57-200=0.500 (n=2519), >200=0.644 (n=132), all=0.515 (n=2721)
- Horizontal: 16-57=0.506 (n=696), 57-200=0.650 (n=1809), >200=0.820 (n=272), all=0.630 (n=2777)
- Bottom_Up: 16-57=0.519 (n=437), 57-200=0.921 (n=2450), >200=0.868 (n=167), all=0.861 (n=3054)
- doan D'/Bottom_Up: all=0.693 (n=1389)
- doan D'/Horizontal: all=0.419 (n=1352)
- doan D'/Top_Down: all=0.568 (n=1797)
- doan D/Bottom_Up: all=1.000 (n=1665)
- doan D/Horizontal: all=0.831 (n=1425)
- doan D/Top_Down: all=0.411 (n=924)
A2: cum>=0.25s 74 (15.58/phut), cum>=3s 2, dai nhat 5.40s, tong 285s
A3 test_bg sky: 3/3054 vung co BDG (0.10/100)
A3 test_bg all: 16/8552 vung co BDG (0.19/100)
A3 test_bg mixed: 10/2777 vung co BDG (0.36/100)
A3 test_bg ground: 3/2721 vung co BDG (0.11/100)
A3 birds bird: 5/150 vung co BDG (3.33/100)
A3 birds all: 5/150 vung co BDG (3.33/100)
A4 fps30 all: model 0.647, tran 0.813, ti so 0.796
A4 fps30 top1: model 0.647, tran 0.813, ti so 0.796
A4 fps15 all: model 0.671, tran 0.897, ti so 0.748
A4 fps15 top1: model 0.670, tran 0.897, ti so 0.747

## nguong 0.12
| dai | n | recall | lo | hi |
|---|---|---|---|---|
| 16-57 | 1203 | 0.550 | 0.506 | 0.683 |
| 57-200 | 6778 | 0.728 | 0.542 | 0.890 |
| >200 | 571 | 0.839 | 0.782 | 0.895 |
| all | 8552 | 0.711 | 0.554 | 0.862 |
- Top_Down: 16-57=0.857 (n=70), 57-200=0.565 (n=2519), >200=0.803 (n=132), all=0.584 (n=2721)
- Horizontal: 16-57=0.526 (n=696), 57-200=0.678 (n=1809), >200=0.838 (n=272), all=0.656 (n=2777)
- Bottom_Up: 16-57=0.540 (n=437), 57-200=0.933 (n=2450), >200=0.868 (n=167), all=0.873 (n=3054)
- doan D'/Bottom_Up: all=0.721 (n=1389)
- doan D'/Horizontal: all=0.462 (n=1352)
- doan D'/Top_Down: all=0.646 (n=1797)
- doan D/Bottom_Up: all=1.000 (n=1665)
- doan D/Horizontal: all=0.839 (n=1425)
- doan D/Top_Down: all=0.464 (n=924)
A2: cum>=0.25s 71 (14.94/phut), cum>=3s 1, dai nhat 5.03s, tong 285s
A3 test_bg sky: 9/3054 vung co BDG (0.29/100)
A3 test_bg all: 61/8552 vung co BDG (0.71/100)
A3 test_bg mixed: 36/2777 vung co BDG (1.30/100)
A3 test_bg ground: 16/2721 vung co BDG (0.59/100)
A3 birds bird: 5/150 vung co BDG (3.33/100)
A3 birds all: 5/150 vung co BDG (3.33/100)
A4 fps30 all: model 0.647, tran 0.813, ti so 0.796
A4 fps30 top1: model 0.647, tran 0.813, ti so 0.796
A4 fps15 all: model 0.671, tran 0.897, ti so 0.748
A4 fps15 top1: model 0.670, tran 0.897, ti so 0.747

Thoi gian suy luan CPU: {"val_pos": 28.79, "val_bg": 28.81, "birds": 34.21, "test_pos": 20.18, "test_bg": 20.18} (ms/o)
