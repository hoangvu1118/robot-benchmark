# Arena-Bench integration workspace

Started 2026-11-17. First milestone: original Gazebo / TurtleBot3 Burger /
map2_obs05 scenario running with reference TEB and a recorded outcome.
Reference smoke validation passed on 2026-11-18 (Asia/Saigon). The finalized
recording contains goal success, scans, odometry, transforms and commands.
No scored benchmark campaign has run. Our navigation stack is not connected yet.

## Watch the robot on Windows

From PowerShell in `D:\Project\Robot`:

```powershell
./benchmark_ws/watch-arena.ps1
./benchmark_ws/watch-arena.ps1 -Planner dwa
# Optional: also open RViz (Gazebo-only mode has been verified).
./benchmark_ws/watch-arena.ps1 -Rviz
```

The launcher uses Ubuntu-22.04's Docker integration and WSLg, opens Gazebo,
and runs the supplied map2 scenario with five scripted people. The default
planner is reference TEB. The DWA option uses Arena's reference configuration.
Both reference planners reached the goal in recorded five-pedestrian smoke
runs. The robot is named `turtlebot3` in Gazebo's model list.
The demo enables the upstream automatic scenario reset; it is not a measured trial. Run only
one Arena container at a time because the working world files are shared.
Use `-Distro` or `-LinuxWorkspace` for non-default WSL installations.

Stop the demo from another PowerShell terminal:

```powershell
docker stop arena-benchmark-view
```

### Watch and record one attempt

Use `-Record` to open Gazebo for a single attempt with automatic resets
disabled. Choose one command at a time:

```powershell
.\benchmark_ws\watch-arena.ps1 -Planner teb -Scenario map2_static -Record
.\benchmark_ws\watch-arena.ps1 -Planner teb -Scenario map2_obs10 -Record
```

The robot receives its goal automatically. Leave the terminal running until
`move_base` returns a result or the smoke watchdog ends the run. Gazebo closes
as the runner finishes. The terminal prints the result folder under
`benchmark_ws/results/smoke-*`, which contains `topics.bag`,
`summary.json`, and `bag-summary.json` once the bag is verified. Switch
to `-Planner dwa` to watch and record DWA.

## Score static-only and 10-pedestrian batches

From PowerShell in `D:\Project\Robot`, start Docker Desktop and close the
Arena viewer. To watch either scene before recording, use one of these:

```powershell
.\benchmark_ws\watch-arena.ps1 -Planner teb -Scenario map2_static
.\benchmark_ws\watch-arena.ps1 -Planner teb -Scenario map2_obs10
```

`map2_static` keeps the map geometry and the robot's start and goal from
`map2_obs05`, with zero pedestrians and zero scenario-added static objects. `map2_obs10`
uses Arena's ten scripted pedestrians with the same map, start and goal.

This command scores 20 attempts per reference planner per scenario.
It completes the static-only case first, then moves on to ten pedestrians.

```powershell
.\benchmark_ws\run-arena-batch.ps1 -Trials 20
```

To start with just the static batch, or to check one attempt per planner in
each scenario, choose either command below. Each invocation starts a new batch.

```powershell
.\benchmark_ws\run-arena-batch.ps1 -Trials 20 -Scenario map2_static
.\benchmark_ws\run-arena-batch.ps1 -Trials 1
```

For the ten-pedestrian batch alone, use `-Trials 20 -Scenario map2_obs10`.
Add `-Planner teb` or `-Planner dwa` to restrict a batch to one reference
planner. Keep the terminal open during recording.

Open `results/scored-*/metrics.csv` for the eight metrics grouped by scenario
and planner. `trials.csv` contains the per-attempt values and invalid reasons.
Each recorded attempt has its own scenario, planner, and trial folder, such as
`map2_static/teb/001/`, containing the ROS bag, contact and geometry data,
`score.json`, generated world, effective parameters, and logs.

Both planners use a 300-second simulation-time budget, position tolerance of
0.20 m, heading tolerance of 0.17 rad, forward and reverse speed caps of
0.22 m/s, turn cap of 0.30 rad/s, acceleration limits of 0.50 m/s² and
0.50 rad/s², and a 10 Hz controller rate. The scored launch applies these
settings before startup. DWA's minimum sampled translation and rotation speeds
are 0.01 m/s and 0.02 rad/s so its dynamic window can produce a command from
rest. The default rotate recovery also uses the shared angular limits.
A shared command limiter enforces the speed caps on the robot's input.
The bag records commands both before and after the limiter. Effective
parameters and the protocol are saved for every trial.

Success and timeout rates use valid attempts as the denominator. A planner
abort is a navigation failure. Safety averages include all valid attempts.
Efficiency and smoothness averages use successful attempts with defined
measurements. Clearance is the minimum sampled distance between projected
Gazebo collision shapes at 20 Hz. Cylinders use 24 points around each end.
The scorer counts contact episodes per Gazebo model after a 0.1-second
separation, excluding ground and self-contact. The map's fixed walls form one
collision model. Roughness is undefined for paths shorter than 0.01 m.
Missing data and setup failures stay in the trial CSV with a reason.

Use `-SimSeconds 5` only to exercise the timeout logic in a separate test
batch. The previous diagnostic batch behavior is available with `-Smoke`.
Modified TEB can join the scored comparison later using this protocol.

To inspect the trajectory from a completed single-goal bag, replace
`RUN_DIRECTORY` with the folder under `results`:

```powershell
docker compose -f benchmark_ws/compose.yaml run --rm benchmark -lc 'source /opt/ros/noetic/setup.bash && python3 /work/score_trajectory.py /work/results/RUN_DIRECTORY/topics.bag'
```

The trajectory scorer reports goal time, path length, translational jerk
and heading change per meter. It uses world-sourced Burger odometry between
the accepted goal and terminal result. The smoke bags supply diagnostic
values under the original planner configurations.

GUI forwarding must be launched through WSL: PowerShell-only Docker mounts
did not expose WSLg's display socket on this machine. The helper deliberately
uses `/mnt/d/...` rather than `wslpath`'s Docker bind alias, which breaks
relative sibling mounts. Software rendering is enabled for compatibility.

## Verified reference run

`results/smoke-20261117T171009Z/` (directory timestamp is UTC):

- `topics.bag`: finalized, approximately 52.6 MB; readable without recovery.
- `bag-summary.json`: one move_base result, status 3, "Goal reached."
- Goal stamp 1.502 s; result stamp 206.402 s: 204.900 s simulated elapsed time.
- Recorded command peaks: 0.22 m/s forward magnitude, 0.30 rad/s angular magnitude.
- Contains 10,332 scans and 6,196 odometry messages, plus TF and command data.
- `parameters.yaml`, `scenario.json`, `generated.world`, source/image identities
  and portability diff retained alongside logs.

This proves the reference system runs and its outcome can be recorded. Contact
scoring has not been validated, so it is not a collision-free success claim.
See `integration-audit.md` before connecting the current AMR method.

## Sources

- Arena-Bench checkout: `../arena-bench`, commit
  `519640415718abc7603ff38bc80b2bd22c38b13c` (clean at inspection).
- AMR checkout: `../CollaborativeAMRStockerization`, commit
  `b5f86a2ef46d3ac8b47f7331bbec1133e603b5d5` (clean at inspection).
- `dependencies.json` pins dependencies resolved on 2026-11-17 from the
  upstream repositories named by Arena-Bench. These are NOT established as
  the exact dependency revisions used for the 2022 publication.
- Base image reuses the local ROS image pinned by digest in `Dockerfile`.
  `environment.json` records both image identities.

## Setup (PowerShell, from D:\Project\Robot)

```powershell
./benchmark_ws/fetch-dependencies.ps1
docker compose -f benchmark_ws/compose.yaml build
docker compose -f benchmark_ws/compose.yaml run --rm benchmark /work/build.sh
docker compose -f benchmark_ws/compose.yaml run --rm benchmark -lc 'cp /work/smoke.sh /tmp/arena-smoke.sh && bash /tmp/arena-smoke.sh'
```

The container uses a dedicated Linux volume for compilation and mutable
simulation files. Original source repositories are mounted read-only.
The old upstream setup.sh is not used: it includes malformed shell commands,
an invalid apt package name, host upgrades, and shell-profile modifications.

`smoke.sh` defaults to TEB and accepts `-e ARENA_PLANNER=dwa` on the
Compose `run` command before the service name. It runs without a graphical
window and records topics and a JSON connectivity summary in the Linux volume,
then copies the closed artifacts
under `results/`. It stops after a move_base result or
300 seconds of wall time. A connectivity pass is NOT a collision-free success
claim. Scenario auto-reset is disabled for this single-run check.

The staged copy has a corrected empty maintainer field so catkin accepts the
task-generator package. `portability.patch` records map/scenario path changes.
The generated smoke launch removes concurrent world generation; the same
upstream world generator runs synchronously before Gazebo starts instead.
No planner tuning has been changed for this check.

After a run, verify the finalized bag (replace RUN_DIRECTORY):

```powershell
docker compose -f benchmark_ws/compose.yaml run --rm benchmark -lc 'source /opt/ros/noetic/setup.bash && python3 /work/summarize_bag.py /work/results/RUN_DIRECTORY/topics.bag'
```

Earlier attempts are retained with `INVALID.md` or
`RECORDING-LIMITATION.md`. They must not be scored. Recording directly into
the Windows bind mount caused a shutdown/backlog issue; the Linux-volume
recorder passed a separate short shutdown check (`recorder-check.sh`).
See `integration-audit.md` for the current method and robot adaptations.

## Integration findings

- Start with original Gazebo, not the later Flatland addition.
- Arena's TEB launch already exposes a velocity-output topic argument.
  Our eventual command chain is TEB -> /cmd_vel_nav -> gate -> /cmd_vel.
- Gate supports configurable base frame, laser x offset, width, odometry
  and plan topics. Check remaining geometric assumptions before enabling it.
- Arena Burger base frame is base_footprint; the current AMR default is
  drive_center. Arena laser frame is base_scan.
- Keep benchmark localization: the supplied launch publishes map -> odom;
  do not also start warehouse AMCL or Unity's transform publishers.
- Arena Burger TEB config caps forward speed at 0.22 m/s. Our gate's
  output must obey the same effective limits for matched comparisons.
- Original scenario JSON contains author-machine absolute paths. World
  generation writes into simulator_setup. Patch only the working copy and
  retain the patch manifest before scoring any run.
- Original sensor simulator imports ford_msgs; task generator imports
  pedsim messages/services and PyQt5 even for scripted Gazebo scenarios.
- The upstream TEB fork is pinned separately from the installed ROS TEB;
  establish which is active before treating a run as a reference result.

## Remaining validation

See [the evaluation plan](PROGRESS-SUMMARY.md#arena-bench-evaluation-plan)
for the eight metrics, readiness checks, and paired trial workflow.
