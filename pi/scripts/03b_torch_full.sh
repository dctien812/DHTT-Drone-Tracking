#!/bin/bash
mkdir -p ~/dtrack/tmp; export TMPDIR=~/dtrack/tmp
nohup ~/dtrack/venv/bin/pip install --retries 10 --timeout 60 --resume-retries 10 torch torchvision pillow > ~/dtrack/pip_torch.log 2>&1 &
echo started