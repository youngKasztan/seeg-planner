<!-- nav:crumb -->
[Docs home](../README.md) › [Planner app (desktop)](README.md) › **Layers and the 3D view**
<!-- /nav:crumb -->

# Layers and the 3D view

> **In short:** the layer list shows exactly the zones the planner uses (with their margins and weights) plus some anatomy for orientation. Ticking a layer only changes what you **see**; the planner always uses every zone.

## Groups

| Group | Content | Ticked at start |
|---|---|---|
| **No-go zones** (hard limit, robot must stay out) | every `[no_go.*]` zone of `robot.toml`, with its margin, e.g. `arteries (margin 2.0 mm)`, `ventricles (margin 1.5 mm, ignored near targets)` | all except `outside_brain` (it would cover the whole head) |
| **Soft zones** (allowed, planner keeps away) | every `[avoid.*]` zone with weight and scale | no |
| **Anatomy** (display only) | grey matter, white matter, CSF, hippocampus, amygdala, thalamus, basal ganglia | no |
| **Head** (display only) | skull estimate, scalp | no |

One tick on a group shows / hides the whole group; expand it (arrow) to tick single layers. The group title shows the number of layers. Tags: `[PRIOR]`, `[ESTIMATE]`, `[atlas function]` = not measured in this patient ([Layer catalogue](../02-brain-layers/layer-catalogue.md)). Colours come from the zone names (`layers.ZONE_COLOURS`) or the anatomy catalogue (`layers.CATALOG`); layers that are already a zone are not listed twice.

## On the slices and in 3D

- slices: each ticked layer is a coloured semi-transparent overlay, in list order; regions on top;
- 3D: meshes from marching cubes (coarser for layers > 100 ml); opacity 0.15 for grey/white matter, scalp and skull, 0.2 for other layers > 20 ml, opaque for small ones (vessels, sinus, plexus). See-through meshes are drawn after the solid ones and do not hide what is inside them.

The headset model is built from the same list, see [Export to headset](export-to-headset.md).

<!-- nav:bar -->
---
← [Target regions](target-regions.md) | [↑ Planner app (desktop)](README.md) | [Planning and results](planning-and-results.md) →
<!-- /nav:bar -->
