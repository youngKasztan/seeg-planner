<!-- nav:crumb -->
[Docs home](../README.md) › [Planner app (desktop)](README.md) › **Opening a patient**
<!-- /nav:crumb -->

# Opening a patient

> **In short:** choose the patient folder made by the pipeline; the program loads the scans and builds the safety maps (~30 s). Saved targets and regions of that patient come back automatically.

## Required files

`orig.nii.gz`, `aparc.DKTatlas+aseg.deep.nii.gz`, `head.nii.gz`; recommended `mask.nii.gz`, the mask files named in `robot.toml` and `headset/headset_manifest.json` (landmarks for the entry zone, needed for the export). Missing optional files are skipped with a `WARNING` in the log.

## What happens

1. scans loaded and put onto one grid (`patient.py`) - [Loading the patient](../05-path-planning/loading-the-patient.md);
2. safety maps built for every zone of `robot.toml` - [Safety maps](../05-path-planning/safety-maps.md);
3. route-search grid and allowed skin entry points prepared - [Route grid and entry points](../05-path-planning/route-grid-and-entry-points.md);
4. the log lists the no-go zones (with volumes in ml), the number of allowed entry points and any warnings;
5. `targets.json` and `regions.json` of this patient are loaded; the layer list and the 3D view are built.

Opening another patient clears the targets and paths of the previous one.

## Files the app writes into the patient folder

| File | When | Content |
|---|---|---|
| `targets.json` | after every change of a target | `[{"name": "T1", "ras_mm": [x, y, z]}, ...]` |
| `regions.json` | after every change of a region | outlines in RAS mm per view, colour |
| `regions/<name>.nii.gz` | Save targets / Export | region masks |
| `headset/plan.json`, `headset/paths.glb`, `headset/patient_scene*.glb`, manifest layers | Export to headset | see [Export to headset](export-to-headset.md) |

<!-- nav:bar -->
---
← [The main window](main-window.md) | [↑ Planner app (desktop)](README.md) | [Targets](targets.md) →
<!-- /nav:bar -->
