<!-- nav:crumb -->
[Docs home](../README.md) › [Path planning](README.md) › **Loading the patient**
<!-- /nav:crumb -->

# Loading the patient

> **In short:** all scans are put onto one common 3D grid, so that every structure can be looked up at the same coordinates.

`patient.Patient` (runs in the background when a folder is opened, ~30 s):

1. **T1** loaded and reoriented to RAS (`nib.as_closest_canonical`); its voxel grid is the planning grid (IXI057 ≈ 1 mm).
2. **Crop** to the head bounding box + 5 voxels (memory and speed); the affine is shifted accordingly.
3. **Resampling** of every other volume onto this grid (`scipy.ndimage.affine_transform`):
   - segmentation labels and binary masks: nearest neighbour;
   - mask files from `robot.toml` (vessels, tracts, priors): **trilinear, then > 0.25**. Plain nearest-neighbour resampling would lose thin vessels from scans with a different grid.
4. Head mask holes filled in 3D (`binary_fill_holes`).
5. Anatomical head frame computed ([Coordinates](../01-overview/coordinates-and-units.md)); headset manifest (landmarks) read.
6. Safety maps built ([next page](safety-maps.md)), then the `Planner` object prepares the route search ([Route grid](route-grid-and-entry-points.md)).

<!-- nav:bar -->
---
← [Path planning](README.md) | [↑ Path planning](README.md) | [Safety maps](safety-maps.md) →
<!-- /nav:bar -->
