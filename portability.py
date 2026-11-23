"""Stage the selected map2 scenario and log changes from the upstream source."""
import argparse
import difflib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('scenario', nargs='?', default='map2_obs05',
                    choices=('map2_static', 'map2_obs05', 'map2_obs10'))
args = parser.parse_args()

root = Path('/arena_ws/src')
sim = root / 'simulator_setup'
upstream = Path('/sources/arena-bench/simulator_setup')
patches = []
for script in root.rglob('*.py'):
    script.write_bytes(script.read_bytes().replace(b'\r\n', b'\n'))

def update(path, new, original=None):
    if original is None:
        original = upstream / path.relative_to(sim)
    old = original.read_text()
    if old != new:
        patches.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                       fromfile=str(original), tofile=str(path)))
    path.write_text(new)

world = sim / 'worlds/map2/worlds/map2.world'
original_world = upstream / world.relative_to(sim)
update(world, original_world.read_text().replace('//map2.dae', str(world.parent / 'map2.dae')))
scenario = sim / 'scenarios' / (args.scenario + '.json')
source = upstream / 'scenarios' / ('map2_obs05.json' if args.scenario == 'map2_static' else scenario.name)
data = json.loads(source.read_text())
if args.scenario == 'map2_static':
    data['pedsim_agents'] = []


def relocate(value):
    if isinstance(value, dict):
        return {key: relocate(item) for key, item in value.items()}
    if isinstance(value, list):
        return [relocate(item) for item in value]
    if isinstance(value, str) and '/simulator_setup/' in value:
        return str(sim / value.split('/simulator_setup/', 1)[1])
    return value
update(scenario, json.dumps(relocate(data), indent=2) + '\n', source)

# Generate the world synchronously before Gazebo loads it. The original
# launch starts both simultaneously, which can load a stale actor layout.
launch = root / 'arena_bringup/launch/start_arena_gazebo.launch'
tree = ET.parse(launch)
for node in list(tree.getroot()):
    if node.tag == 'node' and node.get('name') == 'generate_world':
        tree.getroot().remove(node)
tree.write('/arena_ws/smoke.launch', encoding='unicode')
Path('/work/portability.patch').write_text(''.join(patches))
print(f'Prepared {args.scenario} and sequential world-generation launch')
