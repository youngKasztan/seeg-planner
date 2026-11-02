<!-- nav:crumb -->
[Docs home](../README.md) › [Planner app (desktop)](README.md) › **Target regions**
<!-- /nav:crumb -->

# Target regions

> **In short:** surgeons usually mark an **area**, not a point. Draw its outline on one slice, then on a slice of another view; the region is where the two outlines overlap in 3D. The robot tip may then end anywhere inside it - the planner picks the best point.

## Drawing

1. press **Draw outline** (or **New region**);
2. hold the left mouse button and draw around the area on a slice of one view (e.g. axial); after the first outline the other views jump to the region;
3. draw it on a slice of a second view (e.g. coronal), optionally a third (sagittal);
4. drawing again in the same view replaces that view's outline. Double click a region to rename it; **Delete region** removes it.

**Region only inside the brain** (on by default) clips the region to the brain mask.

## How the 3D region is built (visual hull)

Each outline is extended through the whole volume along its view axis (a prism). The region is the intersection of the prisms:

```math
\text{region} = \bigcap_{\text{views } a} \text{prism}_a \ \cap\ \text{brain}
```

The axial outline gives left-right and front-back, the coronal one adds up-down. With only one outline the region is a slab of ±2 mm (5 slices at 1 mm) around that slice.

## Saving

Outlines are stored in RAS mm in `regions.json` (they survive a different crop of the scan); masks as `regions/<name>.nii.gz` for other tools.

## In planning and in the results

How the tip inside the region is chosen: [Targets check and region tips](../05-path-planning/targets-check-and-region-tips.md). After planning, the chosen tip is a star on the slices; the path list shows how many electrode contacts lie inside the region. The region is exported to the headset as layer `region_<name>` (group *Target regions*, 35 % opacity).

<!-- nav:bar -->
---
← [Targets](targets.md) | [↑ Planner app (desktop)](README.md) | [Layers and the 3D view](layers-and-3d-view.md) →
<!-- /nav:bar -->
