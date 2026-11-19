"""Cau hinh pytest cho test B1a (pha do: ma chua ton tai).

Them vision/scripts/b1a vao sys.path de `import prep_split` ... chay duoc khi 05 viet ma.
Chay (WSL):  cd /mnt/d/Personal/Drone-Tracking/vision && ~/venv-vision/bin/python -m pytest -q tests_b1
Can: python 3.12, numpy, Pillow, pytest (deu co trong ~/venv-vision va ~/venv-ardupilot).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
B1A = os.path.abspath(os.path.join(HERE, "..", "scripts", "b1a"))
if B1A not in sys.path:
    sys.path.insert(0, B1A)

MMFW_ROOT = os.path.abspath(os.path.join(HERE, "..", "data", "mmfw-uav", "extracted"))
