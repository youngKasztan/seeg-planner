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
| hologram does not follow the head | no head QR code visible at calibration | panel says "No head QR code visible"; show a code and press grip / release, or touch the landmarks again |
| `QR: no marker provider` + diagnosis `spatial_entity: MISSING` | the runtime does not offer the OpenXR spatial-entity extensions | see [QR head tracking](qr-head-tracking.md), current status |
| `QR: spatial data permission granted. Close the app and start it again` | extensions are listed only at start | restart the app once |
| `SphereCollider doesn't exist` errors in the log | physics module stripped | harmless |
| registration poor (large FRE) | wrong landmark touched, landmark position on the model wrong | check the hints (patient's own left/right), correct landmarks in the [Desktop viewer](desktop-viewer.md) |
| button does nothing | input not received | the panel shows *last button*; check controller tracking |

<!-- nav:bar -->
---
← [QR head tracking](qr-head-tracking.md) | [↑ Headset and Unity](README.md) | [Tests and results](../07-tests-and-results/README.md) →
<!-- /nav:bar -->
