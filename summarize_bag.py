"""Summarize a finalized smoke recording without claiming collision scoring."""
import json
import math
import sys
from collections import Counter
from pathlib import Path
import rosbag

path = Path(sys.argv[1])
counts = Counter()
goals, results = [], []
first_clock = last_clock = None
peak_v = peak_w = 0.0
previous = None
distance = 0.0
jumps = 0
with rosbag.Bag(str(path)) as bag:
    for topic, msg, timestamp in bag.read_messages():
        counts[topic] += 1
        if topic == '/clock':
            last_clock = msg.clock.to_sec()
            if first_clock is None:
                first_clock = last_clock
        elif topic == '/move_base/goal':
            goals.append({'stamp': msg.header.stamp.to_sec(), 'id': msg.goal_id.id})
        elif topic == '/move_base/result':
            results.append({'stamp': msg.header.stamp.to_sec(), 'id': msg.status.goal_id.id,
                            'status': msg.status.status, 'text': msg.status.text})
        elif topic == '/cmd_vel':
            peak_v = max(peak_v, abs(msg.linear.x))
            peak_w = max(peak_w, abs(msg.angular.z))
        elif topic == '/odom':
            point = (msg.pose.pose.position.x, msg.pose.pose.position.y)
            if previous is not None:
                step = math.hypot(point[0] - previous[0], point[1] - previous[1])
                if step > 1.0:
                    jumps += 1
                else:
                    distance += step
            previous = point
report = {
    'purpose': 'smoke validation only; collision outcome not evaluated',
    'topic_counts': dict(counts), 'goals': goals, 'results': results,
    'simulation_clock_first': first_clock, 'simulation_clock_last': last_clock,
    'peak_absolute_command_linear_x_m_s': peak_v,
    'peak_absolute_command_angular_z_rad_s': peak_w,
    'odometry_distance_excluding_jumps_over_1m': distance,
    'excluded_odometry_jumps': jumps,
    'note': 'Displacement is diagnostic, not a frozen benchmark metric.'}
output = path.with_name('bag-summary.json')
output.write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
