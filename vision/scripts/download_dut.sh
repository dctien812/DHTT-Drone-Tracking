#!/bin/bash
# Tai DUT Anti-UAV (Google Drive, link cong khai trong README cua repo). Chay: bash download_dut.sh
source ~/venv-vision/bin/activate
cd ~
D=/mnt/d/Personal/Drone-Tracking/vision/data/dut-anti-uav
mkdir -p $D
[ -f $D/val.zip ]   || gdown 1333uEQfGuqTKslRkkeLSCxylh6AQ0X6n -O $D/val.zip -q
[ -f $D/test.zip ]  || gdown 1L1zeW1EMDLlXHClSDcCjl3rs_A6sVai0 -O $D/test.zip -q
[ -f $D/train.zip ] || gdown 1RVsSGPUKTdmoyoPTBTWwroyulLek1eTj -O $D/train.zip -q
ls -la $D
