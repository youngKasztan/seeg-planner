<!-- nav:crumb -->
[Docs home](../README.md) › [Robot and configuration](README.md) › **Allowed entry zone**
<!-- /nav:crumb -->

# Allowed entry zone

> **In short:** the robot may not enter through the face, the frontal sinus, close to the midline (sagittal sinus), too low (skull base, neck) or near the ears. These areas are defined relative to landmarks found on the head.

## [entry_zone]

Uses the landmarks in `headset/headset_manifest.json` (see [Headset package and landmarks](../02-brain-layers/headset-package-and-landmarks.md)), expressed in the [anatomical head frame](../01-overview/coordinates-and-units.md) q = (lr, ap, si), in mm. $`n`$ = nasion, $`t`$ = each tragus / preauricular point. A skin point is **removed** when:

| Key | Default | Rule |
|---|---|---|
| `exclude_face` | true | $`q_{ap} > n_{ap} - 35`$ and $`q_{si} < n_{si} + 15`$ (in front of a plane 35 mm behind the nasion and below 15 mm above it) |
| `exclude_frontal_sinus` | true | $`\lvert q_{lr} - n_{lr}\rvert < 25`$ and $`q_{si} < n_{si} + 40`$ and $`q_{ap} > n_{ap} - 40`$ |
| `exclude_midline_mm` | 15.0 | $`\lvert q_{lr} - n_{lr}\rvert \le 15`$ (superior sagittal sinus) |
| `min_height_above_tragus_mm` | 5.0 | $`q_{si} \le \max_t t_{si} + 5`$ (skull base, neck) |
| `ear_exclusion_radius_mm` | 30.0 | $`\lVert q - t\rVert \le 30`$ for any ear landmark |

Without landmarks the zone falls back to the upper half of the head (skin points above the median height) and a warning is logged.

How the skin points and their normals are computed: [Route grid and entry points](../05-path-planning/route-grid-and-entry-points.md).

<!-- nav:bar -->
---
← [Planner settings](config-planning.md) | [↑ Robot and configuration](README.md) | [No-go and soft zones](config-no-go-and-soft-zones.md) →
<!-- /nav:bar -->
