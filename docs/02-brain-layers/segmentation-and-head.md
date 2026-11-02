<!-- nav:crumb -->
[Docs home](../README.md) › [Brain layers and patient data](README.md) › **Segmentation and head mask**
<!-- /nav:crumb -->

# Segmentation and head mask

## Brain segmentation (FastSurfer)

> **In short:** a neural network gives every voxel of the T1 a label: which brain region it belongs to. Almost every other layer is built on these labels.

- Tool: **FastSurfer** (`FastSurferCNN/run_prediction.py`), called by `run_pipeline.py`.
- 95 labels: FreeSurfer **aseg** subcortical structures (e.g. 4 = left lateral ventricle, 16 = brainstem, 17 = left hippocampus) and the **DKT** cortical atlas (1000 + n = left cortex region n, 2000 + n = right).
- Outputs, converted from `.mgz` to NIfTI: `aparc.DKTatlas+aseg.deep.nii.gz`, `mask.nii.gz` (brain), `orig.nii.gz` (conformed T1, 1 mm).
- Label names are shown next to every target in the app (`path_planner/labels.py`).

## Head mask

> **In short:** the outline of the whole head. Its surface is the skin where the robot enters.

`pipeline/head_mask.py`:
1. threshold $`T1 > 0.5\cdot\text{Otsu}(T1)`$ (Otsu = automatic threshold between background and tissue);
2. keep the largest connected component (removes noise outside the head);
3. binary closing, 3 iterations;
4. fill holes slice by slice (sinuses, ear canals).

To be replaced by a CT-based mask when CT is available.

## Anatomical layers for display

From the labels (`seeg_prep.py`, planner `layers.py`): grey matter (cortex labels), white matter, CSF, hippocampus, amygdala, thalamus, basal ganglia, ventricles, brainstem, cerebellum. Which of them are danger zones for the robot is decided in `robot.toml`, see [Layer catalogue](layer-catalogue.md).

<!-- nav:bar -->
---
← [Running the pipeline](running-the-pipeline.md) | [↑ Brain layers and patient data](README.md) | [Arteries from TOF-MRA](arteries.md) →
<!-- /nav:bar -->
