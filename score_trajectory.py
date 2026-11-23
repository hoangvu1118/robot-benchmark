"""Extract motion metrics from a completed, single-goal Arena ROS bag."""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import rosbag
from scipy.signal import savgol_filter


SAMPLE_HZ = 10
MAX_ODOM_GAP_S = 0.2
JERK_WINDOW = 9
MIN_ROUGHNESS_LENGTH_M = 0.01


def measure_motion(odometry, start, end):
    samples = np.asarray(odometry)
    if samples.shape[0] < 2 or not np.isfinite(samples).all():
        raise ValueError('Missing or invalid odometry')
    times = samples[:, 0]
    if np.any(np.diff(times) <= 0):
        raise ValueError('Odometry timestamps must increase within a single run')
    if times[0] > start or times[-1] < end:
        raise ValueError('Odometry does not cover the full goal-to-result window')

    left = np.searchsorted(times, start, side='right') - 1
    right = np.searchsorted(times, end, side='left') + 1
    times = times[left:right]
    if np.any(np.diff(times) > MAX_ODOM_GAP_S):
        raise ValueError('Odometry has a gap larger than 0.2 simulation seconds')
    samples = samples[left:right]

    grid = start + np.arange(math.floor((end - start) * SAMPLE_HZ) + 1) / SAMPLE_HZ
    grid = grid[grid < end]
    path_grid = np.append(grid, end)
    path = np.column_stack([np.interp(path_grid, times, axis) for axis in samples[:, 1:3].T])
    yaw = np.interp(path_grid, times, np.unwrap(samples[:, 3]))
    length = float(np.linalg.norm(np.diff(path, axis=0), axis=1).sum())
    heading_change = float(np.abs(np.diff(yaw)).sum())

    jerk = None
    if len(grid) >= JERK_WINDOW:
        # Differentiate the position fit three times. Exclude filter edges
        # and the potentially shorter last segment.
        half_window = JERK_WINDOW // 2
        derivatives = savgol_filter(path[:-1], JERK_WINDOW, 3, deriv=3,
                                    delta=1 / SAMPLE_HZ, axis=0)
        interior = derivatives[half_window:-half_window]
        jerk = float(np.sqrt(np.mean(np.sum(interior ** 2, axis=1))))

    return {
        'path_length_m': length,
        'jerk_rms_m_s3': jerk,
        'trajectory_roughness_rad_per_m': (
            heading_change / length if length >= MIN_ROUGHNESS_LENGTH_M else None
        ),
    }


def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y),
                      1 - 2 * (q.y * q.y + q.z * q.z))


def read_bag(path):
    accepted = {}
    goals = []
    results = []
    odometry = []
    commands = []
    topics = ['/move_base/status', '/move_base/goal', '/move_base/result', '/odom', '/cmd_vel']
    with rosbag.Bag(str(path)) as bag:
        for topic, msg, _ in bag.read_messages(topics=topics):
            if topic == '/move_base/status':
                for status in msg.status_list:
                    if status.status == 1:  # ACTIVE
                        accepted[status.goal_id.id] = status.goal_id.stamp.to_sec()
            elif topic == '/move_base/result':
                results.append(msg)
            elif topic == '/move_base/goal':
                goals.append(msg)
            elif topic == '/cmd_vel':
                commands.append((msg.linear.x, msg.angular.z))
            elif topic == '/odom':
                pose = msg.pose.pose
                odometry.append((msg.header.stamp.to_sec(), pose.position.x,
                                 pose.position.y, yaw_of(pose.orientation)))
    return accepted, goals, results, odometry, commands


def score(path):
    accepted, _, results, odometry, _ = read_bag(path)

    if len(results) != 1 or len(accepted) != 1:
        raise ValueError('Expected one accepted action goal and one terminal result')
    result = results[0]
    start = accepted.get(result.status.goal_id.id)
    end = result.header.stamp.to_sec()
    if start is None or end <= start:
        raise ValueError('Result does not match the accepted action goal and its time window')
    return {
        'source': str(path),
        'goal_id': result.status.goal_id.id,
        'start_sim_s': start,
        'end_sim_s': end,
        'move_base_status': result.status.status,
        'time_to_goal_s': end - start if result.status.status == 3 else None,
        **measure_motion(odometry, start, end),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bag', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(score(args.bag), indent=2, allow_nan=False))
    except ValueError as error:
        parser.exit(1, f'Cannot score trajectory: {error}\n')
