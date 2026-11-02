<!-- nav:crumb -->
[Docs home](../README.md) › [Path planning](README.md) › **Shape optimisation**
<!-- /nav:crumb -->

# Shape optimisation

> **In short:** the shape is improved to be short, gentle and far from danger. Rules that must never be broken are first treated as fines that grow step by step; at the end a strict check decides.

Code: `Planner._shape`, `_evaluate`, `_refine`.

## Variables and bounds

```math
x = [\,a,\ b,\ L_2,\ \kappa_2,\ \varphi_2,\ L_1,\ \kappa_1,\ \varphi_1\,],\qquad v = \text{normalise}(d_0 + a\,e_1 + b\,e_2)
```

| Variable | Meaning | Bounds |
|---|---|---|
| $`a, b`$ | tip direction around $`d_0`$ | [-1.5, 1.5] (up to 56° along one axis, 65° diagonally) |
| $`L_2, \kappa_2, \varphi_2`$ | arc 2: length, curvature, plane | [0, 35] mm, [0, 1/30] mm⁻¹, [-7, 7] rad |
| $`L_1, \kappa_1, \varphi_1`$ | arc 1: length, curvature, plane | [0, 35] mm, [0, 1/50] mm⁻¹, [-7, 7] rad |

The plane range is more than a full turn so that the optimiser can wrap around. `_shape` turns $`x`$ into the robot polyline exactly as in [Robot model](../03-robot-and-config/robot-model.md) (backwards from the target, straight part until the skin) and clips lengths and curvatures, so the arc limits always hold.

## Effective clearance along the shape

For the sampled points $`r_i`$ (entry -> tip):

```math
c^{\text{eff}}_i = \min\Big(C_{\text{strict}}(r_i),\ \ \begin{cases}10^3 & r_i \text{ within 3 mm of a target}\\ \min\big(C_{\text{ign}}(r_i),\ C^{\text{eff}}_{\text{out},i}\big) & \text{otherwise}\end{cases}\Big)
```

$`C^{\text{eff}}_{\text{out},i} = C_{\text{out}}(r_i)`$ from the first point inside the brain onwards and on all arc points; before the robot reaches the brain (scalp, bone, CSF) it is not checked.

## Cost

```math
\text{cost} = \underbrace{L_0 + L_1 + L_2}_{\text{length}} \;+\; \underbrace{\sum_i \tfrac{1}{2}\big(S(r_i) + S(r_{i+1})\big)\,\lVert r_{i+1} - r_i\rVert}_{\int S\,ds\ \text{(soft zones)}}\;+\; w_\kappa\,\underbrace{R_1^2\big(\kappa_1^2 L_1 + \kappa_2^2 L_2\big)}_{\text{bending}}
```

$`w_\kappa`$ = `curvature_weight` = 0.1, $`R_1`$ = `arc1_min_radius_mm` = 50 mm. Bending energy of a rod is proportional to $`\int\kappa^2 ds`$; multiplied by $`R_1^2`$ it becomes a length, so an arc of radius $`R`$ and length $`L`$ costs

```math
w_\kappa\, L\, (R_1/R)^2
```

> **Why:** shorter paths damage less tissue; soft zones are avoided when that is cheap; wide arcs are mechanically easier and more predictable - bending is priced, not forbidden.

## Fines for the hard rules

| Term | Formula | Weight |
|---|---|---|
| $`V_{\text{nogo}}`$ | $`\sum_i \max(0,\ 0.5 - c^{\text{eff}}_i)^2`$ (0.5 mm extra buffer while searching) | 200 |
| $`V_{\text{entry}}`$ | $`\max(0,\ d_{\text{entry}} - 3)^2`$, $`d_{\text{entry}}`$ = distance to the nearest allowed skin point (1.5 x grid) | 20 |
| $`V_{\text{angle}}`$ | $`\max(0,\ \alpha - 30°)^2`$ | 5 |
| $`V_{\text{length}}`$ | $`\max(0,\ L_0 + L_1 + L_2 - 150)^2`$ | 2 |
| $`V_{\text{straight}}`$ | $`\max(0,\ 15 - L_0)^2`$ | 5 |
| $`V_{\text{miss}}`$ | $`\sum_{\text{earlier targets}} \max(0,\ \text{dist} - 0.3)^2`$ | 200 |
| $`V_{\text{over}}`$ | $`\text{over}^2`$, $`\text{over} = 10\max(0, \kappa_2/\kappa_{2,\max} - 1) + \max(0, L_2 - 35)/5`$ (junction shapes only) | 200 |

```math
f(x; w) = \text{cost} + w\,\big(200\,V_{\text{nogo}} + 20\,V_{\text{entry}} + 5\,V_{\text{angle}} + 2\,V_{\text{length}} + 5\,V_{\text{straight}} + 200\,V_{\text{miss}} + 200\,V_{\text{over}}\big)
```

Squared violations grow smoothly from zero, which tells the optimiser in which direction to move. The weights reflect importance: no-go and missed targets dominate everything. A shape that cannot be built (never leaves the head; arc 2 through a junction target longer than 3 x 70 mm) gets $`f = 10^9`$.

## Penalty continuation with Powell

> **Why Powell:** it needs no derivatives. Here the skin entry jumps when the shape changes slightly (the straight line meets the skin at another voxel), so gradients would be unreliable. **Why continuation:** with small fines the optimiser can move freely through slightly unsafe shapes towards a good region; growing fines then push it back to strict safety.

`Planner._refine`: bounded Powell, four stages, each starting from the previous result:

```math
w \in \{0.2,\ 1,\ 5,\ 25\},\qquad \texttt{maxfev} = 150 \times 8 = 1200,\quad \texttt{xtol} = 10^{-2},\quad \texttt{ftol} = 10^{-4}
```

After each stage with $`w \ge 1`$ the [final check](final-check.md) runs; if there are no problems the remaining stages are skipped.

## Worked examples

Bending cost $`0.1 \cdot L \cdot (50/R)^2`$:

| Arc | L (mm) | R (mm) | cost |
|---|---|---|---|
| arc 1 at its minimum radius | 30 | 50 | 3.0 |
| arc 1, wide | 30 | 100 | 0.75 |
| arc 1, very wide | 30 | 200 | 0.19 |
| arc 2 at its minimum radius | 30 | 30 | 8.3 |
| arc 2, wide | 20 | 60 | 1.4 |

Fines at $`w`$ = 25: entry angle 32° -> 25 · 5 · 2² = 500; straight part 13 mm -> 500; one point 0.2 mm inside a margin -> 25 · 200 · 0.7² = 2450. Typical path costs are 60-150, so a feasible shape always wins when one is found.

Trade-off: a straight 80 mm path passing 1 mm from eloquent cortex for 10 mm costs ≈ 80 + 14.3 = 94.3; a curved 85 mm path (arc 1, 30 mm, R 100) that stays 6 mm away costs ≈ 85 + 2.7 + 0.75 = 88.5 -> the curved path is chosen.

<!-- nav:bar -->
---
← [Planning one path](planning-one-path.md) | [↑ Path planning](README.md) | [Final check and best result](final-check.md) →
<!-- /nav:bar -->
