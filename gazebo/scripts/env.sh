# source this file. MODE: gpu | cpu  (default gpu)
export GZ_VERSION=harmonic
export GZ_SIM_SYSTEM_PLUGIN_PATH=$HOME/ardupilot_gazebo/build:$GZ_SIM_SYSTEM_PLUGIN_PATH
export GZ_SIM_RESOURCE_PATH=$HOME/ardupilot_gazebo/models:$HOME/ardupilot_gazebo/worlds:$GZ_SIM_RESOURCE_PATH
if [ "${RENDER:-gpu}" = "gpu" ]; then
  export GALLIUM_DRIVER=d3d12
  export MESA_D3D12_DEFAULT_ADAPTER_NAME=9060
else
  export LIBGL_ALWAYS_SOFTWARE=1
fi