<!-- nav:crumb -->
[Docs home](../README.md) › [Brain layers and patient data](README.md) › **Layer catalogue**
<!-- /nav:crumb -->

# Layer catalogue

> **In short:** every layer, where it comes from, whether it is measured in this patient, and what the planner does with it.

| Layer | Source exam | Origin | Planner role | Margin / weight |
|---|---|---|---|---|
| arteries | TOF-MRA | patient | **no-go** | 2.0 mm |
| ventricles | T1 segmentation | patient | **no-go** (not checked within 3 mm of a target) | 1.5 mm |
| choroid plexus | T1 segmentation | patient | **no-go** | 1.0 mm |
| midline (falx, interhemispheric fissure, corpus callosum midline) | computed from the segmentation | patient | **no-go**: a path never crosses hemispheres | 1.0 mm |
| hypothalamus (ventral diencephalon) + optic chiasm | T1 segmentation | patient | **no-go** | 2.0 mm |
| brainstem | T1 segmentation | patient | **no-go** | 3.0 mm |
| cerebellum | T1 segmentation | patient | **no-go** | 1.0 mm |
| superior sagittal sinus | anatomical rule | **prior** | **no-go** | 3.0 mm |
| veins | VENAT atlas | **prior** | **no-go** | 1.0 mm |
| corticospinal tract L/R | DTI | patient | **no-go** | 1.0 mm |
| optic radiation L/R | DTI | patient | **no-go** | 1.0 mm |
| outside the brain | brain mask | patient | **no-go** after the straight entry (the arcs stay inside the brain) | 1.0 mm |
| deep grey nuclei (thalamus, caudate, putamen, pallidum, accumbens) | T1 segmentation | patient | soft (may be targets) | w 1.0, 2 mm |
| sulci | T1 | patient | soft | w 1.0, 1.5 mm |
| eloquent cortex | T1 + atlas | **atlas function** | soft | w 2.0, 3 mm |
| arcuate L, uncinate L/R, IFOF L/R | DTI | patient | soft | w 0.5, 3 mm |
| grey / white matter, CSF, hippocampus, amygdala, thalamus, basal ganglia | T1 segmentation | patient | display only | - |
| skull | T1 | **estimate** | display only | - |
| scalp | T1 | patient | display only (its surface = entry points) | - |
| target regions | drawn by the doctor | - | targets | - |

Margins and weights are set in [robot.toml](../03-robot-and-config/config-no-go-and-soft-zones.md); how they act is in [Safety maps](../05-path-planning/safety-maps.md).

## Origin rules

| Origin | Meaning | Tag in app and headset |
|---|---|---|
| patient | measured in this subject's exams | - |
| patient anatomy + atlas function | location from the patient, function assumed from the atlas | `[atlas function]` |
| prior | population atlas or anatomical rule, not imaged | `[PRIOR]` |
| estimate | approximate | `[ESTIMATE]` |

Priors and estimates are replaced automatically when the exam exists (contrast T1 -> veins, CT -> skull).

<!-- nav:bar -->
---
← [Eloquent cortex](eloquent-cortex.md) | [↑ Brain layers and patient data](README.md) | [Headset package and landmarks](headset-package-and-landmarks.md) →
<!-- /nav:bar -->
