<!-- nav:crumb -->
[Docs home](../README.md) › [Headset and Unity](README.md) › **Controls and help panel**
<!-- /nav:crumb -->

# Controls and help panel

> **In short:** the right controller has a red pen tip for touching landmarks; buttons show/hide the hologram and the skin, restart, skip a landmark, and the left grip carries the brain by hand. A panel above the left controller always says what to do next.

`QuestControls.cs` (works over Link and in the Android build; does nothing without a headset).

## Buttons

| Button | Action |
|---|---|
| Right trigger | record the current landmark at the red pen tip (8 cm in front of the right controller, 2 cm down) |
| Left Y / left stick click | skip the current landmark (e.g. eye corners that are hard to reach); at least 3 must be touched |
| Right B | start again: forget all touched points, stop following the QR codes, hologram visible in front of you (0.5 m, facing you) |
| Right A | hologram on / off (to look at the real head) |
| Left X | skin (scalp layer) on / off, to check the fit |
| Left grip (hold) | carry the hologram with the left controller (manual placement); pauses QR following; on release, if the hologram follows QR codes, it is re-anchored at the new place |

## Help panel

A world-space UI panel (uGUI, 600 px scaled to 0.24 m) floats above the left controller, or low in front of the face when the left controller is not tracked. It shows:
- the landmark to touch now, in capitals, with its hint from the manifest (e.g. "deepest point of the nose bridge, between the eyes") and "patient's own left / right";
- the last status ("Recorded: nasion. Fit error (FRE) 2.3 mm", "Anchored to the head QR code(s)", ...);
- the QR status line ([QR head tracking](qr-head-tracking.md));
- the button list and the **last button** pressed, so a button that seems to do nothing is easy to spot.

(The panel uses uGUI with the built-in font because the font shader of the old `TextMesh` text is stripped from builds - the earlier help text was invisible on the headset.)

<!-- nav:bar -->
---
← [Running on the Quest](running-on-the-quest.md) | [↑ Headset and Unity](README.md) | [Landmark registration](landmark-registration.md) →
<!-- /nav:bar -->
