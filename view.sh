#!/usr/bin/env bash
# Interactive reference demonstration. No benchmark scoring or recording.
set -eo pipefail
planner=${ARENA_PLANNER:-teb}
scenario=${ARENA_SCENARIO:-map2_obs05}
case "$planner" in
  teb|dwa) ;;
  *) echo "Unsupported reference planner: $planner" >&2; exit 2 ;;
esac
source /opt/ros/noetic/setup.bash
source /arena_ws/devel/setup.bash
export ROS_PACKAGE_PATH=/arena_ws/src:${ROS_PACKAGE_PATH}
export GAZEBO_MODEL_PATH=/arena_ws/src/simulator_setup/worlds/small_warehouse/models:/usr/share/gazebo-11/models:${GAZEBO_MODEL_PATH:-}
export GAZEBO_PLUGIN_PATH=/arena_ws/actor_plugin_build:${GAZEBO_PLUGIN_PATH:-}
export GAZEBO_MODEL_DATABASE_URI=''
export PYTHONUNBUFFERED=1
python3 /work/portability.py "$scenario"
roscore >/tmp/arena-view-master.log 2>&1 &
master=$!
trap 'kill -TERM "$master" 2>/dev/null || true' EXIT
for attempt in $(seq 1 30); do
  if rosparam list >/dev/null 2>&1; then break; fi
  sleep 1
done
rosparam set world map2
rosparam set /use_sim_time false
rosrun task_generator generate_world.py _task_mode:=scenario _scenario_path:="/arena_ws/src/simulator_setup/scenarios/$scenario.json"
roslaunch /arena_ws/smoke.launch local_planner:="$planner" world:=map2 model:=turtlebot3_burger scenario_file:="$scenario.json" gui:=true headless:=false use_rviz:=${ARENA_RVIZ:-false} viz_path:=false reset:=true
