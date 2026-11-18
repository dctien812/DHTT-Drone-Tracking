#!/bin/bash
mkdir -p ~/dtrack/tmp; export TMPDIR=~/dtrack/tmp
P=~/dtrack/venv/bin/pip
for pk in ultralytics lapx ncnn pnnx onnx onnxslim onnxruntime openvino; do
  echo "== $pk"; $P install --retries 10 --timeout 60 $pk 2>&1 | tail -2 | cut -c1-300
done
$P list 2>/dev/null | grep -i -E "^(torch|torchvision|ultralytics|ncnn|pnnx|onnx|onnxruntime|openvino|lapx|numpy|opencv-python) "
~/dtrack/venv/bin/python -c "import torch,ultralytics,ncnn;print(torch.__version__, ultralytics.__version__)" 2>&1 | tail -3
df -h / | tail -1