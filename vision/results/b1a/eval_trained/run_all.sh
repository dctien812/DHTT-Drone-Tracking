#!/bin/bash
cd /mnt/d/Personal/Drone-Tracking/vision || exit 1
P=$HOME/venv-vision/bin/python
rm -f results/b1a/eval_trained/ALL.done
for T in EE DD; do
  $P -I scripts/b1a/run_eval_trained.py infer $T > results/b1a/eval_trained/infer_$T.log 2>&1
  $P -I scripts/b1a/run_eval_trained.py score $T > results/b1a/eval_trained/score_$T.log 2>&1
done
echo ALLDONE > results/b1a/eval_trained/ALL.done
