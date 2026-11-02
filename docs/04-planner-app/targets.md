<!-- nav:crumb -->
[Docs home](../README.md) › [Planner app (desktop)](README.md) › **Targets**
<!-- /nav:crumb -->

# Targets

> **In short:** left click on a slice adds a target. The program immediately tells which brain region it is in and whether it is too close to a no-go zone.

## Working with targets

| Action | How |
|---|---|
| add | left click on any slice; named `T1`, `T2`, ... |
| select / go to | click its name in the list: all views jump to it |
| rename | double click the name |
| delete / clear | Delete, Clear all |
| move to a safe point | select, then **Snap to safe point** |
| save / load | automatic (`targets.json`); Load targets / Save targets for other files |

Each list line shows: name, anatomical label (e.g. `L hippocampus`, from the segmentation), RAS coordinates in mm and, if needed, `!! too close to arteries (1.4 mm)` in red.

## Safety check of a target

For every no-go zone that is checked at targets (not `ignore_near_targets`, not `outside_brain`):

```math
d_z(\text{target}) - m_z - r < 0 \ \Rightarrow\ \text{too close to zone } z
```

($`d_z`$ = distance to the zone, $`m_z`$ = its margin, $`r`$ = robot radius 1 mm). Such a target cannot get any feasible path, so it is not planned.

## Snap to safe point

Searches a 0.5 mm grid inside a 5 mm ball around the target. A point is safe when its clearance to all strict no-go zones is > 0.3 mm. The nearest safe point **in the same anatomical region** is taken; if there is none, the nearest safe point anywhere. The log says how far the target moved; no safe point within 5 mm -> message, target unchanged.

<!-- nav:bar -->
---
← [Opening a patient](opening-a-patient.md) | [↑ Planner app (desktop)](README.md) | [Target regions](target-regions.md) →
<!-- /nav:bar -->
