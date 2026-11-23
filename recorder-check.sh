#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/noetic/setup.bash
roscore >/tmp/recorder-master.log 2>&1 &
master=$!
trap 'kill -TERM "$master" 2>/dev/null || true' EXIT
sleep 2
/opt/ros/noetic/lib/rosbag/record -O /arena_ws/recorder-check.bag /rosout &
recorder=$!
sleep 2
kill -INT "$recorder"
for attempt in $(seq 1 50); do
    if ! kill -0 "$recorder" 2>/dev/null; then
        wait "$recorder"
        rosbag info /arena_ws/recorder-check.bag
        exit 0
    fi
    sleep 0.1
done
echo 'Recorder did not exit within five seconds' >&2
exit 1
