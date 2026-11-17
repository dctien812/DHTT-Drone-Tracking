#!/bin/bash
env | grep -i -E "gallium|mesa|libgl|egl" ; echo "(env above)"
cat /etc/environment 2>/dev/null | grep -i -E "gallium|mesa"; grep -i -E "gallium|mesa|LIBGL" ~/.bashrc ~/.profile /etc/profile.d/* 2>/dev/null
G='OpenGL renderer|OpenGL version string|Accelerated'
echo "=== A default";            timeout 30 glxinfo -B 2>&1 | grep -E "$G"
echo "=== B GALLIUM=d3d12";      GALLIUM_DRIVER=d3d12 timeout 30 glxinfo -B 2>&1 | grep -E "$G"
echo "=== C GALLIUM=d3d12 + adapter 9060"; GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=9060 timeout 30 glxinfo -B 2>&1 | grep -E "$G"
echo "=== D adapter 9060 only";  MESA_D3D12_DEFAULT_ADAPTER_NAME=9060 timeout 30 glxinfo -B 2>&1 | grep -E "$G"
echo "=== E software";           LIBGL_ALWAYS_SOFTWARE=1 timeout 30 glxinfo -B 2>&1 | grep -E "$G"
echo "=== F GALLIUM=d3d12 + adapter name 'Radeon(TM) Graphics' (iGPU?)"; GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=Radeon timeout 30 glxinfo -B 2>&1 | grep -E "$G"
echo "=== G EGL surfaceless d3d12"; GALLIUM_DRIVER=d3d12 EGL_PLATFORM=surfaceless timeout 30 eglinfo -p surfaceless -B 2>&1 | grep -E "renderer|rror" | head -8