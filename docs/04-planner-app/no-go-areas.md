<!-- nav:crumb -->
[Docs home](../README.md) › [Planner app (desktop)](README.md) › **No-go areas drawn by the doctor**
<!-- /nav:crumb -->

# No-go areas drawn by the doctor

> **In short:** after planning, you may decide that a path goes through a place you do not like or consider dangerous (a vessel not visible on the scans, a lesion, a scar under the entry, ...). Draw a **no-go area** around that place and press **Plan paths** again: every path is planned anew and keeps out of the area, with all robot limits and margins still checked.

## Why re-plan instead of moving the path by hand

> **Why:** a path moved by hand would skip everything that makes it safe and feasible: the robot's shape (straight part + 2 arcs with limited radius), the margins to every no-go zone, the entry angle and zone, and the gap to the other paths. A drawn no-go area is just one more no-go zone for the planner, so the new path goes through exactly the same optimisation and the same strict final check as any other path.

## How to use it

1. Plan the paths as usual and look at them on the slices and in 3D.
2. Press **New no-go area**. A new entry `N1` appears in the list as `[NO-GO] N1` (red), and *Draw outline* switches on.
3. Hold the left mouse button and draw around the place on a slice. Draw it on a slice of a **second view** as well, to set its extent in depth (exactly as for [target regions](target-regions.md)).
4. The log tells you which current paths pass through it, e.g. `N1: P1 pass(es) through this no-go area - press 'Plan paths' to re-plan`.
5. Press **Plan paths**. The log says `1 drawn no-go area(s) added to the no-go zones`, and the new paths avoid the area.
6. To remove it: select it in the list, **Delete**, and plan again.

## What happens inside

| Step | Detail |
|---|---|
| shape of the area | outlines in 1-3 views -> visual hull ([Target regions](target-regions.md)); clipped to the **head** (not the brain), so an area may also cover a skin entry or the bone |
| one outline only | a slab of ±`user_nogo_slab_mm` (5 mm) around the slice, thicker than for target regions, so a path cannot slip just above or below it |
| safety maps | the area gets its own distance map and becomes a strict no-go zone `user_<name>` with margin `user_nogo_margin_mm` (1 mm): $`C_{\text{strict}} = \min\big(C_{\text{strict}}^{\text{robot.toml}},\ d_{\text{area}} - m - r\big)`$ ([Safety maps](../05-path-planning/safety-maps.md#no-go-areas-drawn-by-the-doctor)) |
| route search | the 2 mm cost grid is rebuilt and all cached Dijkstra routes are forgotten (`Planner.refresh_fields`); the skin entry points stay |
| when | at the start of **Plan paths**, only if the drawn areas changed since the last planning (a few seconds) |
| results | the paths table shows the clearance to the area when it is the closest no-go zone (e.g. `user_N1 2.7 mm`); a target inside an area is reported like a target inside any no-go zone |
| saving | `regions.json` (with `"kind": "nogo"`), `regions/<name>.nii.gz` on *Save targets* |
| headset | exported as layer `nogo_<name>` in the group *No-go zones* (35 % opacity) |

## Settings (`robot.toml`, `[planning]`)

| Key | Default | Meaning |
|---|---|---|
| `user_nogo_margin_mm` | 1.0 | gap the robot surface keeps from a drawn no-go area (the robot radius is added) |
| `user_nogo_slab_mm` | 5.0 | half-thickness of an area drawn in one view only |

## Tips

- Draw the area a little larger than the place you want to avoid: the margin is measured from its edge, and the planner will use any gap you leave.
- If no path is found after adding areas, the log explains why (`NOT REACHED: ...`); make the area smaller or delete it.
- The drawn areas are not part of `robot.toml`: they belong to this patient and are stored with the patient's regions.

<!-- nav:bar -->
---
← [Target regions](target-regions.md) | [↑ Planner app (desktop)](README.md) | [Layers and the 3D view](layers-and-3d-view.md) →
<!-- /nav:bar -->
