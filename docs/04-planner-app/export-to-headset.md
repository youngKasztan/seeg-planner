<!-- nav:crumb -->
[Docs home](../README.md) › [Planner app (desktop)](README.md) › **Export to headset**
<!-- /nav:crumb -->

# Export to headset

> **In short:** writes the plan and the brain model into the patient's `headset/` folder (~1 min), in headset coordinates and with the same layers as in the app. Then copy that folder into the Unity project.

Needs planned paths and `headset/headset_manifest.json` (from `tools/export_headset.py`). Targets and regions are saved first.

## Files

| File | Content |
|---|---|
| `plan.json` | targets, paths (points, shape, checks, electrode contacts) in RAS mm and in scene metres |
| `paths.glb` | 3D tubes of the paths, contacts, target spheres |
| `patient_scene.glb` / `patient_scene_lite.glb` | brain model with the app's layers and groups (600 k / 200 k triangles) |
| `headset_manifest.json` | `layers` replaced by the app's layers; landmarks and coordinate system unchanged |
| `*_pipeline.glb`, `headset_manifest_pipeline.json` | the pipeline's original files, kept once |

## plan.json

```
{
  "note": "Research prototype - automatic proposal, must be reviewed by the surgical team.",
  "robot": { ...[robot] of robot.toml... },
  "targets": { "<name>": {"ras_mm": [x,y,z], "scene_m": [x,y,z]} },
  "paths": [ {
      "id": "path_1", "targets": ["T1", "T2"], "colour": [r,g,b],
      "shape": {"straight_mm", "arc1_mm", "arc1_radius_mm", "arc1_plane_deg",
                "arc2_mm", "arc2_radius_mm", "arc2_plane_deg"},
      "segment_of_point": [0,...,1,...,2], "segments": {"0": "straight", "1": "arc 1", "2": "arc 2"},
      "entry_ras_mm", "entry_scene_m", "points_ras_mm", "points_scene_m",
      "length_mm", "min_bend_radius_mm", "entry_angle_deg", "total_turn_deg",
      "min_clearance_mm": {"<zone>": mm, ...}, "feasible": true, "problems": [],
      "electrode": {"contact_spacing_mm", "contact_length_mm",
                    "contacts": [{"n", "depth_from_tip_mm", "ras_mm", "scene_m", "on_target"}],
                    "targets": {"<name>": {"contact", "distance_mm", "on_contact"}}}
  } ],
  "not_reached": [...], "target_problems": {...}
}
```

## paths.glb

| Node | Mesh | Colour |
|---|---|---|
| `path_<n>_straight`, `path_<n>_arc1`, `path_<n>_arc2` | tube with the robot radius along each part (12 sides, parallel-transport frames so it does not twist, rounded tip) | cyan, yellow, orange |
| `path_<n>_contacts` | short cylinders (radius 1.4 x robot radius, contact length) | silver |
| `path_<n>_contacts_on_target` | the same for contacts lying on a target | green |
| `target_<name>` | sphere, 2 mm | magenta |

## patient_scene.glb

Built by `headset_scene.py` from the app's layer list (brain, No-go zones, Soft zones, Anatomy, Head, Target regions; `outside_brain` left out): marching cubes (Gaussian smoothing σ = 1 voxel for layers > 20 ml, 0.5 for thin ones), Taubin smoothing (10 iterations), quadric decimation to the triangle budget. Opacity: grey/white matter, scalp, skull 0.15; target regions 0.35; others 0.2 if > 20 ml, else opaque. Each layer is a named node; the manifest lists name, group, category, visibility, opacity, colour, origin and volume.

Coordinates: $`p_{\text{scene}} = R\,(p_{\text{RAS}} - c_{\text{head}})/1000`$, identical for all three files ([Coordinates](../01-overview/coordinates-and-units.md)).

Next: [Unity project setup](../06-headset-and-unity/unity-project-setup.md).

<!-- nav:bar -->
---
← [Planning and results](planning-and-results.md) | [↑ Planner app (desktop)](README.md) | [Path planning](../05-path-planning/README.md) →
<!-- /nav:bar -->
