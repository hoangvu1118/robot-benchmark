# Integration audit: next step after reference smoke validation

Inspected AMR commit b5f86a2ef46d3ac8b47f7331bbec1133e603b5d5.
This is an implementation checklist, not a validated custom-stack launch.

## Current method differs from the November 8 plan

`teb_warehouse.yaml` currently sets `costmap_converter_plugin: ""` and
`costmap_converter_spin_thread: false`. Do not label this checkout as using
the dynamic converter. Preserve this actual baseline when evaluating the
current method; treat enabling a converter as a separate configuration.

The gate uses the newer shield / crossing-yield / spin-first logic. Its default
spin_w is 0.45 rad/s. Arena Burger TEB uses max_vel_theta 0.30 rad/s. Limit
the actual output for a matched comparison, including gate overrides.

## Concrete interface mapping

| Input / parameter | Arena Burger | Required action |
|---|---|---|
| Laser input | /scan, frame base_scan | Existing LaserScan interface; topic remapping sufficient |
| Odometry | /odom | Existing Odometry interface |
| Robot frame | base_footprint | Override gate base_frame (AMR default drive_center) |
| Laser offset | x = -0.032 m; y = 0; yaw = 0 | Set gate laser_x = -0.032; matches its axis-aligned scan assumption |
| Benchmark navigation footprint | x [-0.105, 0.041], y [-0.105, 0.105] m | Adapt nose_x, tail_x, half_width and shields; verify collision body too |
| Planner output | /cmd_vel | Route only move_base output to /cmd_vel_nav |
| Gate output | /cmd_vel | Sole velocity command publisher when gate enabled |
| Global plan | Default Navfn topic to verify live | Bind gate plan_topic after observing actual publisher |
| Map | /map | Reuse benchmark map and transforms |
| Localization | Supplied map-to-odom transform | Do not launch warehouse AMCL or laser transform publisher |
| Linear/angular planner limits | 0.22 m/s, 0.30 rad/s | Match effective command limits across methods |

Sources: Arena Burger URDF scan_joint, conventional/config/turtlebot3_burger
costmap_common_params.yaml and teb_local_planner_params.yaml; AMR
scripts/velocity_gate.py and src/amr_navigation/gate_logic.py.

## Remaining decisions and checks

1. Preserve the upstream TEB fork for the reproduced reference. Decide whether
   custom-stack tests also use that fork or the warehouse TEB version; report
   any version difference and isolate it in an additional comparison.
2. Start with the current gate and clearing components as an explicit method
   adaptation. Do not silently add the converter described in older notes.
3. Adapt shield margins separately from physical body dimensions. The current
   dimensions and minimum crawl speed were tuned for the warehouse AMR.
4. Verify clearing-scan handling with the Burger's full-angle laser and include
   its output in both costmaps only when clearing is enabled.
5. Check controller/planner patience against gate hold_timeout. Freeze these
   across matched comparisons or explicitly label whole-stack differences.
6. Verify only one final velocity publisher, valid TF at scan timestamps,
   actual output limits, and clean reset of all gate history between trials.
7. Integrate and validate scoring. Current smoke recordings do not establish
   collision-free success. Upstream evaluator package name is arena-evaluation
   while the launch references arena_evaluation; resolve that mismatch before
   enabling the upstream recorder.
