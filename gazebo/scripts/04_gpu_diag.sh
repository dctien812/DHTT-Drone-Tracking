#!/bin/bash
ls /usr/lib/x86_64-linux-gnu/dri | grep -i -E "d3d12|zink|radeon|swrast" | head
dpkg -l | grep -E "mesa-libgallium|libgl1-mesa-dri" | awk '{print $2,$3}'
echo "--- GALLIUM_DRIVER=d3d12"
GALLIUM_DRIVER=d3d12 timeout 30 glxinfo -B 2>&1 | grep -E "renderer|version|Device|Accelerated|rror|libGL"
echo "--- verbose"
GALLIUM_DRIVER=d3d12 LIBGL_DEBUG=verbose timeout 30 glxinfo -B 2>&1 | head -15
echo "--- wayland EGL"
timeout 30 eglinfo -B 2>&1 | head -40