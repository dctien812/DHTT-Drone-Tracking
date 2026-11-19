# Thong ke buoc 6

## So vung cat theo tap va loai (bg None = khong tao duoc)
- train: {('pos', 'ok'): 1153, ('bg', 'ok'): 1153}
- val: {('pos', 'ok'): 1279, ('bg', 'ok'): 1279}
- test: {('pos', 'ok'): 10103, ('off', 'ok'): 10103, ('bg', 'ok'): 10103}
- train chim (am): 708; birds_fa: 150

## Phan bo dai co (theo be rong khung o thang 2304), moi KHUNG dem 1 lan (loai pos)
- train (n=1153): {'<16': '0 (0.0%)', '16-57': '155 (13.4%)', '57-200': '914 (79.3%)', '>200': '84 (7.3%)'}
    - Top_Down n=366: {'57-200': 342, '16-57': 13, '>200': 11}; be rong trung vi 113.4, p5-p95 66.0-190.8
    - Horizontal n=374: {'16-57': 111, '57-200': 217, '>200': 46}; be rong trung vi 101.4, p5-p95 35.4-277.2
    - Bottom_Up n=413: {'57-200': 355, '16-57': 31, '>200': 27}; be rong trung vi 93.0, p5-p95 52.8-214.6
- val (n=1279): {'<16': '0 (0.0%)', '16-57': '191 (14.9%)', '57-200': '1024 (80.1%)', '>200': '64 (5.0%)'}
    - Top_Down n=407: {'57-200': 347, '>200': 60}; be rong trung vi 130.8, p5-p95 76.8-223.2
    - Horizontal n=415: {'16-57': 12, '57-200': 403}; be rong trung vi 91.2, p5-p95 68.0-161.2
    - Bottom_Up n=457: {'16-57': 179, '57-200': 274, '>200': 4}; be rong trung vi 103.2, p5-p95 36.6-187.3
- test (n=10103): {'<16': '0 (0.0%)', '16-57': '2605 (25.8%)', '57-200': '7317 (72.4%)', '>200': '181 (1.8%)'}
    - Top_Down n=3601: {'16-57': 643, '57-200': 2899, '>200': 59}; be rong trung vi 82.2, p5-p95 50.4-141.0
    - Horizontal n=3111: {'>200': 122, '57-200': 2349, '16-57': 640}; be rong trung vi 75.0, p5-p95 37.8-186.6
    - Bottom_Up n=3391: {'57-200': 2069, '16-57': 1322}; be rong trung vi 61.8, p5-p95 33.6-91.2

## Truncated (vung cat duong/lech tam)
- train pos: 0/1153 = 0.000%
- val pos: 0/1279 = 0.000%
- test pos: 0/10103 = 0.000%
- test off: 0/10103 = 0.000%

## Huong theo tap (so khung)
- train: {'Bottom_Up': 413, 'Horizontal': 374, 'Top_Down': 366}
- val: {'Bottom_Up': 457, 'Horizontal': 415, 'Top_Down': 407}
- test: {'Bottom_Up': 3391, 'Horizontal': 3111, 'Top_Down': 3601}

## Kiem nhat quan crop_to_frame: khung nhan o crop + (x0,y0) = khung nhan o 2304 khi khong truncated
- nhan duong da kiem: 22638; nhan khong hop le (5 so, [0,1]): 0; khong khop crop_to_frame (>0.01 px): 0

## So anh = so nhan, nhan nen rong
- train: anh 3014, nhan 3014, ten khop True
- val: anh 2558, nhan 2558, ten khop True
- test: anh 30309, nhan 30309, ten khop True

## Dung luong /mnt/d/Personal/Drone-Tracking/vision/data/b1a: 8.72 GB
