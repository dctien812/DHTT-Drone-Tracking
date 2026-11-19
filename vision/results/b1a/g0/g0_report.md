# G0 - yolov8n.pt goc (airplane) tren B1a

manifest sha256 7c67757cee4d2c3a81d3f87bc9d5519e5765c95f35e976a2178d48b07859e848 verify True; 30 khung/giay (gia dinh)

Nguong van hanh (chon tren VAL, FA val<=1/100): **0.12**; chi tiet: {"thr": 0.12, "val_fa_per_100": 0.8600469116497262, "val_fa_crops": 11, "val_recall": 0.7122752150117279, "val_recall_16-57": 0.6282722513089005, "val_recall_57-200": 0.7197265625, "val_recall_>200": 0.84375}

Anh da cham: {'test_pos': 10103, 'test_off': 10103, 'test_bg': 10103, 'val_pos': 1279, 'val_bg': 1279, 'birds': 150, 'train_pos': 1153}
Thoi gian suy luan (s): {'test_pos': 320.7, 'test_off': 319.9, 'test_bg': 316.9, 'val_pos': 44.7, 'val_bg': 33.3, 'birds': 4.1, 'train_pos': 37.7}
Truncated: {'test_pos': 0, 'test_off': 0, 'val_pos': 0, 'train_pos': 0}


## Nguong 0.12

### A1 test (recall IoU0.5; spread = bootstrap theo doan)
| dai | n | recall | lo | hi | n_nhom |
|---|---|---|---|---|---|
| 16-57 | 2605 | 0.763 | 0.465 | 0.924 | 6 |
| 57-200 | 7317 | 0.696 | 0.507 | 0.900 | 6 |
| >200 | 181 | 0.840 | n/a | n/a | 3 |
| all | 10103 | 0.716 | 0.502 | 0.907 | 6 |

A1 theo huong / doan (recall: 16-57, 57-200, >200, all)
- Top_Down: 16-57=0.306 (n=643), 57-200=0.420 (n=2899), >200=0.593 (n=59), all=0.402 (n=3601)
- Horizontal: 16-57=0.831 (n=640), 57-200=0.771 (n=2349), >200=0.959 (n=122), all=0.791 (n=3111)
- Bottom_Up: 16-57=0.952 (n=1322), 57-200=0.998 (n=2069), >200=n/a (n=0), all=0.980 (n=3391)
- E'/Bottom_Up: 16-57=0.946 (n=984), 57-200=1.000 (n=725), >200=n/a (n=0), all=0.969 (n=1709)
- E'/Horizontal: 16-57=0.831 (n=373), 57-200=0.836 (n=1114), >200=0.000 (n=5), all=0.832 (n=1492)
- E'/Top_Down: 16-57=0.406 (n=330), 57-200=0.489 (n=1413), >200=0.593 (n=59), all=0.477 (n=1802)
- E/Bottom_Up: 16-57=0.967 (n=338), 57-200=0.996 (n=1344), >200=n/a (n=0), all=0.990 (n=1682)
- E/Horizontal: 16-57=0.831 (n=267), 57-200=0.713 (n=1235), >200=1.000 (n=117), all=0.754 (n=1619)
- E/Top_Down: 16-57=0.201 (n=313), 57-200=0.354 (n=1486), >200=n/a (n=0), all=0.327 (n=1799)

A1 loai 28 khung: 16-57=0.761, 57-200=0.696, >200=0.840, all=0.715

### A2 (30 fps)
pooled: cum>=0.25s 68 (12.12/phut), cum>=3s 1, dai nhat 10.50s, tong 337s
- E'/Bottom_Up: cum>=0.25s 1, >=3s 0, dai nhat 0.30s, 1.05/phut
- E'/Horizontal: cum>=0.25s 6, >=3s 0, dai nhat 2.67s, 7.24/phut
- E'/Top_Down: cum>=0.25s 26, >=3s 0, dai nhat 1.83s, 25.97/phut
- E/Bottom_Up: cum>=0.25s 0, >=3s 0, dai nhat 0.13s, 0.00/phut
- E/Horizontal: cum>=0.25s 11, >=3s 0, dai nhat 1.43s, 12.23/phut
- E/Top_Down: cum>=0.25s 24, >=3s 1, dai nhat 10.50s, 24.01/phut

### A3 (bao dong gia theo vung; per_100)
- test_bg sky: 7/3391 vung co BDG (0.21/100), 7 phat hien, 0.062/s
- test_bg all: 37/10103 vung co BDG (0.37/100), 39 phat hien, 0.110/s
- test_bg mixed: 25/3111 vung co BDG (0.80/100), 26 phat hien, 0.241/s
- test_bg ground: 5/3601 vung co BDG (0.14/100), 6 phat hien, 0.042/s
- birds bird: 5/150 vung co BDG (3.33/100), 5 phat hien, 1.000/s
- birds all: 5/150 vung co BDG (3.33/100), 5 phat hien, 1.000/s
- val_bg sky: 1/457 vung co BDG (0.22/100), 1 phat hien, 0.066/s
- val_bg all: 11/1279 vung co BDG (0.86/100), 11 phat hien, 0.258/s
- val_bg mixed: 5/415 vung co BDG (1.20/100), 5 phat hien, 0.361/s
- val_bg ground: 5/407 vung co BDG (1.23/100), 5 phat hien, 0.369/s

### A4 (ti le bam)
- fps30 all: model 0.678, tran 0.894, ti so 0.759
- fps30 top1: model 0.677, tran 0.894, ti so 0.757
- fps15 all: model 0.683, tran 0.952, ti so 0.718
- fps15 top1: model 0.683, tran 0.952, ti so 0.718

### A5
lech tam: 16-57=0.728 (n=2605), 57-200=0.672 (n=7317), >200=0.856 (n=181), all=0.690 (n=10103)
quet 32 o (1013 khung): 16-57=0.837 (n=263), 57-200=0.754 (n=731), >200=0.895 (n=19), all=0.778 (n=1013); BDG/khung (khong chong lan) 0.134, (IoU<0.5) 0.341

### Doi chung (recall theo dai)
- D: 16-57=0.412 (n=17), 57-200=0.858 (n=1047), >200=0.907 (n=75), all=0.854 (n=1139)
- D': 16-57=0.620 (n=329), 57-200=0.568 (n=891), >200=0.781 (n=73), all=0.593 (n=1293)
- E: 16-57=0.667 (n=918), 57-200=0.676 (n=4065), >200=1.000 (n=117), all=0.681 (n=5100)
- E': 16-57=0.815 (n=1687), 57-200=0.722 (n=3252), >200=0.547 (n=64), all=0.751 (n=5003)

## Nguong 0.25

### A1 test (recall IoU0.5; spread = bootstrap theo doan)
| dai | n | recall | lo | hi | n_nhom |
|---|---|---|---|---|---|
| 16-57 | 2605 | 0.727 | 0.379 | 0.914 | 6 |
| 57-200 | 7317 | 0.648 | 0.428 | 0.885 | 6 |
| >200 | 181 | 0.785 | n/a | n/a | 3 |
| all | 10103 | 0.671 | 0.430 | 0.894 | 6 |

A1 theo huong / doan (recall: 16-57, 57-200, >200, all)
- Top_Down: 16-57=0.198 (n=643), 57-200=0.325 (n=2899), >200=0.441 (n=59), all=0.304 (n=3601)
- Horizontal: 16-57=0.809 (n=640), 57-200=0.738 (n=2349), >200=0.951 (n=122), all=0.761 (n=3111)
- Bottom_Up: 16-57=0.946 (n=1322), 57-200=0.998 (n=2069), >200=n/a (n=0), all=0.977 (n=3391)
- E'/Bottom_Up: 16-57=0.939 (n=984), 57-200=1.000 (n=725), >200=n/a (n=0), all=0.965 (n=1709)
- E'/Horizontal: 16-57=0.799 (n=373), 57-200=0.812 (n=1114), >200=0.000 (n=5), all=0.806 (n=1492)
- E'/Top_Down: 16-57=0.297 (n=330), 57-200=0.377 (n=1413), >200=0.441 (n=59), all=0.364 (n=1802)
- E/Bottom_Up: 16-57=0.964 (n=338), 57-200=0.996 (n=1344), >200=n/a (n=0), all=0.990 (n=1682)
- E/Horizontal: 16-57=0.824 (n=267), 57-200=0.670 (n=1235), >200=0.991 (n=117), all=0.719 (n=1619)
- E/Top_Down: 16-57=0.093 (n=313), 57-200=0.275 (n=1486), >200=n/a (n=0), all=0.243 (n=1799)

A1 loai 28 khung: 16-57=0.725, 57-200=0.648, >200=0.785, all=0.670

### A2 (30 fps)
pooled: cum>=0.25s 75 (13.36/phut), cum>=3s 6, dai nhat 11.13s, tong 337s
- E'/Bottom_Up: cum>=0.25s 2, >=3s 0, dai nhat 0.30s, 2.11/phut
- E'/Horizontal: cum>=0.25s 8, >=3s 0, dai nhat 2.67s, 9.65/phut
- E'/Top_Down: cum>=0.25s 27, >=3s 3, dai nhat 4.37s, 26.97/phut
- E/Bottom_Up: cum>=0.25s 0, >=3s 0, dai nhat 0.13s, 0.00/phut
- E/Horizontal: cum>=0.25s 14, >=3s 0, dai nhat 2.07s, 15.57/phut
- E/Top_Down: cum>=0.25s 24, >=3s 3, dai nhat 11.13s, 24.01/phut

### A3 (bao dong gia theo vung; per_100)
- test_bg sky: 3/3391 vung co BDG (0.09/100), 3 phat hien, 0.027/s
- test_bg all: 11/10103 vung co BDG (0.11/100), 11 phat hien, 0.033/s
- test_bg mixed: 8/3111 vung co BDG (0.26/100), 8 phat hien, 0.077/s
- test_bg ground: 0/3601 vung co BDG (0.00/100), 0 phat hien, 0.000/s
- birds bird: 5/150 vung co BDG (3.33/100), 5 phat hien, 1.000/s
- birds all: 5/150 vung co BDG (3.33/100), 5 phat hien, 1.000/s
- val_bg sky: 0/457 vung co BDG (0.00/100), 0 phat hien, 0.000/s
- val_bg all: 3/1279 vung co BDG (0.23/100), 3 phat hien, 0.070/s
- val_bg mixed: 2/415 vung co BDG (0.48/100), 2 phat hien, 0.145/s
- val_bg ground: 1/407 vung co BDG (0.25/100), 1 phat hien, 0.074/s

### A4 (ti le bam)
- fps30 all: model 0.678, tran 0.894, ti so 0.759
- fps30 top1: model 0.677, tran 0.894, ti so 0.757
- fps15 all: model 0.683, tran 0.952, ti so 0.718
- fps15 top1: model 0.683, tran 0.952, ti so 0.718

### A5
lech tam: 16-57=0.691 (n=2605), 57-200=0.622 (n=7317), >200=0.812 (n=181), all=0.643 (n=10103)
quet 32 o (1013 khung): 16-57=0.810 (n=263), 57-200=0.691 (n=731), >200=0.842 (n=19), all=0.725 (n=1013); BDG/khung (khong chong lan) 0.029, (IoU<0.5) 0.138

### Doi chung (recall theo dai)
- D: 16-57=0.412 (n=17), 57-200=0.846 (n=1047), >200=0.893 (n=75), all=0.843 (n=1139)
- D': 16-57=0.599 (n=329), 57-200=0.506 (n=891), >200=0.548 (n=73), all=0.532 (n=1293)
- E: 16-57=0.626 (n=918), 57-200=0.634 (n=4065), >200=0.991 (n=117), all=0.641 (n=5100)
- E': 16-57=0.782 (n=1687), 57-200=0.665 (n=3252), >200=0.406 (n=64), all=0.701 (n=5003)

## Nguong 0.1

### A1 test (recall IoU0.5; spread = bootstrap theo doan)
| dai | n | recall | lo | hi | n_nhom |
|---|---|---|---|---|---|
| 16-57 | 2605 | 0.771 | 0.486 | 0.925 | 6 |
| 57-200 | 7317 | 0.707 | 0.524 | 0.904 | 6 |
| >200 | 181 | 0.845 | n/a | n/a | 3 |
| all | 10103 | 0.726 | 0.518 | 0.910 | 6 |

A1 theo huong / doan (recall: 16-57, 57-200, >200, all)
- Top_Down: 16-57=0.334 (n=643), 57-200=0.441 (n=2899), >200=0.610 (n=59), all=0.425 (n=3601)
- Horizontal: 16-57=0.834 (n=640), 57-200=0.780 (n=2349), >200=0.959 (n=122), all=0.798 (n=3111)
- Bottom_Up: 16-57=0.952 (n=1322), 57-200=0.998 (n=2069), >200=n/a (n=0), all=0.980 (n=3391)
- E'/Bottom_Up: 16-57=0.947 (n=984), 57-200=1.000 (n=725), >200=n/a (n=0), all=0.970 (n=1709)
- E'/Horizontal: 16-57=0.834 (n=373), 57-200=0.842 (n=1114), >200=0.000 (n=5), all=0.837 (n=1492)
- E'/Top_Down: 16-57=0.421 (n=330), 57-200=0.517 (n=1413), >200=0.610 (n=59), all=0.502 (n=1802)
- E/Bottom_Up: 16-57=0.967 (n=338), 57-200=0.996 (n=1344), >200=n/a (n=0), all=0.990 (n=1682)
- E/Horizontal: 16-57=0.835 (n=267), 57-200=0.725 (n=1235), >200=1.000 (n=117), all=0.763 (n=1619)
- E/Top_Down: 16-57=0.243 (n=313), 57-200=0.369 (n=1486), >200=n/a (n=0), all=0.347 (n=1799)

A1 loai 28 khung: 16-57=0.769, 57-200=0.707, >200=0.845, all=0.726

### A2 (30 fps)
pooled: cum>=0.25s 69 (12.29/phut), cum>=3s 1, dai nhat 10.00s, tong 337s
- E'/Bottom_Up: cum>=0.25s 1, >=3s 0, dai nhat 0.27s, 1.05/phut
- E'/Horizontal: cum>=0.25s 6, >=3s 0, dai nhat 2.67s, 7.24/phut
- E'/Top_Down: cum>=0.25s 30, >=3s 0, dai nhat 1.83s, 29.97/phut
- E/Bottom_Up: cum>=0.25s 0, >=3s 0, dai nhat 0.13s, 0.00/phut
- E/Horizontal: cum>=0.25s 11, >=3s 0, dai nhat 1.43s, 12.23/phut
- E/Top_Down: cum>=0.25s 21, >=3s 1, dai nhat 10.00s, 21.01/phut

### A3 (bao dong gia theo vung; per_100)
- test_bg sky: 9/3391 vung co BDG (0.27/100), 9 phat hien, 0.080/s
- test_bg all: 50/10103 vung co BDG (0.49/100), 54 phat hien, 0.148/s
- test_bg mixed: 34/3111 vung co BDG (1.09/100), 37 phat hien, 0.328/s
- test_bg ground: 7/3601 vung co BDG (0.19/100), 8 phat hien, 0.058/s
- birds bird: 5/150 vung co BDG (3.33/100), 5 phat hien, 1.000/s
- birds all: 5/150 vung co BDG (3.33/100), 5 phat hien, 1.000/s
- val_bg sky: 2/457 vung co BDG (0.44/100), 2 phat hien, 0.131/s
- val_bg all: 14/1279 vung co BDG (1.09/100), 14 phat hien, 0.328/s
- val_bg mixed: 5/415 vung co BDG (1.20/100), 5 phat hien, 0.361/s
- val_bg ground: 7/407 vung co BDG (1.72/100), 7 phat hien, 0.516/s

### A4 (ti le bam)
- fps30 all: model 0.678, tran 0.894, ti so 0.759
- fps30 top1: model 0.677, tran 0.894, ti so 0.757
- fps15 all: model 0.683, tran 0.952, ti so 0.718
- fps15 top1: model 0.683, tran 0.952, ti so 0.718

### A5
lech tam: 16-57=0.736 (n=2605), 57-200=0.682 (n=7317), >200=0.856 (n=181), all=0.699 (n=10103)
quet 32 o (1013 khung): 16-57=0.848 (n=263), 57-200=0.762 (n=731), >200=0.895 (n=19), all=0.787 (n=1013); BDG/khung (khong chong lan) 0.183, (IoU<0.5) 0.417

### Doi chung (recall theo dai)
- D: 16-57=0.412 (n=17), 57-200=0.861 (n=1047), >200=0.907 (n=75), all=0.857 (n=1139)
- D': 16-57=0.620 (n=329), 57-200=0.586 (n=891), >200=0.795 (n=73), all=0.606 (n=1293)
- E: 16-57=0.682 (n=918), 57-200=0.685 (n=4065), >200=1.000 (n=117), all=0.691 (n=5100)
- E': 16-57=0.819 (n=1687), 57-200=0.736 (n=3252), >200=0.562 (n=64), all=0.762 (n=5003)

## Lop COCO tren may bay mo hinh (test pos)
```
{
 "0.01": {
  "frames_with_class_hit_iou0.5": {
   "airplane": 8246,
   "kite": 819,
   "boat": 483,
   "skateboard": 463,
   "person": 367,
   "bird": 229,
   "bench": 170,
   "truck": 162,
   "car": 145,
   "surfboard": 109,
   "traffic light": 85,
   "scissors": 84,
   "skis": 56,
   "bus": 49,
   "motorcycle": 48,
   "train": 36,
   "toothbrush": 36,
   "bicycle": 24,
   "baseball bat": 21,
   "sink": 20,
   "fire hydrant": 12,
   "umbrella": 7,
   "clock": 7,
   "giraffe": 7,
   "dining table": 7,
   "frisbee": 6,
   "bottle": 4,
   "chair": 3,
   "toilet": 3,
   "knife": 2,
   "sheep": 2,
   "snowboard": 2,
   "cell phone": 1,
   "parking meter": 1
  },
  "top_conf_class_among_hits": {
   "airplane": 7786,
   "none": 979,
   "kite": 307,
   "skateboard": 265,
   "boat": 227,
   "bird": 106,
   "bench": 104,
   "car": 66,
   "truck": 42,
   "person": 34,
   "bus": 32,
   "traffic light": 25,
   "surfboard": 21,
   "toothbrush": 19,
   "scissors": 16,
   "sink": 16,
   "train": 13,
   "skis": 11,
   "motorcycle": 7,
   "fire hydrant": 6,
   "bicycle": 5,
   "toilet": 3,
   "knife": 2,
   "sheep": 2,
   "dining table": 2,
   "umbrella": 2,
   "frisbee": 2,
   "baseball bat": 1,
   "snowboard": 1,
   "parking meter": 1
  },
  "bird_hits": 229,
  "kite_hits": 819,
  "airplane_hits": 8246,
  "n": 10103
 },
 "0.1": {
  "frames_with_class_hit_iou0.5": {
   "airplane": 7337,
   "kite": 555,
   "skateboard": 184,
   "boat": 151,
   "bird": 121,
   "person": 40,
   "surfboard": 36,
   "skis": 29,
   "truck": 28,
   "bench": 25,
   "scissors": 18,
   "car": 14,
   "bus": 13,
   "motorcycle": 5,
   "baseball bat": 4,
   "traffic light": 2,
   "toothbrush": 2,
   "frisbee": 2,
   "giraffe": 1,
   "sink": 1,
   "snowboard": 1,
   "umbrella": 1,
   "dining table": 1,
   "train": 1
  },
  "top_conf_class_among_hits": {
   "airplane": 7180,
   "none": 2179,
   "kite": 294,
   "skateboard": 146,
   "boat": 92,
   "bird": 81,
   "person": 24,
   "bench": 23,
   "surfboard": 15,
   "truck": 14,
   "car": 14,
   "bus": 13,
   "skis": 9,
   "scissors": 9,
   "motorcycle": 3,
   "traffic light": 2,
   "toothbrush": 2,
   "sink": 1,
   "umbrella": 1,
   "frisbee": 1
  },
  "bird_hits": 121,
  "kite_hits": 555,
  "airplane_hits": 7337,
  "n": 10103
 },
 "0.25": {
  "frames_with_class_hit_iou0.5": {
   "airplane": 6775,
   "kite": 375,
   "skateboard": 97,
   "bird": 72,
   "boat": 46,
   "person": 17,
   "surfboard": 15,
   "skis": 13,
   "bench": 4,
   "car": 2,
   "scissors": 1,
   "bus": 1,
   "truck": 1
  },
  "top_conf_class_among_hits": {
   "airplane": 6714,
   "none": 2917,
   "kite": 250,
   "skateboard": 90,
   "bird": 57,
   "boat": 33,
   "person": 15,
   "surfboard": 11,
   "skis": 7,
   "bench": 4,
   "car": 2,
   "scissors": 1,
   "bus": 1,
   "truck": 1
  },
  "bird_hits": 72,
  "kite_hits": 375,
  "airplane_hits": 6775,
  "n": 10103
 },
 "0.12": {
  "frames_with_class_hit_iou0.5": {
   "airplane": 7232,
   "kite": 523,
   "skateboard": 166,
   "boat": 124,
   "bird": 109,
   "person": 35,
   "surfboard": 28,
   "truck": 24,
   "skis": 23,
   "bench": 20,
   "scissors": 12,
   "bus": 9,
   "car": 7,
   "motorcycle": 4,
   "baseball bat": 3,
   "traffic light": 2,
   "toothbrush": 2,
   "frisbee": 2,
   "sink": 1,
   "umbrella": 1,
   "dining table": 1,
   "train": 1
  },
  "top_conf_class_among_hits": {
   "airplane": 7097,
   "none": 2324,
   "kite": 289,
   "skateboard": 134,
   "bird": 77,
   "boat": 73,
   "person": 22,
   "bench": 18,
   "surfboard": 15,
   "truck": 12,
   "skis": 9,
   "bus": 9,
   "car": 7,
   "scissors": 7,
   "motorcycle": 3,
   "traffic light": 2,
   "toothbrush": 2,
   "sink": 1,
   "umbrella": 1,
   "frisbee": 1
  },
  "bird_hits": 109,
  "kite_hits": 523,
  "airplane_hits": 7232,
  "n": 10103
 }
}
```

## A6
```
{
 "n_labeled": 20,
 "sure_counts": {
  "1": 20
 },
 "a6_full": {
  "0.01": {
   "frames_airplane_iou0.5": 10,
   "frames_any_airplane_det": 10,
   "iou0.5_by_class": {
    "kite": 13,
    "airplane": 10,
    "bird": 1
   }
  },
  "0.12": {
   "frames_airplane_iou0.5": 10,
   "frames_any_airplane_det": 10,
   "iou0.5_by_class": {
    "airplane": 10,
    "kite": 12
   }
  },
  "0.25": {
   "frames_airplane_iou0.5": 10,
   "frames_any_airplane_det": 10,
   "iou0.5_by_class": {
    "airplane": 10,
    "kite": 9
   }
  },
  "0.1": {
   "frames_airplane_iou0.5": 10,
   "frames_any_airplane_det": 10,
   "iou0.5_by_class": {
    "kite": 13,
    "airplane": 10
   }
  }
 },
 "a6_crop": {
  "0.01": {
   "frames_airplane_iou0.5": 7,
   "frames_any_airplane_det": 7,
   "iou0.5_by_class": {
    "kite": 13,
    "airplane": 7
   }
  },
  "0.12": {
   "frames_airplane_iou0.5": 7,
   "frames_any_airplane_det": 7,
   "iou0.5_by_class": {
    "kite": 11,
    "airplane": 7
   }
  },
  "0.25": {
   "frames_airplane_iou0.5": 7,
   "frames_any_airplane_det": 7,
   "iou0.5_by_class": {
    "kite": 9,
    "airplane": 7
   }
  },
  "0.1": {
   "frames_airplane_iou0.5": 7,
   "frames_any_airplane_det": 7,
   "iou0.5_by_class": {
    "kite": 12,
    "airplane": 7
   }
  }
 },
 "camtest": {
  "meta": {
   "orig_size": [
    1536,
    864
   ],
   "resized": [
    2304,
    1296
   ],
   "n_tiles": 32
  },
  "0.01": {
   "airplane_dets_after_merge": 0,
   "max_conf": null
  },
  "0.12": {
   "airplane_dets_after_merge": 0,
   "max_conf": null
  },
  "0.25": {
   "airplane_dets_after_merge": 0,
   "max_conf": null
  },
  "0.1": {
   "airplane_dets_after_merge": 0,
   "max_conf": null
  },
  "all_class_dets_conf>=0.25": {
   "tv": 1,
   "bench": 1
  }
 }
}
```
