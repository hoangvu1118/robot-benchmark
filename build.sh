#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/noetic/setup.bash
python3 /work/prepare.py
cd /arena_ws
packages='arena_bringup;simulator_setup;task_generator;conventional;sensor_simulator;arena_intermediate_planner;arena_mapping;arena_path_search;arena_traj_planner;arena_plan_msgs;plan_visualization;ford_msgs;pedsim_msgs;pedsim_srvs;teb_local_planner'
catkin_make -j2 -l2 -DCMAKE_BUILD_TYPE=Release -DPYTHON_EXECUTABLE=/usr/bin/python3 -DCATKIN_WHITELIST_PACKAGES="$packages"
cmake -S /work/dependencies/ActorCollisionsPlugin -B /arena_ws/actor_plugin_build
cmake --build /arena_ws/actor_plugin_build -j2
