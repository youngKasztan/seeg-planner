<!-- nav:crumb -->
[Docs home](../README.md) › [Path planning](README.md) › **Final check and best result**
<!-- /nav:crumb -->

# Final check and best result

> **In short:** safety is decided here - without fines and without the search buffer. Any broken rule = the path is rejected and never used.

## Checks (`Planner._result`)

| Check | Rejected when | Log message |
|---|---|---|
| no-go zones | $`\min_i c^{\text{eff}}_i < -0.1`$ mm | `enters a no-go zone (x mm too close)` |
| entry zone | nearest allowed entry farther than 3.5 mm | `entry outside the allowed skin zone` |
| entry angle | > 30.5° | `entry angle x deg` |
| length | > 150.5 mm | `too long (x mm)` |
| straight part | < 14.5 mm | `straight part only x mm` |
| arc 2 | $`\kappa_2 > 1.03\,\kappa_{2,\max}`$ or $`L_2 > 35.5`$ mm | `arc 2 out of range` |
| earlier targets | robot farther than `target_pass_mm` = 1 mm | `misses <name> by x mm` |

The small tolerances (0.1-0.5 mm, 3 %) absorb the 1 mm sampling of the path. Arc 1 needs no check: its limits are enforced when the shape is built.

## Result record (`PathResult`)

targets in order, entry point, points with segment labels, feasible flag, cost, length, smallest radius used, entry angle, total turn, **clearance of the robot surface to every zone** (distance - radius), list of problems, and the shape: `straight_mm`, `arc1_mm`, `arc1_radius_mm`, `arc1_plane_deg`, `arc2_mm`, `arc2_radius_mm`, `arc2_plane_deg`.

## Best of all starts

Compared by (feasible, -cost): any feasible path beats any infeasible one, then the lower cost wins. If no start is feasible, the best attempt is logged with its problems (`rejected: ...`).

## Alternatives

For a single target every feasible result is remembered. `alternatives()` returns up to 3 of them, cheapest first, with **entries at least 15 mm apart**. They go into the pool of the [MILP](choosing-the-paths-milp.md), so that if the best path of one target collides with another path, a different entry can be used.

<!-- nav:bar -->
---
← [Shape optimisation](shape-optimisation.md) | [↑ Path planning](README.md) | [Several targets on one path](several-targets-on-one-path.md) →
<!-- /nav:bar -->
