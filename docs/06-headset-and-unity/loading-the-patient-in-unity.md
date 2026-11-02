<!-- nav:crumb -->
[Docs home](../README.md) › [Headset and Unity](README.md) › **Loading the patient in Unity**
<!-- /nav:crumb -->

# Loading the patient in Unity

> **In short:** `PatientLoader` reads the manifest, loads the brain model and the robot paths into one parent object `PatientRoot`, replaces the materials with ones that survive a headset build, and switches layers on or off. Moving `PatientRoot` moves everything together.

## Steps (`PatientLoader.Load`)

1. **Folder**: `Package Folder` if it exists (Editor on the PC); otherwise `Application.persistentDataPath/patient`, filled at every start by copying from `StreamingAssets/patient` (headset app). Copied files: `headset_manifest.json`, `patient_scene.glb`, `patient_scene_lite.glb`, `paths.glb`, `plan.json`.
2. **Manifest** read (Newtonsoft JSON).
3. **PatientRoot** created, 0.6 m in front of the user until registration places it on the head.
4. **Brain**: `patient_scene.glb` (or `_lite` if *Use Lite Scene*) loaded with glTFast under `PatientRoot`.
5. **Paths**: `paths.glb` loaded under the same root (same coordinates), if present.
6. Every node becomes a named layer (`Layers[name]`).
7. **Build-safe materials** (below).
8. Initial visibility of each layer from the manifest (`visible`).

## Why the model was pink, and the fix

glTFast creates its materials at run time from shaders that a player build strips, so on the headset the model showed up pink. `Editor/SeegMaterials.cs` creates two URP Lit materials in `Assets/SeegPlanner/Resources` (always included in a build): `SeegLitOpaque` and `SeegLitTransparent`. `PatientLoader` replaces every material with a copy of one of them and sets the colour:

| Node | Colour from |
|---|---|
| brain layers | manifest `layers[].colour` and `opacity` (transparent material if opacity < 1) |
| `path_<n>_straight / _arc1 / _arc2` | segment colours: cyan / yellow / orange |
| `path_<n>_contacts` / `_contacts_on_target` | silver / green |
| `target_<name>` | magenta |

If the materials are missing: Tools -> SEEG Planner -> **Recreate headset materials**.

## Coordinates

The `.glb` files are in metres, y up, centred on the head ([Coordinates](../01-overview/coordinates-and-units.md)). glTFast mirrors x when importing (glTF is right-handed, Unity left-handed); `PatientLoader.SceneToUnityLocal` applies the same mirroring to landmark and region-centroid coordinates from the manifest (`LandmarkLocal`, `RegionLocal`), so landmarks and meshes match.

## Layer control

`SetLayerVisible(name, on)` switches a node; the groups (No-go zones, Soft zones, Anatomy, Head, Target regions) come from the manifest written by the planner's export, so the headset has exactly the layers of the desktop app.

<!-- nav:bar -->
---
← [Unity project setup](unity-project-setup.md) | [↑ Headset and Unity](README.md) | [Desktop viewer](desktop-viewer.md) →
<!-- /nav:bar -->
