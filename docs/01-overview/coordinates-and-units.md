<!-- nav:crumb -->
[Docs home](../README.md) › [Overview](README.md) › **Coordinates and units**
<!-- /nav:crumb -->

# Coordinates and units

> **In short:** everything in the planner is in millimetres in the scanner's coordinates (RAS). The headset uses metres, centred on the head, with "up" as the y axis. One fixed formula converts between them.

| System | Axes | Unit | Used for |
|---|---|---|---|
| Scanner RAS | x = right, y = anterior, z = superior | mm | all planner geometry; `plan.json` fields `*_ras_mm` |
| Voxel index (i, j, k) | array axes of the T1 after reorientation to RAS | voxel | masks and safety maps; the affine matrix maps voxel -> RAS |
| Coarse grid | voxel grid resampled to 2 mm | cell | route search, skin entry points |
| Anatomical head frame q = (lr, ap, si) | left->right, back->front, up; origin = cortex centre | mm | entry-zone rules (work even if the head was tilted in the scanner) |
| Headset scene | glTF: x = right, y = up, z = posterior; origin = head centre | m | `patient_scene.glb`, `paths.glb`, `plan.json` fields `*_scene_m` |

## Anatomical head frame

Built from the segmentation (`patient.head_frame`, also in `tools/export_headset.py`) using centroids of label groups:

```math
\mathbf{lr} = \frac{c_{\text{right hem.}} - c_{\text{left hem.}}}{\lVert\cdot\rVert},\qquad
\mathbf{ap} = \frac{(c_{\text{frontal}} - c_{\text{occipital}}) - ((c_{\text{frontal}} - c_{\text{occipital}})\cdot\mathbf{lr})\,\mathbf{lr}}{\lVert\cdot\rVert},\qquad
\mathbf{si} = \mathbf{lr}\times\mathbf{ap}
```

A point $`p`$ (RAS) in this frame: $`q = F\,(p - c)`$ with $`F = [\mathbf{lr};\ \mathbf{ap};\ \mathbf{si}]`$ and $`c`$ the centroid of all cortical labels.

## RAS -> headset scene

Same formula in `tools/export_headset.py` and `path_planner/export.py`:

```math
p_{\text{scene}} = \frac{R\,(p_{\text{RAS}} - c_{\text{head}})}{1000},\qquad
R = \begin{bmatrix}1&0&0\\0&0&1\\0&-1&0\end{bmatrix}\quad(\det R = +1,\ \text{a pure rotation})
```

$`c_{\text{head}}`$ = mean of the scalp mesh vertices, stored as `coordinate_system.head_centre_ras_mm` in `headset_manifest.json` together with the full 4x4 matrix `ras_mm_to_scene_m`. In Unity, glTFast converts glTF (right-handed) to Unity (left-handed) by mirroring x; `PatientLoader.SceneToUnityLocal` applies the same mirroring to landmark coordinates read from the manifest.

## Units in robot.toml

Distances in millimetres, angles in degrees. Inside the code, arc plane angles are radians and curvatures are 1/mm.

<!-- nav:bar -->
---
← [Path planning in plain words](planning-in-plain-words.md) | [↑ Overview](README.md) | [Glossary](glossary.md) →
<!-- /nav:bar -->
