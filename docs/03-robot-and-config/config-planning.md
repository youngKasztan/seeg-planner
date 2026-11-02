<!-- nav:crumb -->
[Docs home](../README.md) › [Robot and configuration](README.md) › **Planner settings**
<!-- /nav:crumb -->

# Planner settings

## [planning]

| Key | Default | Meaning | Effect of a larger value |
|---|---|---|---|
| `search_grid_mm` | 2.0 | cell size of the coarse route search; the allowed-entry tolerance is 1.5 x this = 3 mm | faster, coarser routes; thin gaps between zones may disappear |
| `sample_step_mm` | 1.0 | spacing of the checked points along the path | faster, a thin zone could slip between samples |
| `target_tolerance_mm` | 3.0 | zones with `ignore_near_targets = true` (ventricles) are not checked this close to a target | targets nearer to such zones become reachable |
| `target_pass_mm` | 1.0 | a path through several targets must pass this close to each earlier target | looser multi-target paths |
| `insertion_cost_mm` | 150.0 | the price of one insertion, in mm of path | the planner tries harder to reach several targets with one path |
| `max_targets_per_path` | 3 | largest group of targets on one path | more groups (combinatorial: slower) |
| `group_max_distance_mm` | 60.0 | consecutive targets of a group further apart are never on one path | more groups tried |
| `min_path_distance_mm` | 2.0 | gap between the surfaces of two robot bodies used together | paths must stay further apart |
| `min_entry_distance_mm` | 10.0 | minimum distance between two skin entries used together | entries spread more |
| `time_limit_s` | 240 | after this many seconds no more groups are tried; every target alone is always planned (code default 120 if missing) | more groups tried, longer planning |
| `entry_candidates` | 3 | Dijkstra entry points tried per path | more starts: better paths, slower |
| `optimizer_iterations` | 150 | x 8 = max. function evaluations per optimisation stage (1200) | more thorough, slower |
| `curvature_weight` | 0.1 | weight of the bending cost (code default 0.5 if missing) | straighter, wider arcs preferred |

How these values are used step by step: [Path planning](../05-path-planning/README.md).

<!-- nav:bar -->
---
← [Robot and electrode settings](config-robot-and-electrode.md) | [↑ Robot and configuration](README.md) | [Allowed entry zone](config-entry-zone.md) →
<!-- /nav:bar -->
