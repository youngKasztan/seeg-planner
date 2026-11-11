<!-- nav:crumb -->
[Docs home](../README.md) › [Headset and Unity](README.md) › **Troubleshooting**
<!-- /nav:crumb -->

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| model pink on the headset | glTFast shaders stripped from the build | materials from `Resources` ([Loading the patient in Unity](loading-the-patient-in-unity.md)); Tools -> SEEG Planner -> Recreate headset materials |
| help text invisible on the headset | `TextMesh` font shader stripped | the panel uses uGUI (already done) |
| `headset_manifest.json not found` | Package Folder wrong / StreamingAssets empty | set Package Folder (Editor) or copy the headset files to `Assets/StreamingAssets/patient/` |
| old plan shown on the headset | old files in StreamingAssets | export again, copy, rebuild (files are copied at every start) |
| hologram does not follow the head | no head marker visible at calibration | panel says "No head marker visible"; show a marker and press grip / release, or touch the landmarks again |
| `QR: no marker provider` + diagnosis `spatial_entity: MISSING` | the runtime does not offer the OpenXR spatial-entity extensions | the QR source is off by default; head tracking uses AprilTags - see [Head tracking with markers](qr-head-tracking.md) |
| `AprilTag camera: no camera image - enable 'Camera Image Support'` | camera image capture is off | Project Settings -> OpenXR (Android) -> Meta Quest: Camera (Passthrough) gear -> Camera Image Support on; rebuild |
| `AprilTag camera: waiting for camera permission` / `DENIED` | the headset camera permission was not granted | answer the permission dialog; or Settings -> Privacy -> App permissions -> camera for the app |
| green frame not on the tag (shifted / tilted) | wrong tag size or camera pose | check `headbandTagMm` / `largeTagMm` and `printScale` against the printed sheet; `camera pose: DEFAULT` on the panel means the camera-in-head pose was not read |
| `QR: spatial data permission granted. Close the app and start it again` | extensions are listed only at start | restart the app once |
| `SphereCollider doesn't exist` errors in the log | physics module stripped | harmless |
| registration poor (large FRE) | wrong landmark touched, landmark position on the model wrong | check the hints (patient's own left/right), correct landmarks in the [Desktop viewer](desktop-viewer.md) |
| button does nothing | input not received | the panel shows *last button*; check controller tracking |

<!-- nav:bar -->
---
← [Head tracking with markers](qr-head-tracking.md) | [↑ Headset and Unity](README.md) | [Tests and results](../07-tests-and-results/README.md) →
<!-- /nav:bar -->
