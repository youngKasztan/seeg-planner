# Unity app (Quest 3 now, optical see-through headsets later)

Status: **scripts written, not yet compiled** - first step on the headset is to create the project and test them.

## Setup
1. Unity 6 LTS, template "Mixed Reality" (or 3D URP). Android Build Support for Quest.
2. Packages: OpenXR Plugin, XR Interaction Toolkit, Meta OpenXR (Quest passthrough), `com.unity.cloud.gltfast`, `com.unity.nuget.newtonsoft-json`.
   Use OpenXR features only where possible - the same project then builds for HoloLens 2 (MRTK3), Magic Leap 2 and Android XR.
3. Copy `Assets/SeegPlanner/*.cs` into the project.
4. Scene: an empty object with `PatientLoader`; another with `LandmarkRegistration` (assign the loader and the right-controller tip).
   Bind the controller trigger to `LandmarkRegistration.Capture()`.

## Getting the patient onto the headset
Export with `python tools/export_headset.py --package <package> --head head.nii.gz --out headset/`, then copy the folder to the Quest:
```
adb push headset/. /sdcard/Android/data/<your.app.id>/files/patient/
```
(`PatientLoader` reads `Application.persistentDataPath/patient` by default.)

## Registration (brain inside the head)
Touch, in order: nose tip, nasion, left pre-auricular point, right pre-auricular point, vertex.
After 3+ points the hologram snaps onto the head; the fiducial registration error (FRE, mm) is logged.
Landmark positions are auto-estimated by the exporter - check them on the model first.
Same maths as `tools/registration.py` (self-test: `python tools/registration.py`).
Next: surface refinement (ICP) with ~50 touched scalp points, then marker tracking via the headset camera.

## Coordinates
MRI RAS mm -> glTF scene metres (see `headset_manifest.json: coordinate_system`). glTFast mirrors X when importing;
`PatientLoader.SceneToUnityLocal` applies the same mirroring to landmark coordinates.
