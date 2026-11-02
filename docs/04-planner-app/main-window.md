<!-- nav:crumb -->
[Docs home](../README.md) › [Planner app (desktop)](README.md) › **The main window**
<!-- /nav:crumb -->

# The main window

> **In short:** four views on the left (three MRI slices and 3D), one panel on the right with targets, regions, layers, the Plan button, results and the log.

```
┌──────────────────────────────┬──────────────────────────────┐
│  Axial slice                 │  Coronal slice               │  Planner panel
│                              │                              │  ─ Targets (list, Delete, Snap to safe point, Clear all)
├──────────────────────────────┼──────────────────────────────┤  ─ Target regions (Draw outline, New / Delete region,
│  Sagittal slice              │  3D view                     │      "Region only inside the brain")
│                              │  (Front / Left / Right / Top)│  ─ Layers (groups with ticks)
└──────────────────────────────┴──────────────────────────────┘  ─ Show paths, Show electrode contacts
 Toolbar: Open patient folder | Load targets | Save targets |     ─ Plan paths | Stop | progress bar
          Edit robot.toml | Reload robot.toml                    ─ Paths (results table)
                                                                 ─ Export to headset
                                                                 ─ Log
```

## Toolbar

| Button | Action |
|---|---|
| Open patient folder | load a patient (background, ~30 s) - [Opening a patient](opening-a-patient.md) |
| Load targets / Save targets | read / write a targets JSON; Save also writes the region masks |
| Edit robot.toml | opens the file in the default editor |
| Reload robot.toml | reads the file again and reloads the patient |

## Slice views

- mouse wheel = next / previous slice, **Shift + wheel** = 5 slices; the slider above each view does the same;
- **left click** = add a target; **right click** = move the cursor (green cross; the other two views jump to it);
- R/L or A/P letters show the orientation; the title shows the slice number;
- overlays: ticked layers (coloured, semi-transparent), target regions, targets (magenta; filled on this slice, ring on other slices; yellow edge = selected), paths and contacts - see [Planning and results](planning-and-results.md).

## 3D view

Left drag = rotate, wheel or right drag = zoom, middle drag (or Ctrl + left drag) = move; buttons Front / Left / Right / Top reset the camera. Shows the brain (faint), ticked layers (large layers faint, small ones solid), targets, paths with segment colours, contacts and regions.

## Long tasks

Loading, planning and exporting run in a background thread; the progress bar and the status line show the current step. **Stop** ends planning (the paths already found are kept). Closing the window during a task stops it first.

<!-- nav:bar -->
---
← [Install and run](install-and-run.md) | [↑ Planner app (desktop)](README.md) | [Opening a patient](opening-a-patient.md) →
<!-- /nav:bar -->
