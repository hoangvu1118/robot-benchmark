#!/usr/bin/env bash
set -eo pipefail
planner=${ARENA_PLANNER:-teb}
scenario=${ARENA_SCENARIO:-map2_obs05}
batch=${ARENA_BATCH_ID:-}
trial=${ARENA_TRIAL:-}
scored=${ARENA_SCORED:-false}
gui=false
headless=true
rviz=false
if [[ ${ARENA_GUI:-false} == true ]]; then
  gui=true
  headless=false
  rviz=${ARENA_RVIZ:-false}
fi
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
# Record to Linux storage; Windows bind-mount writes can lag behind simulation.
result_root=/work/results
linux_root=/arena_ws/results
if [[ -n $batch ]]; then
  if [[ ! $batch =~ ^(baseline|scored)-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$ || ! $trial =~ ^[0-9]{3}$ ]]; then
    echo "Invalid batch or trial identifier" >&2
    exit 2
  fi
  case "$scenario" in map2_static|map2_obs05|map2_obs10) ;; *) exit 2 ;; esac
  result_root="$result_root/$batch/$scenario/$planner"
  linux_root="$linux_root/$batch/$scenario/$planner"
  mkdir -p "$linux_root"
  run_dir="$linux_root/$trial"
  mkdir "$run_dir"
else
  mkdir -p "$linux_root"
  prefix="smoke-$planner"
  if [[ $scenario != map2_obs05 ]]; then
    case "$scenario" in map2_static|map2_obs10) prefix="$prefix-$scenario" ;; *) exit 2 ;; esac
  fi
  run_dir=$(mktemp -d "$linux_root/$prefix-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
fi
cleanup() {
  local status=$?
  set +e
  if [[ -n ${bag_pid:-} ]]; then kill -INT "$bag_pid" 2>/dev/null || true; wait "$bag_pid" || true; fi
  if [[ -n ${launch_pid:-} ]]; then kill -INT "$launch_pid" 2>/dev/null || true; wait "$launch_pid" || true; fi
  if [[ -n ${limit_pid:-} ]]; then kill -INT "$limit_pid" 2>/dev/null || true; wait "$limit_pid" || true; fi
  if [[ -n ${master_pid:-} ]]; then kill -INT "$master_pid" 2>/dev/null || true; fi
  if [[ $scored == true ]]; then
    python3 /work/score_trial.py "$run_dir" || status=1
    if [[ -f "$run_dir/safety.tsv" ]]; then
      gzip -1 "$run_dir/safety.tsv" || status=1
    fi
  elif [[ -n $batch || $gui == true ]]; then
    python3 /work/summarize_bag.py "$run_dir/topics.bag" > "$run_dir/bag-verification.log" 2>&1 || status=1
  fi
  mkdir -p "$result_root" && cp -a "$run_dir" "$result_root/" || status=1
  exit "$status"
}
trap cleanup EXIT
echo "Saving $planner / $scenario to $result_root/$(basename "$run_dir")"
python3 /work/portability.py "$scenario" > "$run_dir/portability.log" 2>&1
cp /work/environment.json /work/dependencies.json /work/portability.patch "$run_dir/"
scenario_path="/arena_ws/src/simulator_setup/scenarios/$scenario.json"
cp "$scenario_path" "$run_dir/scenario.json"
roscore > "$run_dir/roscore.log" 2>&1 &
master_pid=$!
for attempt in $(seq 1 30); do
  if rosparam list >/dev/null 2>&1; then break; fi
  sleep 1
done
rosparam set world map2
rosparam set /use_sim_time false
rosrun task_generator generate_world.py _task_mode:=scenario _scenario_path:="$scenario_path" > "$run_dir/world-generation.log" 2>&1
launch_file=/arena_ws/smoke.launch
if [[ $scored == true ]]; then
  python3 /work/configure_scoring.py "$run_dir" "$planner" "${ARENA_SIM_SECONDS:-}"
  export ARENA_SAFETY_DIR="$run_dir"
  export GAZEBO_PLUGIN_PATH="/arena_ws/safety_build:$GAZEBO_PLUGIN_PATH"
  launch_file="$run_dir/scored.launch"
  rosparam set /use_sim_time true
fi
cp /arena_ws/src/simulator_setup/worlds/map2/worlds/map2.world "$run_dir/generated.world"
# Start the recorder binary directly so its PID receives SIGINT at cleanup.
scored_topics=()
if [[ $scored == true ]]; then
  scored_topics=(/arena/raw_cmd_vel)
  python3 /work/limit_scored_commands.py "$run_dir/protocol.json" > "$run_dir/speed-limits.log" 2>&1 &
  limit_pid=$!
fi
/opt/ros/noetic/lib/rosbag/record -O "$run_dir/topics.bag" /clock /scan /odom /tf /tf_static /cmd_vel /move_base/result /move_base/status /move_base/goal /move_base_simple/goal /scenario_reset /End_of_scenario /rosout "${scored_topics[@]}" > "$run_dir/rosbag.log" 2>&1 &
bag_pid=$!
roslaunch "$launch_file" local_planner:="$planner" world:=map2 model:=turtlebot3_burger scenario_file:="$scenario.json" gui:="$gui" headless:="$headless" use_rviz:="$rviz" viz_path:=false reset:=false > "$run_dir/launch.log" 2>&1 &
launch_pid=$!
echo "Arena run logs: $run_dir"
status=0
if [[ $scored == true ]]; then
  python3 /work/monitor_scored_trial.py "$run_dir" || status=$?
else
  python3 /work/check_runtime.py "$run_dir" || status=$?
fi
rosparam dump "$run_dir/parameters.yaml"
exit "$status"
