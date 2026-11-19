# vision/ - luong phu V1: do bo nhan dien drone (mot lop "drone")

Muc tieu: tra loi bang so bo nhan dien (YOLO, Ultralytics) bat duoc muc tieu nho co nao (10-40 px), ti le bao nhieu,
bao dong gia bao nhieu, sai so be rong khung bao, toc do. Ket qua: `results/SUMMARY.md` (+ cac CSV cung thu muc).
Khong dung toi `onboard/`, `sim/`, `gcs/`. Bien dich sang Hailo KHONG nam trong luong nay.

## Dung moi truong (WSL Ubuntu-24.04, CPU; may nay khong co GPU NVIDIA trong WSL)
```bash
python3 -m venv ~/venv-vision && source ~/venv-vision/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install ultralytics gdown        # ban da dung: torch 2.15.0+cpu, ultralytics 8.4.215
```
Goi tu PowerShell: `wsl -d Ubuntu-24.04 -- bash /mnt/d/Personal/Drone-Tracking/vision/scripts/<file>.sh`.
Khi chay tren CPU: toi da 6 luong, `workers<=4`, `nice -n 10`.

## Du lieu: DUT Anti-UAV (detection) - Apache-2.0, anh RGB, 10.000 anh (train 5200 / val 2600 / test 2200)
Link Google Drive cong khai trong README cua repo https://github.com/wangdongdut/DUT-Anti-UAV (nhanh master).
Det-Fly (OneDrive/Baidu) KHONG tai tu dong duoc nen bo qua (xem results/SUMMARY.md).
```bash
bash scripts/download_dut.sh                 # ~1.4 GB zip vao data/dut-anti-uav/
python -I scripts/prepare_dut.py             # giai nen, nhan VOC -> YOLO (1 lop) vao data/dut-yolo/
python -I scripts/dataset_stats.py           # results/dataset_stats.csv
```

## Cham (tap test, khong dung de huan luyen)
```bash
# 2 model cu (chi nap hai file best.pt cua DHTT-UAV-Testing-CLEAN; AI-7 la YOLOv12n 40 lop, drone = lop 38)
TAG=old_finetune W=/mnt/d/Personal/DHTT-UAV-Testing-CLEAN/finetune/best.pt CLS=0  bash scripts/run_eval_all.sh
TAG=old_ai7      W=/mnt/d/Personal/DHTT-UAV-Testing-CLEAN/AI-7/best.pt      CLS=38 bash scripts/run_eval_all.sh
TAG=old_finetune W=... CLS=0 bash scripts/run_sweep.sh     # quet be rong 6..40 px (anh thu nho, khung 640)
python -I scripts/make_summary.py                          # gop CSV -> results/SUMMARY.md
```
`eval_detector.py` co 3 che do: `full` (thu nho ca anh ve imgsz 640/1280), `crop` (cat 640x640 o do phan giai goc quanh
muc tieu, lech tam ngau nhien, hat giong theo ten anh), `sweep` (thu nho anh de muc tieu rong tw px).

## Tinh chinh (yolov8n chinh thuc, CPU, <=84 phut)
```bash
python -I scripts/build_train_set.py     # data/dut-train: 1400 crop goc + 700 anh thu nho + 150 crop khong muc tieu (tu split train)
bash scripts/run_train_after_eval.sh     # hoac: python -I scripts/train_ft.py ; ket qua o runs/ft_v8n/weights/best.pt
TAG=ft_v8n W=/mnt/d/Personal/Drone-Tracking/vision/runs/ft_v8n/weights/best.pt CLS=0 bash scripts/run_eval_all.sh
```
`data/`, `runs/`, `weights/`, `*.pt` nam trong `.gitignore`. File `.pt` la pickle: chi nap 2 best.pt cu va trong so
chinh thuc do ultralytics tu tai; du lieu tai ve chi doc nhu anh/nhan, khong chay gi trong goi du lieu.

## B1: nhan dien + theo doi tren video ghi san (offline, chi doc video; ket qua: `results/b1/B1_REPORT.md`)
Video: `D:\Personal\DHTT-TRACKING-TEST\AI-6\video\` (CHI DOC; 119 file, 640x512 30 fps, 1 file 464x848). Khong co nhan -> so do "khong can nhan".
Goi qua WSL (xuong dong LF), tai lap theo thu tu:
```bash
bash scripts/run_b1_detect.sh                 # pha detect: 3 model x (full | crop320), luu moi phat hien conf>=0.1 vao runs/b1_det/*.npz (~15 phut/luot tren 8 loi)
bash scripts/run_b1_track.sh                  # pha track: ByteTrack + BoT-SORT (khong ReID/GMC), conf 0.25 va 0.5 -> results/b1/trk_*.csv
python -I scripts/summarize_b1.py             # -> results/b1/summary_b1.csv, B1_TABLES.md
python -I scripts/render_b1.py runs/b1_det/ft_crop runs/b1_videos/best_ft_crop 0.25 V_DRONE_075,V_AIRPLANE_001
python -I scripts/grab_b1.py runs/b1_videos/best_ft_crop runs/b1_videos/best_ft_crop/check   # 3 khung/video de tu kiem
python -I scripts/catalog_b1.py results/b1/catalog.csv ; python -I scripts/sheets_b1.py runs/b1_videos/sheets
```
`lap` duoc ultralytics tu cai vao `~/venv-vision` khi chay tracker lan dau (lap 0.5.14).

## V2: huan luyen lai ft2_v8n (anh am + chia theo nhom; ket qua: `results/v2/V2_REPORT.md`, bang: `results/v2/compare.md`)
Du lieu moi: Det-Fly (`data/det-fly`, 7.635 cap xml+jpg khop), COCO am (`data/coco-neg`, may bay/chim, 1.884 anh co giay phep CC BY/BY-SA/PD), tap dung san `data/v2/` (ft2 train/val, test_clean).
Ket qua: ft2 giam bao dong gia (tap sach 32,2 -> 9,3/100 anh) nhung van goi may bay that la drone (~70% khung o 0,5) va khong dat 3/4 tieu chi -> chua thay ft_v8n.
```bash
bash scripts/run_features_v2.sh ; bash scripts/run_py_v2.sh split_v2.py             # dac trung 32x32 + chia theo nhom + kiem ro ri (results/v2/split_summary.md)
bash scripts/run_download_coco_neg_v2.sh 1600 1200 ; bash scripts/run_py_v2.sh build_data_v2.py
bash scripts/run_train_v2.sh --epochs 30 --limit 4200                                # ~3,8 gio CPU -> runs/ft2_v8n ; chep best.pt -> weights/ft2_v8n_best.pt
bash scripts/run_eval_v2.sh <tag> <weights>                                         # tap sach + 120 khung nhan tay
bash scripts/run_video_v2.sh <tag> <weights> detect ; bash scripts/run_py_v2.sh summarize_v2.py ; bash scripts/run_py_v2.sh compare_v2.py
```

## B1a: nhan dien may bay canh bang (yolov8n goc lop airplane vs huan luyen them; ket qua: `results/b1a/B1A_REPORT.md`)
Kiem cheo theo may bay (hoc 2 bo, kiem 2 bo con lai), mot vong, mot seed, khong tinh chinh. Ket luan tam: huan luyen them KHONG hon model goc
mot cach on dinh tren tap kiem cheo (EE Top_Down 0,129 so voi 0,402; bao dong gia nhieu hon). Model "final" bat may bay tren video that 1
tot hon goc o doan lien tuc (98,6% so voi 84,2%) nhung khong hon o khung rai (69,4% so voi 71,8%), va phat hien gia gap ~17 lan (fin1: 69 so voi 4 tren 269 khung; fin2 phong 2304 px: 441). Mac dinh van dung `yolov8n.pt` goc, lop airplane,
nguong 0,12; final la ung vien vong sau (them nen kho lam mau am). Script: `scripts/b1a/` (lenh chay lai o cuoi bao cao).
