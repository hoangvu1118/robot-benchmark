"""Bounded smoke check. This is connectivity validation, not benchmark scoring."""
import json
import sys
import time
from collections import Counter
from pathlib import Path
import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from move_base_msgs.msg import MoveBaseActionResult

rospy.init_node('benchmark_smoke_check', anonymous=True)
counts = Counter()
outcomes = []
distance = 0.0
previous = None
def odom(msg):
    global distance, previous
    counts['odom'] += 1
    point = (msg.pose.pose.position.x, msg.pose.pose.position.y)
    if previous is not None:
        distance += ((point[0]-previous[0])**2 + (point[1]-previous[1])**2)**0.5
    previous = point
def command(msg):
    counts['cmd_vel'] += 1
    if abs(msg.linear.x) + abs(msg.angular.z) > 1e-5:
        counts['nonzero_cmd_vel'] += 1
rospy.Subscriber('/odom', Odometry, odom)
rospy.Subscriber('/scan', LaserScan, lambda _: counts.update(['scan']))
rospy.Subscriber('/cmd_vel', Twist, command)
rospy.Subscriber('/move_base/result', MoveBaseActionResult,
                 lambda msg: outcomes.append({'status': msg.status.status, 'text': msg.status.text}))
deadline = time.monotonic() + 300
while time.monotonic() < deadline and not rospy.is_shutdown() and not outcomes:
    time.sleep(0.25)
healthy = all(counts[key] > 0 for key in ('scan', 'odom', 'nonzero_cmd_vel'))
result = {'purpose': 'connectivity smoke test; not collision-scored',
          'distance_note': 'Raw odometry displacement may include initial scenario teleport; not a scored path length.',
          'topics': dict(counts), 'odometry_distance_m': distance,
          'move_base_results': outcomes, 'connectivity_pass': healthy}
Path(sys.argv[1], 'summary.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2), flush=True)
sys.exit(0 if healthy else 1)
