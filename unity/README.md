# Unity app (Quest 3 now, optical see-through headsets later)

Status: scripts compile-checked (C# 9) outside Unity; `RigidFit.cs` unit-tested (2000 random poses).
Not yet run inside Unity / on a headset.

## Quick start on a laptop (no headset needed)
1. Unity Hub -> New project -> **Universal 3D** (Unity 6.3 LTS), name `SeegPlannerApp`.
2. Window -> Package Manager -> `+` -> **Add package by name**, add both:
   - `com.unity.cloud.gltfast`
   - `com.unity.nuget.newtonsoft-json`
3. Copy `Assets/SeegPlanner/` from this repo into the project's `Assets/` folder (Explorer drag and drop).
   Wait for compilation - the Console must show no red errors.
4. In the scene: GameObject -> Create Empty, name it `Patient`, then Add Component:
   `PatientLoader`, `LandmarkRegistration`, `DesktopViewer`.
   - PatientLoader -> Package Folder: the folder with `patient_scene.glb` and `headset_manifest.json`,
     e.g. `C:\Users\<you>\Desktop\dataMedical\IXI057\headset`
   - LandmarkRegistration -> Loader: drag `Patient` onto it
   - DesktopViewer -> Loader and Registration: drag `Patient` onto both
5. Press **Play**. Mouse: left drag rotate, right drag pan, wheel zoom.
   The panel switches layers (origin shown as [PRIOR] / [ESTIMATE]), shows the 5 landmarks, and
   **Simulate registration** places a virtual head at a random pose, "touches" the landmarks with ~2 mm noise
   and reports FRE + target error at the hippocampus - the same code path the headset uses.
   **Edit landmarks**: choose a landmark, click on the skin to move it; it is saved to `headset_manifest.json`.
6. Electrode plan: run `planner/plan_seeg.py` (writes `plan.json` into the same folder), add the component
   `PlanViewer` to `Patient` and drag `Patient` into its Loader field. The plan appears in a panel on the right.


## Headset setup (Quest 3)
1. Unity 6 LTS, template "Mixed Reality" (or 3D URP). Android Build Support for Quest.
2. Packages: OpenXR Plugin, XR Interaction Toolkit, Meta OpenXR (Quest passthrough), `com.unity.cloud.gltfast`, `com.unity.nuget.newtonsoft-json`.
   Use OpenXR features only where possible - the same project then builds for HoloLens 2 (MRTK3), Magic Leap 2 and Android XR.
3. Copy `Assets/SeegPlanner/*.cs` into the project.
4. Scene: an empty object with `PatientLoader`; another with `LandmarkRegistration` (assign the loader and the right-controller tip).
   Bind the controller trigger to `LandmarkRegistration.Capture()`.

## Getting the patient onto the headset
Export with `python tools/export_headset.py --package <package> --head head.nii.gz --t1 orig.nii.gz --out headset/`, then copy the folder to the Quest:
```
adb push headset/. /sdcard/Android/data/<your.app.id>/files/patient/
```
(`PatientLoader` reads `Application.persistentDataPath/patient` by default.)

## Registration (brain inside the head)
Touch the landmarks in the order given by `touch_order` in `headset_manifest.json`: nose tip, nasion, right inner and outer eye corner, right tragus, left inner and outer eye corner, left tragus (eyes closed).
After 3+ points the hologram snaps onto the head; the fiducial registration error (FRE, mm) is logged.
Landmark positions are auto-estimated by the exporter - check them on the model first.
Same maths as `tools/registration.py` (self-test: `python tools/registration.py`).
C# test without Unity: `mcs -out:t.exe unity/Tests/RigidFitTest.cs unity/Assets/SeegPlanner/RigidFit.cs && mono t.exe`
(or any C# compiler).
Next: surface refinement (ICP) with ~50 touched scalp points, then marker tracking via the headset camera.

## Coordinates
MRI RAS mm -> glTF scene metres (see `headset_manifest.json: coordinate_system`). glTFast mirrors X when importing;
`PatientLoader.SceneToUnityLocal` applies the same mirroring to landmark coordinates.
