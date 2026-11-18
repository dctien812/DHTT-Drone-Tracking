#!/bin/bash
mkdir -p ~/dtrack/tmp; export TMPDIR=~/dtrack/tmp
P=~/dtrack/venv/bin/pip
$P install --retries 10 --timeout 60 --resume-retries 10 --no-deps torch torchvision 2>&1 | tail -3
$P install --retries 10 filelock sympy networkx jinja2 fsspec typing_extensions setuptools numpy 2>&1 | tail -2
~/dtrack/venv/bin/python -c "import torch;print(torch.__version__, torch.cuda.is_available(), torch.get_num_threads())" 2>&1 | tail -4
df -h / | tail -1; du -sh ~/dtrack/venv