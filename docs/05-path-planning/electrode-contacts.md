<!-- nav:crumb -->
[Docs home](../README.md) › [Path planning](README.md) › **Electrode contacts**
<!-- /nav:crumb -->

# Electrode contacts

> **In short:** the electrode records only at its contacts, every 5 mm along the path. The program computes where they are and shows which contact lies on each target, so it is visible whether a target is really recorded.

Code: `path_planner/electrode.py`. Contacts are numbered from the tip: contact 1 = deepest (the usual SEEG convention).

## Positions

Depths measured back from the tip along the arc length:

```math
d_k = d_{\text{first}} + k\,\Delta,\qquad k = 0, 1, \dots,\qquad d_k \le L - L_{\text{straight,min}}
```

$`\Delta`$ = `contact_spacing_mm` = 5 mm, $`d_{\text{first}}`$ = `first_contact_mm` = 0, $`L`$ = path length; no contacts in the first `min_straight_mm` = 15 mm under the skin; `n_contacts` > 0 limits the count. Centres and tangents are interpolated along the polyline by arc length.

## On target

For each target of the path the nearest contact centre is found; the target is **recorded** when the distance is at most `on_target_mm` = 1.5 mm (half a 2 mm contact + 0.5 mm).

- The last target is always on contact 1 (the tip is exactly on it).
- An earlier target of a multi-target path is on a contact only if its arc-length distance from the tip is a multiple of 5 mm ± 1.5 mm. This is checked and shown, **not yet optimised** ([Limitations](../08-project/limitations-and-roadmap.md)).

## Where it is shown

Paths table (`18 contacts | T1: #7 1.2 mm | T2: #1 0.0 mm`, red if a target is between contacts), slices (squares, dots, green rings), 3D, `plan.json` (number, depth from tip, position, on target) and `paths.glb` (silver / green bands). See [Planning and results](../04-planner-app/planning-and-results.md).

<!-- nav:bar -->
---
← [Choosing the paths (MILP)](choosing-the-paths-milp.md) | [↑ Path planning](README.md) | [Headset and Unity](../06-headset-and-unity/README.md) →
<!-- /nav:bar -->
