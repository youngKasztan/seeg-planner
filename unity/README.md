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
   Zoom: wheel or the Zoom slider (- / + / Reset) at the top of the panel.
   The panel switches layers in the same groups as the planner app (No-go zones, Soft zones, Anatomy, Head:
   tick a group to show all of it, > to choose single layers; origin shown as [PRIOR] / [ESTIMATE]),
   switches the robot paths on/off, shows the landmarks, and
   **Simulate registration** places a virtual head at a random pose, "touches" the landmarks with ~2 mm noise
   and reports FRE + target error at the hippocampus - the same code path the headset uses.
   **Edit landmarks**: choose a landmark, click on the skin to move it; it is saved to `headset_manifest.json`.
6. Robot paths: plan them in `path_planner/app.py` and press *Export to headset*; `paths.glb` and the brain model
   with the planner's layers (`patient_scene.glb`) are written to the same folder and loaded on the next Play.


## Headset over Meta Horizon Link (Quest 3, no Android build)
Play mode in the Editor runs on the headset, with passthrough; the patient files are read from the PC folder.
1. PC: Meta Horizon Link app -> Settings -> General -> OpenXR Runtime: Meta Horizon Link active;
   Settings -> Developer (or Beta): Developer runtime features ON, Pass-through over Meta Horizon Link ON.
2. Package Manager: install **Unity OpenXR: Meta** (brings OpenXR + AR Foundation).
3. Project Settings -> XR Plug-in Management -> Windows tab: OpenXR ON; OpenXR -> Windows tab: add
   Oculus Touch Controller Profile, enable feature group Meta Quest; Project Validation: Fix All.
4. URP asset: HDR off; Renderer: Post-processing off (passthrough needs the alpha channel).
5. Scene: delete Main Camera; GameObject -> XR -> AR Session and XR Origin (Mobile AR);
   on its Main Camera: Background Type = Solid Color, colour black with alpha 0;
   Tracked Pose Driver: position / rotation input = XR HMD centerEyePosition / centerEyeRotation.
6. `Patient` object: add `QuestControls` (Loader and Registration = Patient). DesktopViewer stays: its panel
   is on the PC screen, and it does not move the camera while a headset is active.
7. Headset: Quick Settings -> Link -> connect; press Play in Unity.
Controls: right trigger = record landmark at the red pen tip, left Y = skip landmark, right B = restart,
right A = hologram on/off, left X = skin on/off, left grip = carry the brain.

## Headset app on the Quest (passthrough without Link)
Meta Horizon Link v83+ has no Beta tab, so "Passthrough over Link" cannot be switched on; an app built for the
headset always has passthrough.
1. Unity Hub -> Installs -> Unity 6.3 -> Add modules: Android Build Support (+ OpenJDK, Android SDK & NDK).
2. Headset in Developer Mode (Meta Horizon phone app of the headset's admin account -> Devices -> Developer Mode).
3. Copy the patient's `headset` folder content (headset_manifest.json, patient_scene*.glb, paths.glb, plan.json)
   into `Assets/StreamingAssets/patient/`. PatientLoader copies them out of the app at start (no adb).
4. File -> Build Profiles -> Android -> Switch Platform. XR Plug-in Management -> Android tab: OpenXR,
   Meta Quest feature group, Oculus Touch Controller Profile; Project Validation -> Fix All.
5. Headset on USB, allow USB debugging in the headset; Build Profiles -> Android -> Run Device = Quest 3 -> Build And Run.

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
