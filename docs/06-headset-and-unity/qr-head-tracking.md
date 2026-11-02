<!-- nav:crumb -->
[Docs home](../README.md) › [Headset and Unity](README.md) › **QR head tracking**
<!-- /nav:crumb -->

# QR head tracking

> **In short:** after registration the hologram is fixed in the room. If the person moves the head, the hologram would stay behind. QR codes fixed on the head (headband; in the operating room the head clamp) are tracked by the headset; the hologram is tied to them and moves with the head.

`HeadMarkerTracker.cs` (added automatically by `QuestControls`).

## How it works

1. **Registration** puts `PatientRoot` on the head ([Landmark registration](landmark-registration.md)).
2. **Calibrate** (automatically after every landmark from the 3rd on, and when the grip is released): for every head QR code visible now, the pose of the hologram relative to the code is stored:

```math
T_{\text{marker}\leftarrow\text{root}} = T_{\text{world}\leftarrow\text{marker}}^{-1}\; T_{\text{world}\leftarrow\text{root}}
```

3. **Every frame:** each visible calibrated code predicts where the hologram should be,

```math
T_{\text{world}\leftarrow\text{root}} = T_{\text{world}\leftarrow\text{marker}}(\text{now})\;T_{\text{marker}\leftarrow\text{root}}
```

   the predictions are averaged (positions averaged; quaternions flipped into the same hemisphere, summed and normalised) and smoothed:

```math
k = 1 - e^{-\Delta t / 0.15\,\text{s}},\qquad p \leftarrow p + k\,(p_{\text{target}} - p),\qquad q \leftarrow \text{slerp}(q, q_{\text{target}}, k)
```

   jumps larger than 10 cm snap at once ($`k = 1`$). With no code visible the hologram keeps its last pose.
4. Codes that were not visible during calibration are **added automatically** the first time they are seen together with an already calibrated code (a headband with 3 codes keeps working when the head turns).
5. Anchors are stored per QR **text**, not per tracking id, because the runtime may report a code again under a new id.

## Markers

`python tools/make_qr_markers.py` (needs `segno`, `reportlab`) writes:
- `seeg_qr_markers.pdf`: `SEEG-HEAD-1` 100 mm, `SEEG-HEAD-2/3` 70 mm;
- `seeg_qr_markers_small.pdf`: size test 60 / 50 / 40 / 30 mm + headband set 3 x 50 mm.

Text convention `SEEG-HEAD-<n>-<size>MM` (e.g. `SEEG-HEAD-1-50MM`); only codes starting with `SEEG-HEAD` are used. QR version 1 with a 4-module quiet zone; print at 100 % and check the 100 mm scale bar. **printScale** = 0.95 because the university printer prints 100 mm as 95 mm; the panel shows measured / expected size of each code as a check.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `headPrefix` | `SEEG-HEAD` | codes treated as head markers |
| `printScale` | 0.95 | real printed size / nominal size |
| `smoothing` | 0.15 s | time constant (0 = no smoothing) |
| `snapDistance` | 0.10 m | larger jumps are applied at once |

Project Settings -> XR Plug-in Management -> OpenXR (Android): feature group **Spatial Entities** with **Markers** only; QR detection on, markers fixed size with the real printed side length (e.g. 0.0475 m), "Markers are static" **off** (the head moves). The app asks for the permission `com.oculus.permission.USE_SCENE` (spatial data); after the first "Allow" it must be restarted once.

## Status line on the panel

e.g. `QR: 1-50MM 48/47.5mm*  2-50MM (lost)  FOLLOWING`: per code its number, measured / expected size, `*` = anchored, `(lost)` = not tracked now; mode `FOLLOWING`, `PAUSED (grip)` or `not anchored`. Without a provider: `QR: no marker provider` with a diagnosis line - see [Troubleshooting](troubleshooting.md).

## Current status (2026-10-28)

Code ready. On the test Quest 3 the OpenXR runtime does **not** offer the extension `XR_EXT_spatial_entity` (nor any other spatial-entity / scene extension), so AR Foundation gets no marker provider. Most likely the university's device management blocks spatial data. Options: a personal / unmanaged headset; Passthrough Camera API + OpenCV ArUco markers; or HoloLens 2 / Magic Leap 2 with native QR tracking.

<!-- nav:bar -->
---
← [Landmark registration](landmark-registration.md) | [↑ Headset and Unity](README.md) | [Troubleshooting](troubleshooting.md) →
<!-- /nav:bar -->
