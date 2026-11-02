<!-- nav:crumb -->
[Docs home](../README.md) › [Path planning](README.md) › **Safety maps**
<!-- /nav:crumb -->

# Safety maps

> **In short:** for every point of the head the program stores "how many millimetres of safety are left here". The optimiser later checks thousands of robot shapes just by looking these numbers up.

## Zone masks

`Patient._mask_from(spec)`: one boolean mask per zone of `robot.toml` = union of its `labels`, `mask` files, `computed` surface and `outside_of` region ([zone keys](../03-robot-and-config/config-no-go-and-soft-zones.md)).

**Midline** (`Patient.midline`), with $`d_L`$, $`d_R`$ the distances (mm) to the nearest left / right hemisphere label:

```math
\text{midline} = \big(|d_L - d_R| \le \max(\text{voxel size})\big)\ \wedge\ \big(\min(d_L, d_R) < 15\ \text{mm}\big)\ \wedge\ \text{head}
```

= voxels about equally far from both hemispheres: falx, interhemispheric fissure, midline of the corpus callosum and 3rd ventricle. As a no-go zone it keeps each path in the hemisphere it enters.

## Distance maps and clearance

> **Why:** asking "does the robot touch an artery?" for thousands of shapes would be slow. A distance map answers it with one lookup per point.

For each zone an exact Euclidean distance transform in mm (anisotropic voxels respected): $`d_z(x)`$ = distance to the nearest voxel of the zone, 0 inside. The **clearance** is what is left after the margin $`m_z`$ and the robot radius $`r`$ = `diameter_mm`/2 = 1 mm:

```math
c_z(x) = d_z(x) - m_z - r
```

$`c_z(x) \ge 0`$ <=> a robot body centred at $`x`$ keeps at least the margin from the zone. Zones are merged by the minimum into three maps:

| Map | Zones | Value outside the grid | Rule |
|---|---|---|---|
| $`C_{\text{strict}} = \min_z c_z`$ | no-go zones with `ignore_near_targets = false` | -10 (forbidden) | >= 0 everywhere on the path |
| $`C_{\text{ign}}`$ | no-go zones with `ignore_near_targets = true` (ventricles) | +1000 | >= 0 except within `target_tolerance_mm` = 3 mm of a target |
| $`C_{\text{out}}`$ | `outside_of` zones (`outside_brain`) | -10 | >= 0 once the robot is inside the brain, and on both arcs |

Examples: arteries ($`m`$ = 2 mm) -> the robot axis stays at least 3 mm from any artery voxel; `outside_brain` ($`m`$ = 1 mm) -> the arcs stay at least 2 mm inside the brain mask.

## Soft map

```math
S(x) = \sum_{z\,\in\,\text{soft}} w_z\, e^{-d_z(x)/s_z}
```

$`w_z`$ = `weight`, $`s_z`$ = `scale_mm`. A cost **per millimetre of path** (the path pays $`\int S\,ds`$): inside the zone the full $`w`$, at distance $`s`$ 37 %, at $`3s`$ 5 %. Table of values: [No-go and soft zones](../03-robot-and-config/config-no-go-and-soft-zones.md).

## Sampling

A `Field` samples a map at any RAS point with **trilinear interpolation** (`scipy.ndimage.map_coordinates`, order 1). `Patient.sample(points)` returns $`C_{\text{strict}}, C_{\text{ign}}, C_{\text{out}}, S`$ with one coordinate transform for all four (the optimiser calls it thousands of times).

<!-- nav:bar -->
---
← [Loading the patient](loading-the-patient.md) | [↑ Path planning](README.md) | [Route grid and entry points](route-grid-and-entry-points.md) →
<!-- /nav:bar -->
