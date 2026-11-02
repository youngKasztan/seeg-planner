<!-- nav:crumb -->
[Docs home](../README.md) › [Brain layers and patient data](README.md) › **White-matter tracts from DTI**
<!-- /nav:crumb -->

# White-matter tracts from DTI

> **In short:** DTI measures in which direction water diffuses; in nerve bundles it moves along the fibres. Following that direction from one brain region to another traces the bundle. The motor tract and the visual pathway become no-go zones; other language/memory tracts are soft zones.

`pipeline/tracts_dti.py` (DIPY, pure Python, no MRtrix)

## Steps

1. Stack the DTI volumes, read bvals/bvecs. IXI has 17 volumes but 16 gradient rows; the tensor fit residual shows they match volumes 0-15 (0.051 vs 0.092).
2. Rigid registration mean b0 -> T1 (same function as for the MRA); segmentation moved onto the DTI grid.
3. **bvec sign convention chosen automatically**: quick tracking from 1500 random white-matter seeds for each sign variant; the variant with the longest mean streamline wins (IXI057: 48 mm vs ~25 mm for wrong variants).
4. Tensor model, fractional anisotropy (FA), one main direction per voxel (relative peak threshold 0.5, min. separation 25°).
5. Deterministic tracking (`LocalTracking`): step 0.5 mm, stop when FA < 0.15, 2 seeds per voxel, seeds in white matter next to both end regions (ROI dilated by 2 voxels, FA > 0.15). Seeding from both ends of each tract.
6. A streamline is kept if it has at least 20 points, one end in ROI A and the other in ROI B (both dilated by 3 voxels), and never enters the exclusion labels.
7. Density map; mask = density >= max(3, 5 % of the maximum); closing; largest component. `.trk` files are saved for viewing.

## Tracts

| Tract | ROI A | ROI B | Planner role | IXI057 |
|---|---|---|---|---|
| corticospinal `cst_L` / `cst_R` | precentral gyrus | brainstem | **no-go**, margin 1 mm | 7.8 / 6.6 ml |
| optic radiation `optic_rad_L` / `_R` (incl. Meyer's loop) | thalamus (LGN) | pericalcarine, lateral occipital, lingual | **no-go**, margin 1 mm | 12.1 / 8.3 ml |
| arcuate `arcuate_L` | pars opercularis + triangularis | superior/middle temporal, supramarginal | soft | 5.5 ml |
| uncinate `uncinate_L` / `_R` | orbitofrontal | anterior 35 % of temporal labels | soft | 7.4 / 5.7 ml |
| IFOF `ifof_L` / `_R` | orbitofrontal + pars triangularis | occipital | soft | 9.6 / 8.1 ml |

Exclusion labels: the other hemisphere and the cerebellum for all; additional regions per tract (e.g. occipital labels for the arcuate) to stop wrong bundles.

**Limitations:** 16 directions, 1.75 x 1.75 x 2 mm; deterministic tensor tracking cannot resolve crossing fibres; not yet compared with expert tractography.

<!-- nav:bar -->
---
← [Arteries from TOF-MRA](arteries.md) | [↑ Brain layers and patient data](README.md) | [Veins, sinuses and CT](veins-sinuses-and-ct.md) →
<!-- /nav:bar -->
