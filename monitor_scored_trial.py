"""Stop after a terminal action or a simulation-time deadline."""
import json
from pathlib import Path
import sys
import time

import rospy
from move_base_msgs.msg import MoveBaseActionResult
from actionlib_msgs.msg import GoalStatusArray


def monitor(run):
    protocol = json.loads((run / 'protocol.json').read_text())
    active = {}
    results = {}

    def statuses(message):
        for status in message.status_list:
            if status.status == 1 and status.goal_id.id:
                active[status.goal_id.id] = status.goal_id.stamp.to_sec()

    def result(message):
        results[message.status.goal_id.id] = message

    rospy.init_node('arena_scored_trial', anonymous=True)
    rospy.Subscriber('/move_base/status', GoalStatusArray, statuses)
    rospy.Subscriber('/move_base/result', MoveBaseActionResult, result)
    last_progress = wall_start = time.monotonic()
    previous = latest = 0.0
    outcome = {'outcome': 'invalid', 'reason': 'simulation or goal stopped progressing'}
    while not rospy.is_shutdown():
        wall = time.monotonic()
        latest = rospy.Time.now().to_sec()
        if latest > previous:
            last_progress, previous = wall, latest
        known = dict(active)
        terminal = dict(results)
        if terminal:
            for goal, message in terminal.items():
                known.setdefault(goal, message.status.goal_id.stamp.to_sec())
        if len(known) > 1:
            outcome['reason'] = 'multiple goals reached the action server'
            break
        if known:
            goal, start = next(iter(known.items()))
            limit = start + protocol['trial_sim_seconds']
            message = terminal.get(goal)
            end = message.header.stamp.to_sec() if message else limit
            if message and end <= limit:
                if latest >= end + 0.15:
                    outcome = {'outcome': 'terminal', 'status': message.status.status,
                               'goal_id': goal, 'start': start, 'end': end}
                    break
            elif latest >= limit + 0.25:
                outcome = {'outcome': 'timeout', 'goal_id': goal, 'start': start, 'end': limit}
                break
        if wall - last_progress > 45 or (not known and wall - wall_start > 60) or wall - wall_start > 1200:
            break
        time.sleep(0.025)
    (run / 'termination.json').write_text(json.dumps(outcome, indent=2) + '\n')
    print(json.dumps(outcome), flush=True)


if __name__ == '__main__':
    monitor(Path(sys.argv[1]))
