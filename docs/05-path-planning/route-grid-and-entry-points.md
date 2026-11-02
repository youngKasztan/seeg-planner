<!-- nav:crumb -->
[Docs home](../README.md) › [Path planning](README.md) › **Route grid and entry points**
<!-- /nav:crumb -->

# Route grid and entry points

> **In short:** once per patient, a coarse 2 mm "terrain map" is built (how expensive it is to pass each cell), and the skin points where the robot may enter are found together with the direction of the skin there.

Done in `Planner.__init__`, right after loading.

## Cost grid

All safety maps are resampled to `search_grid_mm` = 2 mm (trilinear; head mask nearest neighbour). With $`c = \min(C_{\text{strict}}, C_{\text{ign}})`$, the cost per unit length of a cell is

```math
\text{cost}(x) =
\begin{cases}
\infty & c(x) \le 0 \ \text{ or } x \notin \text{head}\\
2.5 & \text{outside the brain } (C_{\text{out}} \le 0)\text{: scalp, bone, CSF}\\
1 + S(x) + 3\,e^{-\max(c,\,0)/2} & \text{inside the brain}
\end{cases}
```

> **Why:** forbidden cells are walls. Cells near danger are expensive - $`3e^{-c/2}`$ adds 2.34 at 0.5 mm clearance, 1.10 at 2 mm, 0.15 at 6 mm - so the cheapest route keeps a distance by itself. Soft zones add their price. Outside the brain a flat 2.5 is used: that part only serves to get in.

## Allowed skin entry points

1. skin cells = head mask on the 2 mm grid minus its erosion (one-cell shell);
2. outward **normal** = minus the gradient of the head mask smoothed with a Gaussian ($`\sigma`$ = 2 cells = 4 mm), mapped to mm and normalised;
3. the points are expressed in the anatomical frame and filtered with the [entry-zone rules](../03-robot-and-config/config-entry-zone.md) (face, frontal sinus, midline, skull base, ears).

The log reports the number of allowed points; they are stored in a k-d tree for fast "nearest allowed entry" queries.

**Entry angle** of a path = angle between its insertion direction $`u`$ and the inward normal of the nearest allowed point $`j`$:

```math
\alpha = \arccos\big(u \cdot (-n_j)\big)
```

Also prepared: a trilinear head-mask field, used to find where the straight part of the robot leaves the head ([Robot model](../03-robot-and-config/robot-model.md)).

<!-- nav:bar -->
---
← [Safety maps](safety-maps.md) | [↑ Path planning](README.md) | [Targets check and region tips](targets-check-and-region-tips.md) →
<!-- /nav:bar -->
