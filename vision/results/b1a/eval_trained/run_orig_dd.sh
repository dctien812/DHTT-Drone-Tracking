#!/bin/bash
cd /mnt/d/Personal/Drone-Tracking/vision || exit 1
P=$HOME/venv-vision/bin/python
$P -I scripts/b1a/run_eval_trained.py infer ORIG_DD > results/b1a/eval_trained/infer_orig_DD.log 2>&1
$P -I scripts/b1a/run_eval_trained.py score ORIG_DD > results/b1a/eval_trained/score_orig_DD.log 2>&1
echo done > results/b1a/eval_trained/orig_DD.done
