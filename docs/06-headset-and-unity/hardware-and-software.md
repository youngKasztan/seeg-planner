<!-- nav:crumb -->
[Docs home](../README.md) › [Headset and Unity](README.md) › **Hardware and software**
<!-- /nav:crumb -->

# Hardware and software

> **In short:** development on a Meta Quest 3 (passthrough: the real world is filmed and shown with the hologram on top). The target are optical see-through headsets (HoloLens 2, Magic Leap 2), where the real world is seen directly. Using only OpenXR features keeps the project portable.

## Hardware

| Device | Role | Notes |
|---|---|---|
| Meta Quest 3 | development headset | passthrough video; Horizon OS 2.x; the test unit is managed by the university |
| HoloLens 2 / Magic Leap 2 | target | optical see-through; native QR / marker tracking |
| Windows laptop | planner app, Unity Editor, builds | |

## Software stack

| Component | Version | Why |
|---|---|---|
| Unity | 6.3 LTS (6000.3.25f1), URP | long-term support, mobile rendering |
| Unity OpenXR: Meta | 2.6.1 | Quest support through the open OpenXR standard |
| AR Foundation | 6.6.0 | passthrough camera, marker (QR) manager |
| glTFast (`com.unity.cloud.gltfast`) | 6.x | loads the `.glb` files at run time |
| Newtonsoft JSON (`com.unity.nuget.newtonsoft-json`) | - | reads `headset_manifest.json` and `plan.json` |
| Unity OpenXR: Spatial Entities (`com.unity.xr.spatialentities-openxr`) | 6.6.2 | QR marker provider (test project only) |

No Meta XR SDK / MRUK is used, to stay on OpenXR.

## Scripts (`unity/Assets/SeegPlanner/`)

| Script | Role | Page |
|---|---|---|
| `PatientLoader.cs` | loads the brain, paths and manifest; materials; layer visibility | [Loading the patient in Unity](loading-the-patient-in-unity.md) |
| `Editor/SeegMaterials.cs` | creates the build-safe materials | [Loading the patient in Unity](loading-the-patient-in-unity.md) |
| `DesktopViewer.cs` | laptop viewer without a headset | [Desktop viewer](desktop-viewer.md) |
| `QuestControls.cs` | controllers and the help panel | [Controls and help panel](controls-and-help-panel.md) |
| `LandmarkRegistration.cs`, `RigidFit.cs` | aligning the hologram with the head | [Landmark registration](landmark-registration.md) |
| `HeadMarkerTracker.cs` | following the head with QR codes | [QR head tracking](qr-head-tracking.md) |

The Unity project itself (`SeegPlannerApp`) is not in git; the scripts are copied into `unity/Assets/SeegPlanner/` of the repo. Patient files in `StreamingAssets/patient` are never committed.

<!-- nav:bar -->
---
← [Headset and Unity](README.md) | [↑ Headset and Unity](README.md) | [Unity project setup](unity-project-setup.md) →
<!-- /nav:bar -->
