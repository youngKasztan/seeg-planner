<!-- nav:crumb -->
[Docs home](../README.md) › [Brain layers and patient data](README.md) › **Sulci, skull and priors**
<!-- /nav:crumb -->

# Sulci, skull and priors

> **In short:** some layers can be derived from the T1 alone (sulci), some only roughly (skull), and some are not visible at all without extra exams (veins, sagittal sinus). For those, the pipeline uses a population atlas or an anatomical rule and marks the layer as **PRIOR** or **ESTIMATE**.

## Structural extras (`pipeline/structural_extras.py`)

| Layer | Algorithm | Origin | IXI057 |
|---|---|---|---|
| `extras/sulci.nii.gz` | brain envelope = closing of the brain with a 6 mm ball + hole filling; sulci = envelope minus brain tissue, opened once | patient | 86 ml |
| `extras/skull_t1.nii.gz` | shell deeper than 2 mm under the skin, within 12 mm of the brain envelope, outside the envelope dilated by 1.5 mm; bone = voxels darker than the Otsu threshold of that shell; closing, opening, largest component | **estimate** (bone gives almost no MRI signal) | 581 ml, median thickness 4.2 mm |
| `extras/sss_prior.nii.gz` | gap between brain envelope and skull (< 10 mm from the brain), within 5 mm of the midline, above the top of the lateral ventricles; largest component | **prior** (anatomical rule: the superior sagittal sinus always runs there) | 9.6 ml |

**Why sulci matter:** sulci hide small surface vessels, so a path through a sulcus is riskier - they are a soft zone.

## Venous prior from the VENAT atlas (`pipeline/atlas_priors.py`)

Used only when there is no contrast T1.

1. Register the MNI152 template to the skull-stripped patient T1: rigid (versor, moments initialisation, MI 48 bins, 10 % sampling, 200 iterations) -> affine (300 iterations) -> **B-spline** (4 x 4 x 4 control grid ≈ 3 cm spacing, L-BFGS-B, 40 iterations).
2. Warp the VENAT probability map (Huck et al. 2019, 7T QSM of 20 subjects, 0.5 mm) into the patient.
3. "Likely vein" = probability > 0.15, components < 20 voxels removed -> `priors/veins_prior.nii.gz` (IXI057: 44.8 ml).

**Planner role:** `veins_prior` and `sagittal_sinus` are no-go zones, shown with `[PRIOR]` in the app. They tell where veins usually are, not where they are in this patient.

<!-- nav:bar -->
---
← [Veins, sinuses and CT](veins-sinuses-and-ct.md) | [↑ Brain layers and patient data](README.md) | [Eloquent cortex](eloquent-cortex.md) →
<!-- /nav:bar -->
