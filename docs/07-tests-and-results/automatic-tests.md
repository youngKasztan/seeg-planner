<!-- nav:crumb -->
[Docs home](../README.md) › [Tests and results](README.md) › **Automatic tests**
<!-- /nav:crumb -->

# Automatic tests

## Planner (`python tests/test_path_planner.py`)

> **In short:** a synthetic head (no patient data needed) where the right answer is known. Each test checks one behaviour of the planner.

Synthetic patient: 1 mm grid, head = sphere of radius 48 mm, brain = 40 mm, four labelled quadrants (left/right x front/back), optional artery tube.

| # | Test | Checks |
|---|---|---|
| 1 | an artery runs right above a target | margin kept; no arc tighter than allowed; the arcs are really circular (constant curvature) |
| 2 | two targets on one vertical line | both reached with **one** path |
| 3 | target inside a no-go zone | reported, not planned |
| 4 | Stop | raises `Cancelled` during the single paths; keeps the single paths if stopped during groups |
| 5 | time limit 0 s | every target alone is still planned, no group tried |
| 6 | the two cheapest paths cross | the selection uses the alternative entry |
| 7 | midline zone | a line from the left to the right hemisphere is blocked, a left-only line is not |
| 8 | electrode contacts | every 5 mm of arc length from the tip, none in the straight entry; a target 20 mm above the tip is on contact 5 |
| 9 | target region from an axial and a coronal outline (a box) | the tip is inside the region |
| 10 | two targets not on one line | one path: straight through the first, then bending onto the second (exact arc start) |

Self-test on a real patient: `python path_planner/app.py --selftest <patient folder>` ([Install and run](../04-planner-app/install-and-run.md)).

## Other tests

| Command | Checks |
|---|---|
| `python tests/test_ct_phantom.py` | CT layers on a phantom |
| `python tests/test_veins_phantom.py` | vein extraction on a phantom |
| `python tools/registration.py` | Kabsch + ICP on a synthetic head with touch noise |
| `unity/Tests/RigidFitTest.cs` (`mcs` + `mono`, outside Unity) | Horn's method on 2000 random poses |

<!-- nav:bar -->
---
← [Tests and results](README.md) | [↑ Tests and results](README.md) | [Results on IXI057](results-ixi057.md) →
<!-- /nav:bar -->
