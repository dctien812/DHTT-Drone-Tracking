#!/bin/bash
cd ~/dtrack; export TMPDIR=~/dtrack/tmp
~/dtrack/venv/bin/python bench.py --model models/ft_v8n_640_ncnn_model --fmt ncnn --imgsz 640 --maxf 30 --out results/smoke.csv --save results/smoke.png 2>&1 | tail -8