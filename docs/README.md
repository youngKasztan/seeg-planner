# SEEG Planner documentation

Planning safe curved paths for a concentric-tube continuum robot carrying an SEEG electrode, from MRI exams to a hologram on the patient's head.

> **Research prototype, not for clinical use.** Every path is an automatic proposal that must be reviewed by the surgical team.

**New here?** Read [What the system does](01-overview/what-the-system-does.md) and [Path planning in plain words](01-overview/planning-in-plain-words.md) first. Every page has a short **In short** summary at the top and *previous / next* links at the bottom, so the whole documentation can be read page by page.

<!-- nav:contents -->
## Contents

### 1. [Overview](01-overview/README.md)

- [What the system does](01-overview/what-the-system-does.md) - goal, the three parts, data flow, a typical session
- [Path planning in plain words](01-overview/planning-in-plain-words.md) - the idea of the planner without formulas, and why it is built this way
- [Coordinates and units](01-overview/coordinates-and-units.md) - scanner RAS, voxel grid, anatomical head frame, headset scene
- [Glossary](01-overview/glossary.md) - medical terms and methods in plain words

### 2. [Brain layers and patient data](02-brain-layers/README.md)

- [Running the pipeline](02-brain-layers/running-the-pipeline.md) - one command, required exams, steps, patient folder
- [Segmentation and head mask](02-brain-layers/segmentation-and-head.md) - FastSurfer labels, head mask, anatomy layers
- [Arteries from TOF-MRA](02-brain-layers/arteries.md) - registration, Frangi filter, thresholds, validation (Dice 0.78)
- [White-matter tracts from DTI](02-brain-layers/white-matter-tracts.md) - tractography, automatic bvec check, the 9 tracts
- [Veins, sinuses and CT](02-brain-layers/veins-sinuses-and-ct.md) - contrast-T1 subtraction, CT bone and contacts
- [Sulci, skull and priors](02-brain-layers/sulci-skull-and-priors.md) - sulci, skull estimate, sagittal sinus rule, VENAT venous atlas
- [Eloquent cortex](02-brain-layers/eloquent-cortex.md) - motor, sensory, visual, auditory and language areas from the atlas
- [Layer catalogue](02-brain-layers/layer-catalogue.md) - every layer: source, origin, role in the planner, margin / weight
- [Headset package and landmarks](02-brain-layers/headset-package-and-landmarks.md) - 3D scene, manifest, phantom, automatic face and ear landmarks

### 3. [Robot and configuration](03-robot-and-config/README.md)

- [Robot model](03-robot-and-config/robot-model.md) - straight part + 2 arcs, arc formula, shape built backwards from the target
- [The configuration file robot.toml](03-robot-and-config/configuration-file.md) - how it is read and reloaded, the full current file
- [Robot and electrode settings](03-robot-and-config/config-robot-and-electrode.md) - [robot] and [electrode]: every key
- [Planner settings](03-robot-and-config/config-planning.md) - [planning]: every key and the effect of changing it
- [Allowed entry zone](03-robot-and-config/config-entry-zone.md) - [entry_zone]: face, sinus, midline, skull base, ears
- [No-go and soft zones](03-robot-and-config/config-no-go-and-soft-zones.md) - zone definition, all margins and weights, cost table

### 4. [Planner app (desktop)](04-planner-app/README.md)

- [Install and run](04-planner-app/install-and-run.md) - Python environment, run_app.bat, Windows exe, self-test
- [The main window](04-planner-app/main-window.md) - slice views, 3D view, toolbar, side panel
- [Opening a patient](04-planner-app/opening-a-patient.md) - required files, what is computed, files the app writes
- [Targets](04-planner-app/targets.md) - add, rename, safety check, snap to a safe point
- [Target regions](04-planner-app/target-regions.md) - drawing outlines, visual hull, saving
- [Layers and the 3D view](04-planner-app/layers-and-3d-view.md) - layer groups, tags, colours, transparency
- [Planning and results](04-planner-app/planning-and-results.md) - Plan / Stop, paths table, drawing on the slices, log messages
- [Export to headset](04-planner-app/export-to-headset.md) - plan.json, paths.glb, brain model with the app's layers

### 5. [Path planning](05-path-planning/README.md)

- [Loading the patient](05-path-planning/loading-the-patient.md) - one grid for all scans, crop, resampling
- [Safety maps](05-path-planning/safety-maps.md) - zone masks, midline, distance maps, clearance, soft map
- [Route grid and entry points](05-path-planning/route-grid-and-entry-points.md) - 2 mm cost grid, allowed skin points, normals, entry angle
- [Targets check and region tips](05-path-planning/targets-check-and-region-tips.md) - best tip inside a region, target safety check
- [Planning one path](05-path-planning/planning-one-path.md) - Dijkstra, entry candidates, straight entries, fitting the robot shape
- [Shape optimisation](05-path-planning/shape-optimisation.md) - variables, cost, fines and weights, penalty continuation, examples
- [Final check and best result](05-path-planning/final-check.md) - strict checks, result record, alternatives
- [Several targets on one path](05-path-planning/several-targets-on-one-path.md) - group list, order test, exact arc shapes, pruning, time limit
- [Choosing the paths (MILP)](05-path-planning/choosing-the-paths-milp.md) - why a MILP, formulation, conflicts, worked example
- [Electrode contacts](05-path-planning/electrode-contacts.md) - contact positions, targets on contacts

### 6. [Headset and Unity](06-headset-and-unity/README.md)

- [Hardware and software](06-headset-and-unity/hardware-and-software.md) - Quest 3, target headsets, Unity packages, scripts
- [Unity project setup](06-headset-and-unity/unity-project-setup.md) - project, packages, scene objects, patient files
- [Loading the patient in Unity](06-headset-and-unity/loading-the-patient-in-unity.md) - PatientLoader, build-safe materials, coordinates
- [Desktop viewer](06-headset-and-unity/desktop-viewer.md) - laptop viewer, edit landmarks, simulated registration
- [Running on the Quest](06-headset-and-unity/running-on-the-quest.md) - Meta Horizon Link, Android build, logs
- [Controls and help panel](06-headset-and-unity/controls-and-help-panel.md) - controller buttons, pen tip, panel
- [Landmark registration](06-headset-and-unity/landmark-registration.md) - procedure, Horn / Kabsch maths, FRE, ICP
- [QR head tracking](06-headset-and-unity/qr-head-tracking.md) - following the head, markers, settings, current status
- [Troubleshooting](06-headset-and-unity/troubleshooting.md) - pink model, no marker provider, other problems

### 7. [Tests and results](07-tests-and-results/README.md)

- [Automatic tests](07-tests-and-results/automatic-tests.md) - planner tests on a synthetic head, other tests
- [Results on IXI057](07-tests-and-results/results-ixi057.md) - pipeline numbers, planner and headset results

### 8. [Project and repository](08-project/README.md)

- [Repository structure](08-project/repository-structure.md) - every file and its documentation page
- [Limitations and roadmap](08-project/limitations-and-roadmap.md) - what is not done yet, next steps
- [Data sources and safety](08-project/data-sources.md) - test data, atlases, regulatory note
- [Updating these docs](08-project/updating-these-docs.md) - how the docs are organised and regenerated
<!-- /nav:contents -->
