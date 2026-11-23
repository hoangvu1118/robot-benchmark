"""Enforce identical physical speed caps after each scored planner."""
import json
import math
from pathlib import Path
import sys

import rospy
from geometry_msgs.msg import Twist


def run(protocol):
    max_linear = protocol['max_linear_m_s']
    max_angular = protocol['max_angular_rad_s']
    rospy.init_node('arena_scored_speed_limits')
    output = rospy.Publisher('/cmd_vel', Twist, queue_size=5)

    def limit(command):
        twist = Twist()
        if math.isfinite(command.linear.x) and math.isfinite(command.angular.z):
            twist.linear.x = max(-max_linear, min(command.linear.x, max_linear))
            twist.angular.z = max(-max_angular, min(command.angular.z, max_angular))
        else:
            rospy.logerr_throttle(1.0, 'Unsafe nonfinite planner command replaced with a stop')
        output.publish(twist)

    rospy.Subscriber('/arena/raw_cmd_vel', Twist, limit, queue_size=5)
    rospy.spin()


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[1]).read_text()))
