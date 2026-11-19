# Moi truong GPU AMD (RX 9060 XT, Windows, PyTorch ROCm)

Rieng cua du an, khong dung toi he thong, khong dung toi `~/venv-vision` trong WSL.
Vi tri: `vision\.venv-gpu` (Python 3.12.16 do uv tai ve, khong cai vao he thong).

## Lenh da chay (tu thu muc `vision`)
```
uv venv --python 3.12 .venv-gpu
uv pip install --python .venv-gpu\Scripts\python.exe pip
B=https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/
.venv-gpu\Scripts\python.exe -m pip install --no-cache-dir B+rocm_sdk_core-7.2.1-py3-none-win_amd64.whl B+rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl B+rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl B+rocm-7.2.1.tar.gz
.venv-gpu\Scripts\python.exe -m pip install --no-cache-dir B+torch-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl B+torchaudio-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl B+torchvision-0.24.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl
.venv-gpu\Scripts\python.exe -m pip install --no-cache-dir -c tools\gpu_env\constraints.txt ultralytics
```
(B la thu muc URL tren, noi chuoi truc tiep.) `constraints.txt` ghim torch/torchvision/torchaudio de ultralytics khong thay ban ROCm.

## Phien ban
Python 3.12.16, torch 2.9.1+rocm7.2.1, torchvision 0.24.1+rocm7.2.1, ultralytics 8.4.215.

## Luu y quan trong
MIOpen (mac dinh) loi voi BatchNorm: `miopenStatusUnknownError` vi hiprtc thieu header C++ (`type_traits`).
Cach tranh trong ma huan luyen: `torch.backends.cudnn.enabled = False` (chay duoc, da kiem).
Neu loss NaN voi ultralytics: them `amp=False`. Dung `device=0`.

## Kiem tra
`.venv-gpu\Scripts\python.exe -I tools\gpu_env\check_gpu.py`

## Go bo
Xoa thu muc `vision\.venv-gpu` la het (tuy chon: `uv python uninstall 3.12.16` de go ban Python uv da tai; va xoa `%APPDATA%\Ultralytics` neu khong can).
