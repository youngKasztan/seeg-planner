<!-- nav:crumb -->
[Docs home](../README.md) › [Brain layers and patient data](README.md) › **Eloquent cortex**
<!-- /nav:crumb -->

# Eloquent cortex

> **In short:** cortex areas whose damage causes a deficit (movement, feeling, sight, hearing, speech). Without fMRI they are taken from the atlas regions of the segmentation, so they are marked **[atlas function]**.

`pipeline/seeg_prep.py`, from DKT labels:

| Function | Regions | Labels |
|---|---|---|
| motor | precentral gyrus | 1024, 2024 |
| sensory | postcentral gyrus | 1022, 2022 |
| visual | pericalcarine cortex (V1) | 1021, 2021 |
| auditory | transverse temporal gyrus (Heschl) | 1034, 2034 |
| language (left dominance assumed, ~95 % of right-handers; must be confirmed clinically) | pars opercularis + triangularis (Broca, 1018, 1020), posterior half of the superior temporal gyrus (Wernicke, 1030), supramarginal gyrus (1031) | left only |

The package also stores `dist_eloquent.nii.gz` (distance map to all eloquent areas).

**Planner role:** soft zone `eloquent_cortex` (weight 2, scale 3 mm): allowed but expensive. The labels in `robot.toml` include the whole superior temporal gyrus (1030). Open question: make it a no-go zone except the gyrus of the target ([Limitations](../08-project/limitations-and-roadmap.md)).

<!-- nav:bar -->
---
← [Sulci, skull and priors](sulci-skull-and-priors.md) | [↑ Brain layers and patient data](README.md) | [Layer catalogue](layer-catalogue.md) →
<!-- /nav:bar -->
