"""Produce a scored Arena result from an instrumented single-goal run."""
from collections import defaultdict
import csv
import gzip
import json
import math
from pathlib import Path
import sys

import numpy as np
from rosbag.bag import ROSBagException
from shapely.geometry import MultiPoint
from shapely.ops import unary_union

from score_trajectory import measure_motion, read_bag, yaw_of


def points_of(coordinates):
    values = list(map(float, coordinates))
    if len(values) < 6 or len(values) % 2 or not all(math.isfinite(value) for value in values):
        raise ValueError('Invalid collision geometry')
    return list(zip(values[::2], values[1::2]))


def minimum_gap(robot, other_shapes, clearance):
    left, bottom, right, top = robot.bounds
    for points in other_shapes:
        if clearance == 0:
            break
        x, y = zip(*points)
        dx = max(left - max(x), min(x) - right, 0)
        dy = max(bottom - max(y), min(y) - top, 0)
        if math.hypot(dx, dy) < clearance:
            clearance = min(clearance, robot.distance(MultiPoint(points).convex_hull))
    return clearance


def safety_metrics(run, start, end, actors, sample_hz):
    with (run / 'static-geometry.tsv').open() as stream:
        geometry = unary_union([
            MultiPoint(points_of(row)).convex_hull for row in csv.reader(stream, delimiter='\t')
        ])
    if geometry.is_empty:
        raise ValueError('Missing static collision geometry')

    events = 0
    samples = []
    shapes = defaultdict(list)
    previous = None
    clearance = math.inf

    def finish_sample():
        nonlocal clearance
        if not shapes:
            return
        if 'turtlebot3' not in shapes or len(shapes) - 1 != actors:
            raise ValueError('Robot or pedestrian collision geometry is incomplete')
        samples.append(previous)
        robot = unary_union([MultiPoint(points).convex_hull for points in shapes['turtlebot3']])
        clearance = min(clearance, robot.distance(geometry))
        if clearance > 0:
            for name, polygons in shapes.items():
                if name != 'turtlebot3':
                    clearance = minimum_gap(robot, polygons, clearance)

    margin = 1.6 / sample_hz
    path = run / 'safety.tsv'
    stream = path.open() if path.exists() else gzip.open(run / 'safety.tsv.gz', 'rt')
    with stream:
        for kind, stamp, name, *points in csv.reader(stream, delimiter='\t'):
            stamp = float(stamp)
            if kind == 'contact':
                if start <= stamp <= end:
                    events += 1
            elif kind == 'shape' and start <= stamp <= end:
                if stamp != previous:
                    finish_sample()
                    shapes.clear()
                    previous = stamp
                shapes[name].append(points_of(points))
    finish_sample()
    if (not samples or samples[0] - start > margin or end - samples[-1] > margin
            or any(b - a > margin for a, b in zip(samples, samples[1:]))):
        raise ValueError('Safety recording does not cover the trial at the configured rate')
    return {'collision_count': events, 'clearance_m': 0.0 if events else clearance}


def score(run):
    protocol = json.loads((run / 'protocol.json').read_text())
    trial = json.loads((run / 'termination.json').read_text())
    if trial['outcome'] == 'invalid':
        raise ValueError(trial['reason'])
    start, end = trial['start'], trial['end']
    accepted, goals, results, odometry, commands = read_bag(run / 'topics.bag')
    goal_id = trial['goal_id']
    terminal = [msg for msg in results if msg.status.goal_id.id == goal_id]
    if len(goals) != 1 or set(accepted) - {goal_id} or (goal_id not in accepted and not terminal):
        raise ValueError('The bag does not contain exactly one matching goal')
    if not commands:
        raise ValueError('Missing command recording')
    command_peaks = np.max(np.abs(commands), axis=0)
    caps = np.asarray([protocol['max_linear_m_s'], protocol['max_angular_rad_s']])
    if np.any(command_peaks > caps + 1e-4):
        raise ValueError(f'Command limits exceeded: {command_peaks.tolist()}')

    motion = measure_motion(odometry, start, end)
    goal = goals[0].goal.target_pose
    if goal.header.frame_id.lstrip('/') != 'map':
        raise ValueError('The recorded goal must use the Arena map frame')
    samples = np.asarray(odometry)
    x, y = (np.interp(end, samples[:, 0], axis) for axis in samples[:, 1:3].T)
    yaw = np.interp(end, samples[:, 0], np.unwrap(samples[:, 3]))
    xy_error = math.hypot(x - goal.pose.position.x, y - goal.pose.position.y)
    yaw_error = abs(math.remainder(yaw - yaw_of(goal.pose.orientation), 2 * math.pi))
    if trial['outcome'] == 'timeout':
        outcome = 'timeout'
    else:
        if len(terminal) != 1 or terminal[0].status.status != trial['status']:
            raise ValueError('Terminal state is missing from the bag')
        outcome = 'navigation_failure'
        if (trial['status'] == 3 and xy_error <= protocol['goal_xy_m'] + 1e-4
                and yaw_error <= protocol['goal_yaw_rad'] + 1e-4):
            outcome = 'success'

    scenario = json.loads((run / 'scenario.json').read_text())
    actors = sum(agent['number_of_peds'] for agent in scenario['pedsim_agents'])
    return {
        'outcome': outcome,
        'move_base_status': trial.get('status'),
        'sim_seconds': end - start,
        'time_to_goal_s': end - start if outcome == 'success' else None,
        'goal_xy_error_m': xy_error,
        'goal_yaw_error_rad': yaw_error,
        'peak_linear_command_m_s': float(command_peaks[0]),
        'peak_angular_command_rad_s': float(command_peaks[1]),
        **motion,
        **safety_metrics(run, start, end, actors, protocol['clearance_sample_hz']),
    }


if __name__ == '__main__':
    folder = Path(sys.argv[1])
    try:
        result = score(folder)
    except (OSError, ValueError, ROSBagException) as error:
        result = {'outcome': 'invalid', 'reason': str(error)}
    (folder / 'score.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, indent=2, allow_nan=False), flush=True)
