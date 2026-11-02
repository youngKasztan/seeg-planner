<!-- nav:crumb -->
[Docs home](../README.md) › [Planner app (desktop)](README.md) › **Planning and results**
<!-- /nav:crumb -->

# Planning and results

> **In short:** press **Plan paths**. Each target is planned alone (~10-30 s each), then groups of targets on one path until the time limit; the best combination is chosen automatically. The results appear on the slices, in 3D, in the Paths table and in the log.

## Running

- **Plan paths** needs a patient and at least one target or region. Region tips are chosen first, then the targets are planned.
- Progress bar and status: e.g. `planning T1 -> T2 (95 s)`.
- **Stop** ends planning at any moment; if the single paths are done, they are kept and the best combination of what was found is used.
- To change limits: Edit robot.toml -> save -> Reload robot.toml -> Plan again.

What happens inside: [Path planning](../05-path-planning/README.md).

## Paths table

| Column | Example | Meaning |
|---|---|---|
| Path | `P1: T1 -> T2` | path number (in its colour) and the targets in the order the robot reaches them |
| Length | `96 mm` | skin to tip |
| Shape (mm) | `straight 31 \| arc 1 24 mm R 131 \| arc 2 5 mm R 79` | length of each part and radius of each arc ("straight" for an arc with no bend) |
| Closest no-go | `arteries 0.4 mm` | the no-go zone the robot surface comes closest to, and that distance (see note) |
| Electrode contacts on targets | `18 contacts \| T1: #7 1.2 mm \| T2: #1 0.0 mm` | number of contacts, and for each target the nearest contact (1 = deepest) and its distance; red = a target between two contacts |

Note on *Closest no-go*: the value is the distance from the robot **surface** to the zone (distance - robot radius). A feasible path always has this value >= the zone's margin.

## On the slices

- each path is drawn in segment colours: **cyan** straight, **yellow** arc 1, **orange** arc 2 - faint everywhere, bold where it crosses the current slice (± 2 slices), with its number `P1` at the crossing;
- **Show electrode contacts**: white squares = contacts on this slice, faint dots = on other slices, **green ring** = a contact lying on a target;
- star = tip chosen inside a target region.

## Log messages

| Message | Meaning |
|---|---|
| `T1: OK (length 96 mm: straight 31 \| arc 1 ...)` | feasible path found |
| `T1 -> T2: rejected: entry angle 34 deg; misses T1 by 2.3 mm` | best attempt broke these rules |
| `T3: target too close to arteries (1.4 mm) - move it or use 'Snap to safe point'` | target itself violates a margin |
| `n group(s) skipped: they cannot be shorter than separate paths` | pruned groups |
| `time limit 240 s reached: n group(s) not tried` | raise `time_limit_s` to try them |
| `NOT REACHED: T4 - its paths come too close to another chosen path` | lost to a collision in the final choice |
| `region R1: tip at (...), reachable, 3 point(s) of the region tried` | region tip chosen |
| `path 1 electrode: ...` | contacts per path |

<!-- nav:bar -->
---
← [Layers and the 3D view](layers-and-3d-view.md) | [↑ Planner app (desktop)](README.md) | [Export to headset](export-to-headset.md) →
<!-- /nav:bar -->
