"""Prepare a scored launch without changing the stock planner files."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import yaml


def configure(run, planner, deadline):
    protocol = json.loads(Path('/work/scoring/protocol.json').read_text())
    if deadline:
        protocol['trial_sim_seconds'] = float(deadline)
    (run / 'protocol.json').write_text(json.dumps(protocol, indent=2) + '\n')

    launch = ET.parse('/arena_ws/smoke.launch')
    original = '$(find arena_bringup)/launch/sublaunch_testing/move_base/move_base_$(arg local_planner).launch'
    include = next(node for node in launch.getroot().findall('include') if node.get('file') == original)
    planner_launch = ET.parse(
        '/arena_ws/src/arena_bringup/launch/sublaunch_testing/move_base/'
        f'move_base_{planner}.launch'
    )
    # The top-level include's extra arguments are for learning-based planners.
    for argument in list(include):
        if argument.get('name') != 'model':
            include.remove(argument)
    ET.SubElement(include, 'arg', name='cmd_vel_topic', value='/arena/raw_cmd_vel')
    include.set('file', str(run / 'scored-move-base.launch'))
    node = planner_launch.getroot().find('node')
    shared = {
        'max_vel_x': protocol['max_linear_m_s'],
        'max_vel_theta': protocol['max_angular_rad_s'],
        'acc_lim_x': protocol['linear_acceleration_m_s2'],
        'acc_lim_theta': protocol['angular_acceleration_rad_s2'],
        'xy_goal_tolerance': protocol['goal_xy_m'],
        'yaw_goal_tolerance': protocol['goal_yaw_rad'],
    }
    if planner == 'dwa':
        namespace = 'DWAPlannerROS'
        shared.update(
            max_vel_trans=protocol['max_linear_m_s'],
            min_vel_x=-protocol['max_linear_m_s'],
            acc_lim_trans=protocol['linear_acceleration_m_s2'],
            # An initial control sample can change speed by 0.05 at 10 Hz.
            min_vel_trans=0.01,
            min_vel_theta=0.02,
        )
    else:
        namespace = 'TebLocalPlannerROS'
        shared['max_vel_x_backwards'] = protocol['max_linear_m_s']
    ET.SubElement(node, 'rosparam', ns=namespace).text = yaml.safe_dump(shared)
    # move_base's default rotate recovery reads its limits from this namespace.
    ET.SubElement(node, 'rosparam', ns='TrajectoryPlannerROS').text = yaml.safe_dump({
        'max_vel_theta': protocol['max_angular_rad_s'],
        'acc_lim_theta': protocol['angular_acceleration_rad_s2'],
        'min_in_place_vel_theta': 0.02,
        'yaw_goal_tolerance': protocol['goal_yaw_rad'],
    })
    node.find("param[@name='controller_frequency']").set('value', str(protocol['controller_hz']))
    planner_launch.write(run / 'scored-move-base.launch', encoding='unicode')
    launch.write(run / 'scored.launch', encoding='unicode')

    world = Path('/arena_ws/src/simulator_setup/worlds/map2/worlds/map2.world')
    tree = ET.parse(world)
    ET.SubElement(tree.getroot().find('world'), 'plugin',
                  name='arena_safety_recorder', filename='libArenaSafetyRecorder.so')
    tree.write(world, encoding='unicode')


if __name__ == '__main__':
    configure(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
