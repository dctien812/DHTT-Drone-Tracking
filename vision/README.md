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
