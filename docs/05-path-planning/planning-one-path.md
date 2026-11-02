<!-- nav:crumb -->
[Docs home](../README.md) › [Path planning](README.md) › **Planning one path**
<!-- /nav:crumb -->

# Planning one path

> **In short:** for one target (or one ordered group of targets) the planner finds rough routes from several skin points, turns each into a robot shape, optimises each, and keeps the best. Every target is first planned alone like this.

`Planner.plan_sequence(names, tips)`. Steps in order:

## 1. Dijkstra from the target

> **Why Dijkstra:** it finds the cheapest route through the whole 3D maze, so a good start exists even when the straight line is blocked. One run from the target gives the cost to *every* skin point at once.

`skimage.graph.MCP_Geometric` on the [cost grid](route-grid-and-entry-points.md), 26-neighbourhood, **started at the target**. A step between neighbouring cells $`a, b`$ costs

```math
\text{step}(a, b) = \lVert a - b\rVert \cdot \frac{\text{cost}(a) + \text{cost}(b)}{2}\qquad(\lVert a-b\rVert = 1,\ \sqrt2 \text{ or } \sqrt3 \text{ cells})
```

Cells within `target_tolerance_mm` / grid = 1.5 cells of the target that are free of strict zones get $`\min(\text{cost}, 2)`$, so a target next to the ventricle wall stays reachable. The cumulative cost to every cell is **cached by target position**; the route from any skin cell is read back by traceback.

## 2. Entry candidates

Allowed entries sorted by their cumulative cost; taken greedily if more than 25 mm from those already chosen, up to `entry_candidates` = 3. The rough route from each is one start.

## 3. Legs between targets (groups only)

Between consecutive targets the straight segment is used if $`C_{\text{strict}} > 0`$ at all 30 samples, otherwise the Dijkstra route of the next target. If a leg has no route the group is impossible.

## 4. Straight entries

`_straight_entries` (up to 2): skin points from which the plain straight line to the target is already safe:
- length < `max_length_mm` (150), entry angle < `max_entry_angle_deg` (30°);
- at 100 samples: $`C_{\text{strict}} > 0.3`$, ($`C_{\text{ign}} > 0.3`$ or within 3 mm of the target), and once inside the brain the line stays inside;
- score $`= L + L\cdot\overline{S}`$ (≈ length + $`\int S\,ds`$), lowest first, entries at least 20 mm apart.

For a group, a straight line continuing the line through the first two targets is tried first.

## 5. Fitting the robot shape to a route

> **Why:** a Dijkstra route zig-zags along the grid; the robot can only make straight + 2 arcs. The fit finds the robot shape closest to the route, as a good start for the optimiser.

`Planner._optimise`:
- local frame at the tip: $`d_0`$ = direction from the target to the route point ~10 mm back along the route; $`e_1 \perp d_0`$, $`e_2 = d_0 \times e_1`$;
- minimise over the 8 shape numbers ([Shape optimisation](shape-optimisation.md)):

```math
\text{fit}(x) = \frac{1}{N}\sum_{i} \operatorname{dist}\big(\text{route}_i,\ \text{shape}(x)\big)^2 + 0.01\,\lVert \text{entry}(x) - E\rVert^2
```

  (route points more than 1 mm from the entry $`E`$; nearest-point distances with a k-d tree);
- three Powell starts: arcs 15 mm and straight; arcs 20 mm at half the max. curvature in plane 0; the same in plane π. Powell options: `maxfev` 600, `xtol` 1e-2, `ftol` 1e-3;
- the best fit is passed to the optimisation.

## 6. Order of starts and the best result

1. (groups only) exact arc shapes and junction shapes - [Several targets on one path](several-targets-on-one-path.md);
2. (groups only) the line continuing through the first two targets;
3. the 3 Dijkstra routes;
4. the straight entries not already tried.

Each start goes through fit -> [optimisation](shape-optimisation.md) -> [final check](final-check.md). The best result is chosen by (feasible, -cost). For a single target all starts are tried; for groups the search stops at the first feasible result.

<!-- nav:bar -->
---
← [Targets check and region tips](targets-check-and-region-tips.md) | [↑ Path planning](README.md) | [Shape optimisation](shape-optimisation.md) →
<!-- /nav:bar -->
