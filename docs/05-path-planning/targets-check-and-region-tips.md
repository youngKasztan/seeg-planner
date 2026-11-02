<!-- nav:crumb -->
[Docs home](../README.md) › [Path planning](README.md) › **Targets check and region tips**
<!-- /nav:crumb -->

# Targets check and region tips

When **Plan paths** is pressed, these two steps run first.

## 1. Choosing the tip inside each target region

> **In short:** the tip may end anywhere in a region, so the planner picks the point that is easiest to reach safely. After that the region is treated like a normal point target.

`Planner.region_tip(name, mask)`:

1. region voxels (max 20 000, random subsample) -> RAS points;
2. safe points: $`C_{\text{strict}} > 0.3`$ mm (none -> "the whole region lies in no-go zones");
3. depth inside the region (Euclidean distance transform of the region); points at least 1.5 mm inside the edge are preferred (or the deepest available if the region is thin);
4. **one multi-source Dijkstra from all allowed skin entries** over the [cost grid](route-grid-and-entry-points.md) gives the route cost from the skin to every cell; points are ranked by it;
5. the 3 cheapest points at least 5 mm apart are planned in full ([Planning one path](planning-one-path.md), 2 entry candidates each);
6. the tip of the best result (feasible first, then cheapest) is used. Log: `region R1: tip at (x, y, z), reachable, 3 point(s) of the region tried`.

## 2. Target safety check

> **Why:** if the target itself violates a margin, no path can be feasible; checking first saves minutes and tells the user exactly why.

`Planner.check_target(tip)`, for every strict no-go zone (not `ignore_near_targets`, not `outside_of`):

```math
d_z(\text{tip}) - m_z - r < 0 \ \Rightarrow\ \text{too close to zone } z
```

Such targets are left out and reported (`target too close to arteries (1.4 mm) - move it or use 'Snap to safe point'`). The same check runs in the app every time a target is added ([Targets](../04-planner-app/targets.md)).

<!-- nav:bar -->
---
← [Route grid and entry points](route-grid-and-entry-points.md) | [↑ Path planning](README.md) | [Planning one path](planning-one-path.md) →
<!-- /nav:bar -->
