"""Stage a mutable Linux copy; never modify the source checkouts."""
import json
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path('/arena_ws/src')
root.mkdir(parents=True, exist_ok=True)
packages = {
    'arena_bringup', 'simulator_setup', 'task_generator', 'conventional',
    'sensor_simulator', 'arena_intermediate_planner', 'arena_mapping',
    'arena_path_search', 'arena_traj_planner', 'arena_plan_msgs',
    'plan_visualization', 'arena_local_planner_drl',
    'ford_msgs', 'pedsim_msgs', 'pedsim_srvs', 'teb_local_planner',
}
found = set()
for source in [Path('/sources/arena-bench'), Path('/work/dependencies')]:
    for manifest in source.rglob('package.xml'):
        name = ET.parse(manifest).getroot().findtext('name')
        if name not in packages:
            continue
        if name in found:
            raise RuntimeError('Duplicate package: ' + name)
        found.add(name)
        target = root / name
        if not target.exists():
            shutil.copytree(manifest.parent, target, ignore=shutil.ignore_patterns('.git'))
        for script in target.rglob('*.py'):
            script.write_bytes(script.read_bytes().replace(b'\r\n', b'\n'))
            script.chmod(script.stat().st_mode | 0o111)
missing = packages - found
if missing:
    raise RuntimeError('Missing packages: ' + ', '.join(sorted(missing)))

# Catkin rejects this upstream empty maintainer field.
manifest = root / 'task_generator/package.xml'
text = manifest.read_text()
text = text.replace('<maintainer email="elias@open.open"></maintainer>',
                    '<maintainer email="elias@open.open">elias</maintainer>')
manifest.write_text(text)
Path('/work/staged-packages.json').write_text(json.dumps(sorted(found), indent=2))
print('Staged', len(found), 'packages')
