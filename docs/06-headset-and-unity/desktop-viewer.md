<!-- nav:crumb -->
[Docs home](../README.md) › [Headset and Unity](README.md) › **Desktop viewer**
<!-- /nav:crumb -->

# Desktop viewer

> **In short:** look at the patient model on the laptop in Unity's Play mode, without a headset: switch layers, check the robot paths, correct the landmarks and simulate the registration.

`DesktopViewer.cs` (works with the new Input System and the old Input Manager).

## Camera

Left drag = rotate, right drag = pan, wheel = zoom; Zoom slider with - / + / Reset at the top of the panel. Starts looking at the face.

## Panel (left side)

| Control | Action |
|---|---|
| Default / All / None | layer visibility as in the manifest / all / none |
| layer groups | same groups as the planner app; tick a group = all its layers, `>` = expand for single layers; origin tags `[PRIOR]` / `[ESTIMATE]` / `[atlas function]` |
| Robot paths and targets | `paths.glb` on / off |
| Show alignment landmarks | small spheres at the landmarks |
| Edit landmarks (click on the skin) | choose a landmark in the list, click on the skin to move it there; saved to `headset_manifest.json`, so the corrected points are used on the headset too |
| Simulate registration (random head pose) | see below |

## Simulated registration

A virtual head is placed at a random pose (0.5-0.7 m in front, rotated up to ±25° tilt and any turn). Every landmark is "touched" with up to 2.5 mm of random noise; `LandmarkRegistration` moves the hologram onto the virtual head - the same code the headset uses. The panel shows the FRE and the **target error at the left hippocampus** (distance between where the hippocampus is in the virtual head and where the registered hologram puts it).

<!-- nav:bar -->
---
← [Loading the patient in Unity](loading-the-patient-in-unity.md) | [↑ Headset and Unity](README.md) | [Running on the Quest](running-on-the-quest.md) →
<!-- /nav:bar -->
