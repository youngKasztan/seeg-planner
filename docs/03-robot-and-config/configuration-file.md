<!-- nav:crumb -->
[Docs home](../README.md) › [Robot and configuration](README.md) › **The configuration file robot.toml**
<!-- /nav:crumb -->

# The configuration file robot.toml

> **In short:** every limit and setting is a number in `path_planner/robot.toml`. Edit, save, press **Reload robot.toml** in the app. No code changes.

## How it is read

- `config.py` reads the file with Python's `tomllib`; `[robot]` and `[planning]` must exist.
- In the Windows exe, a `robot.toml` **next to** `ContinuumPathPlanner.exe` wins over the copy bundled inside, so users can edit it.
- **Edit robot.toml** (toolbar) opens it in the default editor; **Reload robot.toml** reads it again and reloads the whole patient, because margins change the safety maps.
- Distances are in millimetres, angles in degrees.

## Sections

| Section | Page |
|---|---|
| `[robot]` | [Robot and electrode settings](config-robot-and-electrode.md) |
| `[electrode]` | [Robot and electrode settings](config-robot-and-electrode.md) |
| `[planning]` | [Planner settings](config-planning.md) |
| `[entry_zone]` | [Allowed entry zone](config-entry-zone.md) |
| `[no_go.<name>]`, `[avoid.<name>]` | [No-go and soft zones](config-no-go-and-soft-zones.md) |

## Current file

```toml
[robot]
diameter_mm         = 2.0
max_length_mm       = 150.0
min_straight_mm     = 15.0
max_entry_angle_deg = 30.0
arc1_max_length_mm  = 35.0
arc1_min_radius_mm  = 50.0
arc2_max_length_mm  = 35.0
arc2_min_radius_mm  = 30.0

[electrode]
contact_spacing_mm = 5.0
contact_length_mm  = 2.0
first_contact_mm   = 0.0
n_contacts         = 0
on_target_mm       = 1.5

[planning]
search_grid_mm        = 2.0
sample_step_mm        = 1.0
target_tolerance_mm   = 3.0
target_pass_mm        = 1.0
insertion_cost_mm     = 150.0
max_targets_per_path  = 3
group_max_distance_mm = 60.0
min_path_distance_mm  = 2.0
min_entry_distance_mm = 10.0
time_limit_s          = 240
entry_candidates      = 3
optimizer_iterations  = 150
curvature_weight      = 0.1

[entry_zone]
exclude_face               = true
exclude_frontal_sinus      = true
exclude_midline_mm         = 15.0
min_height_above_tragus_mm = 5.0
ear_exclusion_radius_mm    = 30.0

# 12 [no_go.*] and 4 [avoid.*] tables - see "No-go and soft zones"
```

<!-- nav:bar -->
---
← [Robot model](robot-model.md) | [↑ Robot and configuration](README.md) | [Robot and electrode settings](config-robot-and-electrode.md) →
<!-- /nav:bar -->
