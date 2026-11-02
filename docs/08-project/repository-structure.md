<!-- nav:crumb -->
[Docs home](../README.md) › [Project and repository](README.md) › **Repository structure**
<!-- /nav:crumb -->

# Repository structure

```
seeg-planner/
├── README.md                 project summary
├── requirements.txt          pipeline libraries
├── docs/                     this documentation (+ images)
├── pipeline/                 raw exams -> patient layers
├── tools/                    headset export, registration maths, previews, QR markers, docs navigation
├── path_planner/             desktop planner app (+ robot.toml, exe build)
├── unity/                    headset scripts (copy of Assets/SeegPlanner), Unity tests
└── tests/                    automatic tests
```

## Files

| File | Content | Docs |
|---|---|---|
| `pipeline/run_pipeline.py` | runs all pipeline steps | [Running the pipeline](../02-brain-layers/running-the-pipeline.md) |
| `pipeline/head_mask.py` | head mask | [Segmentation and head](../02-brain-layers/segmentation-and-head.md) |
| `pipeline/vessels_mra.py` | arteries | [Arteries](../02-brain-layers/arteries.md) |
| `pipeline/tracts_dti.py` | tracts | [Tracts](../02-brain-layers/white-matter-tracts.md) |
| `pipeline/veins_ct1.py`, `ct_layers.py` | veins, CT | [Veins, sinuses and CT](../02-brain-layers/veins-sinuses-and-ct.md) |
| `pipeline/structural_extras.py`, `atlas_priors.py` | sulci, skull, priors | [Sulci, skull and priors](../02-brain-layers/sulci-skull-and-priors.md) |
| `pipeline/seeg_prep.py` | package, eloquent cortex | [Eloquent cortex](../02-brain-layers/eloquent-cortex.md) |
| `tools/export_headset.py` | headset scene, manifest, landmarks | [Headset package](../02-brain-layers/headset-package-and-landmarks.md) |
| `tools/registration.py` | Kabsch, ICP, FRE/TRE | [Landmark registration](../06-headset-and-unity/landmark-registration.md) |
| `tools/make_qr_markers.py` | printable QR markers | [QR head tracking](../06-headset-and-unity/qr-head-tracking.md) |
| `tools/render_preview.py`, `render_vessel_check.py` | PNG previews | - |
| `tools/docs_nav.py` | rebuilds the navigation of these docs | [Updating these docs](updating-these-docs.md) |
| `path_planner/app.py` | main window | [Planner app](../04-planner-app/README.md) |
| `path_planner/patient.py` | loading, safety maps | [Loading the patient](../05-path-planning/loading-the-patient.md), [Safety maps](../05-path-planning/safety-maps.md) |
| `path_planner/planner.py` | the planner | [Path planning](../05-path-planning/README.md) |
| `path_planner/robot_model.py` | robot shape | [Robot model](../03-robot-and-config/robot-model.md) |
| `path_planner/robot.toml`, `config.py` | configuration | [Configuration file](../03-robot-and-config/configuration-file.md) |
| `path_planner/electrode.py` | contacts | [Electrode contacts](../05-path-planning/electrode-contacts.md) |
| `path_planner/regions.py` | target regions | [Target regions](../04-planner-app/target-regions.md) |
| `path_planner/layers.py`, `labels.py`, `view3d.py` | display layers, label names, 3D view | [Layers and 3D view](../04-planner-app/layers-and-3d-view.md) |
| `path_planner/export.py`, `headset_scene.py` | export | [Export to headset](../04-planner-app/export-to-headset.md) |
| `path_planner/build_exe.bat`, `run_app.bat` | exe build, start | [Install and run](../04-planner-app/install-and-run.md) |
| `unity/Assets/SeegPlanner/*.cs` | headset app | [Headset and Unity](../06-headset-and-unity/README.md) |
| `tests/*.py`, `unity/Tests/` | tests | [Automatic tests](../07-tests-and-results/automatic-tests.md) |

Patient data (NIfTI, headset folders) is never committed (`.gitignore`).

<!-- nav:bar -->
---
← [Project and repository](README.md) | [↑ Project and repository](README.md) | [Limitations and roadmap](limitations-and-roadmap.md) →
<!-- /nav:bar -->
