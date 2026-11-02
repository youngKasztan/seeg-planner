<!-- nav:crumb -->
[Docs home](../README.md) › [Headset and Unity](README.md) › **Unity project setup**
<!-- /nav:crumb -->

# Unity project setup

> **In short:** a Universal 3D (URP) project with two packages, the scripts copied in, and one scene object `Patient` that carries the components.

## Laptop project (no headset needed)

1. Unity Hub -> New project -> **Universal 3D** (Unity 6.3 LTS), name `SeegPlannerApp`.
2. Window -> Package Manager -> `+` -> **Add package by name**: `com.unity.cloud.gltfast` and `com.unity.nuget.newtonsoft-json`.
3. Copy `unity/Assets/SeegPlanner/` of the repo into the project's `Assets/`. Wait for compilation; the Console must show no red errors. `SeegMaterials.cs` creates `Assets/SeegPlanner/Resources/SeegLitOpaque.mat` and `SeegLitTransparent.mat` automatically.
4. Scene: GameObject -> Create Empty, name `Patient`, Add Component: `PatientLoader`, `LandmarkRegistration`, `DesktopViewer`.
   - PatientLoader -> **Package Folder**: the patient's `headset` folder, e.g. `C:\Users\MSI\Desktop\dataMedical\IXI057\headset`;
   - LandmarkRegistration -> Loader = `Patient`;
   - DesktopViewer -> Loader and Registration = `Patient`.
5. **Play** -> [Desktop viewer](desktop-viewer.md).

## Additions for the Quest

1. Package Manager: **Unity OpenXR: Meta** (brings OpenXR and AR Foundation).
2. Project Settings -> XR Plug-in Management: OpenXR on (Windows tab for Link, Android tab for the headset build); feature group **Meta Quest**, **Oculus Touch Controller Profile**; Project Validation -> Fix All.
3. URP asset: HDR off; Renderer: post-processing off (passthrough needs the alpha channel).
4. Scene: delete Main Camera; GameObject -> XR -> **AR Session** and **XR Origin (Mobile AR)**; on its camera: Background Type = Solid Color, black with alpha 0; Tracked Pose Driver = XR HMD centerEyePosition / centerEyeRotation.
5. `Patient`: add **`QuestControls`** (Loader and Registration = `Patient`). It adds `HeadMarkerTracker` by itself. `DesktopViewer` may stay: it does not move the camera while a headset is active.

## Patient files for a headset build

Copy the content of the patient's `headset` folder (`headset_manifest.json`, `patient_scene*.glb`, `paths.glb`, `plan.json`) into `Assets/StreamingAssets/patient/`. At start the app copies them to its data folder ([Loading the patient in Unity](loading-the-patient-in-unity.md)), so a new build always shows the newly exported plan and no `adb push` is needed.

Folders on the development laptop: project `C:\Users\MSI\UnityProjects\SeegPlannerApp`, test copy `C:\Users\MSI\Desktop\UnityKopia\SeegPlannerApp`.

<!-- nav:bar -->
---
← [Hardware and software](hardware-and-software.md) | [↑ Headset and Unity](README.md) | [Loading the patient in Unity](loading-the-patient-in-unity.md) →
<!-- /nav:bar -->
