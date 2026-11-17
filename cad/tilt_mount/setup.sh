set -e
python3 -m venv ~/venv-cad
~/venv-cad/bin/pip install -q cadquery trimesh numpy pytest matplotlib 2>&1 | tail -5
~/venv-cad/bin/python -c 'import cadquery;print(cadquery.__version__)'
