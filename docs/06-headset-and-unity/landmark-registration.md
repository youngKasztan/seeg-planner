<!-- nav:crumb -->
[Docs home](../README.md) › [Headset and Unity](README.md) › **Landmark registration**
<!-- /nav:crumb -->

# Landmark registration

> **In short:** you touch a few points on the real face and ears with the controller (nose tip, nasion, eye corners, tragus). The same points are known on the model. The program computes the rotation and shift that put the model points onto the touched points, and moves the hologram there.

`LandmarkRegistration.cs` + `RigidFit.cs`; reference implementation `tools/registration.py`.

## Procedure

1. Touch order from the manifest (`touch_order`): nose tip, nasion, right inner eye corner, right outer eye corner, right tragus, left inner eye corner, left outer eye corner, left tragus. Eyes closed.
2. For each: put the red pen tip on the point, press the right trigger (or skip with Y).
3. From the **3rd** point on, the fit is recomputed after every point and the hologram jumps onto the head; the FRE is shown.
4. Check the fit with X (skin on/off) and A (hologram on/off).

## Maths

$`p_i`$ = landmark in the model (PatientRoot local coordinates), $`w_i`$ = touched point (world). The rigid transform minimising

```math
\sum_i \lVert R\,p_i + t - w_i\rVert^2
```

is found in closed form with **Horn's quaternion method** (`RigidFit.Solve`): the centroids $`\bar p`$, $`\bar w`$ are removed, the 3x3 cross-covariance $`S = \sum (p_i - \bar p)(w_i - \bar w)^T`$ is built, and the optimal rotation is the eigenvector of the largest eigenvalue of Horn's symmetric 4x4 matrix $`N(S)`$. Then

```math
t = \bar w - R\,\bar p,\qquad \text{PatientRoot.rotation} = R,\quad \text{PatientRoot.position} = t
```

This is the same result as Kabsch's SVD method in `tools/registration.py`. Fit quality, the **fiducial registration error**:

```math
\text{FRE} = \sqrt{\tfrac{1}{N}\sum_i \lVert R\,p_i + t - w_i\rVert^2}
```

FRE says how well the touched points fit; the error that matters is at the target deep in the brain (**TRE**), which the [desktop simulation](desktop-viewer.md) estimates.

## Refinement (reference code)

`tools/registration.py` also implements **ICP** on many touched skin points against the scalp mesh (iteratively match each point to the nearest surface vertex and re-fit). Self-test (`python tools/registration.py`): 5 landmarks with 2 mm touch noise give a target error below 6 mm; adding ICP with 60 surface points reduces it. Not yet in the headset app.

## Accuracy limits

The pen tip offset is a fixed guess (no tool-tip calibration yet); skin moves under the pen; auto-detected landmarks may need correction ([Desktop viewer](desktop-viewer.md) -> Edit landmarks); the model is IXI057, not the person wearing it.

<!-- nav:bar -->
---
← [Controls and help panel](controls-and-help-panel.md) | [↑ Headset and Unity](README.md) | [QR head tracking](qr-head-tracking.md) →
<!-- /nav:bar -->
