# Navigation benchmark: progress and remaining work

Updated: **2026-11-22** (Asia/Saigon).

This handoff summarizes the work completed in this conversation and the saved
artifacts checked on November 22. Runtime and GUI validation took place on
November 18; this document does not imply Docker or Gazebo is currently running.

## Current status

**Arena-Bench runs with its reference TEB planner, the robot has reached its
goal, and a complete recording has been verified. Gazebo viewing on Windows
also works. Our custom navigation stack has not been connected yet.**

The completed work is setup and smoke validation, not a scored comparison of
navigation methods. We have not established collision-free performance or an
improvement over the reference planners.

## Objective we agreed on

Use the benchmark's simulator, robot, sensors and scenarios, then connect our
navigation software to control that robot. Compare reference DWA, reference
TEB and our method under matched conditions, and collect the results.

The larger project has two parts:

1. Public benchmarks: Arena-Bench and DynaBARN in their original setups.
2. Our Unity warehouse: the previously selected 15 AMR test cases.

Implementation so far covers the initial **Arena-Bench reference setup only**.

## Completed work

| Area | What was completed |
|---|---|
| Source audit | Inspected the existing Arena-Bench clone and our AMR navigation code; recorded source revisions and integration assumptions. |
| Isolated environment | Built a ROS Noetic / Gazebo Classic container using the project's existing ROS image. Original source repositories are mounted read-only; builds and mutable simulation files use a separate Linux volume. |
| Dependencies | Downloaded pinned revisions of the TEB fork, pedsim, ford_msgs, actor-collision plugin and evaluator repository. Compiled the packages needed by the reference run and the actor-collision plugin. |
| Portability fixes | Corrected author-machine scenario/mesh paths, Windows Python line endings and an empty package-maintainer field in the staged copy. Made world generation finish before Gazebo starts. |
| Reference run | Ran TurtleBot3 Burger in `map2_obs05.json`, with five scripted people and reference TEB. Verified sensors, transforms, motion commands and goal completion. |
| Recording | Added a bounded smoke runner, runtime monitor and bag summarizer. Verified a finalized bag containing the navigation result. |
| Windows viewing | Added a PowerShell launcher and WSLg GUI configuration. Verified a Gazebo window and live robot motion commands. |
| Integration audit | Documented robot-specific parameters, topic connections, speed limits and differences between our current code and the older plan. |

No custom navigation adapter or validated custom-stack launch has been completed.

## Verified result and evidence

Successful recording: [results/smoke-20261117T171009Z/](results/smoke-20261117T171009Z/).
The directory timestamp is UTC; the run occurred on November 18 in Asia/Saigon.

| Check | Observed result |
|---|---|
| Navigation outcome | One `move_base` result: status **3**, `Goal reached.` |
| Simulated elapsed time from goal to result | **204.900 seconds** |
| Recorded maximum absolute velocity commands | **0.22 m/s** linear; **0.30 rad/s** angular |
| Recorded sensor messages | **10,332** laser scans; **6,196** odometry messages |
| Recording | Finalized `topics.bag`, approximately **52.6 MB**, readable without recovery |
| Collision outcome | **Not evaluated** |

Evidence includes [bag-summary.json](results/smoke-20261117T171009Z/bag-summary.json),
`summary.json`, `topics.bag`, runtime parameters, the scenario, generated world,
logs, dependency/image identities and the portability diff.

These are diagnostic observations from one run, not benchmark averages or
evidence of superiority. Building the collision plugin does not validate
collision detection or scoring.

## Problems encountered and how they were handled

- The upstream installer contains broken commands and host-level changes.
  We used a separate container build instead.
- Editing a running launcher disrupted one early diagnostic recording.
  Launchers are now copied to a fixed temporary file before execution.
- An early recorder shutdown hung, and its recovered bag lacked the final
  seconds. The runner now writes to Linux storage, stops the recorder before
  the simulator, and copies closed artifacts to Windows. The final run passed.
- PowerShell-only Docker mounts did not expose WSLg's display socket.
  The viewer launches Docker through Ubuntu's WSL integration.
- `wslpath` returned a Docker bind alias that broke sibling source mounts.
  The launcher uses the verified `/mnt/d/...` path instead.

Failed/incomplete attempts are retained with `INVALID.md` or
`RECORDING-LIMITATION.md`; do not include them in scored results.

## Important findings before connecting our method

The inspected AMR revision is
`b5f86a2ef46d3ac8b47f7331bbec1133e603b5d5`. Recheck the checkout before
implementation if the AMR code has changed since that inspection.

- **The dynamic costmap converter is disabled in that revision.** The older
  plan described it as enabled. Enabling it must be an explicit configuration
  change, not an unreported part of the baseline.
- Our gate defaults to a `drive_center` frame; Arena Burger uses
  `base_footprint`, with laser frame `base_scan` and laser x offset **-0.032 m**.
- The gate's default spin command is **0.45 rad/s**, above Arena TEB's
  **0.30 rad/s** limit. Match actual output limits, including gate overrides.
- Shield geometry, robot width, nose/tail positions and minimum crawl speed
  need adaptation to the Burger robot.
- Keep Arena's map/localization setup; do not launch the warehouse AMCL,
  Unity bridge or conflicting transform publishers.
- The upstream evaluator package name and the name referenced by the launch
  differ. Resolve and validate that path before enabling its recorder.
- Dependencies are pinned for our setup, but have **not** been established as
  the exact revisions used for the original 2022 paper.

Full details: [integration-audit.md](integration-audit.md).

## Arena-Bench evaluation plan

First score **reference DWA** and **reference TEB** on TurtleBot3 Burger in
`map2_static` and `map2_obs10`. Target 20 scored attempts per planner per
scenario after the pilot. Add **modified TEB** later under the same frozen
protocol. The follow-up comparison is modified TEB versus reference TEB.
DynaBARN and the Unity warehouse suite are later phases.

### Metric definitions to validate during the pilot

Measure each trial from acceptance of its goal to the first terminal outcome
using Gazebo simulation time. Classify valid trials as success, timeout, or
navigation failure. Use a shared goal pose tolerance and simulation-time
deadline. Record simulator, launch, and recorder failures as invalid attempts
with a reason. Keep those attempts in the run log.

| Category | Metric | Proposed scoring rule |
|---|---|---|
| Reliability | Success rate (%) | Fraction of valid trials that reach the shared goal position and heading tolerance before the deadline and report a successful navigation result. Report collisions separately. |
| Reliability | Timeout rate (%) | Fraction of valid trials still active at the shared simulation-time deadline. Record planner aborts and stalls separately when their causes differ. A stalled robot in a running simulator reaches the deadline. |
| Safety | Collision count (episodes/trial) | Count the onset of each robot–obstacle contact episode per Gazebo model. Merge contact across links of the same model and require a 0.1 s separation before a new episode. Exclude ground and self-contact. The fixed walls are one model and each pedestrian is a separate model. |
| Safety | Clearance (m) | Minimum planar gap from the robot to static walls or pedestrians, using projected Gazebo collision geometry sampled at 20 Hz. Assign zero for contact or projected overlap. |
| Efficiency | Time to goal (s) | Simulation time from goal acceptance to verified completion, including waits. Report for successful trials. |
| Efficiency | Path length (m) | Sum planar displacement along the executed simulator trajectory within the trial window. Compare successful trials for efficiency and retain distance to termination for failure analysis. |
| Smoothness | Jerk (m/s³) | RMS magnitude of the third derivative of executed world-frame planar position. Use a fixed simulation-time sampling grid and the same smoothing, differentiation, and endpoint rules for every planner. The diagnostic scorer uses 10 Hz and a nine-sample cubic fit. |
| Smoothness | Trajectory roughness (rad/m) | Sum absolute changes in unwrapped robot heading on the same sampling grid, divided by executed path length. Include in-place turns and mark near-zero-length trials undefined with a fixed threshold. |

Compute safety on all valid trials. Compare jerk and roughness on successful
trials and retain values for failed trials where defined. For efficiency and
smoothness, show the sample count and compare modified TEB directly with
reference TEB on the pairs where both succeeded. Report missing measurements
with a reason. Fix all thresholds and sampling choices after the pilot and
before the measured runs.

### Run order and readiness

1. **Verify baseline recording.** Both reference planners reached the goal in
   the five-pedestrian smoke runs. Reference TEB also reached the goal in
   the static-only and ten-pedestrian smoke runs.
2. **Make the scored configurations comparable.** Use the same robot, map,
   sensors, start and goal poses, obstacle scripts, localization, global
   planner, and reset procedure. Align goals, motion limits, and relevant
   controller settings through planner configurations and verify actual
   commands, including gate overrides. Arena's shipped Burger DWA and TEB
   profiles differ in angular speed (2.75 versus 0.30 rad/s), acceleration,
   goal tolerances, and controller frequency. Save adjusted configs and
   document departures from upstream defaults.
3. **Validate the recorder and scorer before collecting results.** Add
   robot and obstacle ground truth and a contact stream. Check one known
   goal completion, one timeout, one wall contact, one pedestrian contact,
   and one collision-free pass. Verify sustained contact counts once, records
   contain the full goal window, and no motion before a reset enters the
   metrics. `score_trajectory.py` reads accepted-goal-to-result motion from
   existing bags for pilot diagnostics.
4. **Run a paired DWA/TEB pilot, then freeze the protocol.** Use the same
   start, goal, actor timing and seed where supported for each paired setup.
   Restart from a clean state and rotate planner order across pairs. Freeze the
   scenario matrix, trial budget, outcome rules and parameters after the
   pilot. Then run 20 attempts per planner and scenario, retaining failures
   and keeping infrastructure failures visible.
5. **Connect and evaluate modified TEB.** Start with the pinned Arena TEB
   fork for both TEB configurations, and record the AMR components and
   revisions used. The inspected AMR configuration has its dynamic converter
   disabled. Adapt the gate and clearing inputs to Burger, keep Arena
   localization, route planner output through `/cmd_vel_nav` to the gate,
   and verify the gate is the sole publisher on `/cmd_vel`. Verify a goal
   and finalized bag before running the frozen evaluation. If the
   modification stays outside the planner, describe it as a TEB-based stack.

### Storage and publication

Save each trial's bag, scenario, effective parameters, source revisions,
simulation settings, pair ID, simulator and recorder logs, outcome and failure
reason. Use explicit pilot and measured campaign identifiers. Export a trial
CSV and a protocol with metric units and formulas. The scored CSV and report
are deliverables for the measured campaign.

Publish all eight metrics by scenario and planner with valid and invalid
counts, paired modified TEB–reference TEB differences, and uncertainty
intervals. Include the observed tradeoffs. If clearance improves and time to
goal increases, report both changes. A claim about overall improvement requires
a criterion agreed before measurement.

## How to use the current setup

Run from PowerShell in `D:\Project\Robot`, with Docker Desktop running.

The scored batch runner collects 20 TEB and 20 DWA attempts in
`map2_static` followed by 20 TEB and 20 DWA attempts in `map2_obs10`.
It writes a metric summary, trial CSV, and artifacts for each attempt.
See [batch commands and artifact locations](README.md#score-static-only-and-10-pedestrian-batches).

Watch the reference TEB and DWA demonstrations one at a time:

```powershell
.\benchmark_ws\watch-arena.ps1 -Planner teb
.\benchmark_ws\watch-arena.ps1 -Planner dwa
```

Stop the demonstration:

```powershell
docker stop arena-benchmark-view
```

The launcher also accepts `-Rviz`, but that optional mode has not been verified.
The demonstration uses automatic scenario reset, which can restart the scene
on goal proximity or after the upstream three-minute simulation-time timeout.
Use the bounded smoke check to capture a trial without these automatic resets.
Run only one Arena simulation at a time because the working world files are shared.

Run the bounded TEB smoke check and then the DWA check:

```powershell
docker compose -f benchmark_ws/compose.yaml run --rm benchmark -lc 'cp /work/smoke.sh /tmp/arena-smoke.sh && bash /tmp/arena-smoke.sh'
docker compose -f benchmark_ws/compose.yaml run --rm -e ARENA_PLANNER=dwa benchmark -lc 'cp /work/smoke.sh /tmp/arena-smoke.sh && bash /tmp/arena-smoke.sh'
```

The smoke runner saves each attempt under `results/smoke-<planner>-*`.
Check `summary.json` for the navigation outcome and run the bag summarizer
from the README to verify the recording. A wall-clock smoke watchdog is
separate from the simulation-time deadline needed for the scored timeout rate.

Build instructions and further details: [README.md](README.md).

## Key files

| File | Purpose |
|---|---|
| `Dockerfile`, `compose.yaml` | Isolated ROS/Gazebo environment |
| `dependencies.json`, `environment.json` | Recorded dependency, source and image identities |
| `fetch-dependencies.ps1`, `prepare.py`, `build.sh` | Dependency download, staged sources and compilation |
| `portability.py`, `portability.patch` | Scenario/world portability changes |
| `smoke.sh`, `check_runtime.py` | Bounded reference execution and connectivity/outcome checks |
| `summarize_bag.py` | Inspect saved bag contents and diagnostic measurements |
| `compose.gui.yaml`, `watch-arena.ps1`, `view.sh` | Interactive Gazebo viewing through WSLg |
| `integration-audit.md` | Required adaptations and outstanding method decisions |
| `results/smoke-20261117T171009Z/` | Verified reference recording and supporting artifacts |
