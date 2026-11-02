<!-- nav:crumb -->
[Docs home](../README.md) › [Brain layers and patient data](README.md) › **Running the pipeline**
<!-- /nav:crumb -->

# Running the pipeline

> **In short:** one command turns the raw exams of a patient into a folder with all masks the planner needs and the files for the headset. Steps that are already done are skipped, so a stopped run can be continued.

```
python pipeline/run_pipeline.py --t1 T1.nii.gz --mra MRA.nii.gz \
    --dti_dir DTI/ --bvals bvals.txt --bvecs bvecs.txt \
    [--t1_gd T1_gd.nii.gz] [--ct CT.nii.gz --ct_postimplant] \
    [--venat VENAT_PartialVolume.nii.gz] [--truth vessels_expert.nii.gz] \
    --out results/PATIENT --fastsurfer /path/to/FastSurfer [--device cpu|cuda]
```

## Exams

| Exam | Needed? | Gives |
|---|---|---|
| T1 (3D, ~1 mm) | **required** | segmentation, head, sulci, skull estimate, sinus prior, eloquent cortex |
| TOF-MRA | strongly recommended | arteries. Without it the package carries the warning "trajectories cannot be considered safe" |
| DTI (+ bvals, bvecs) | recommended | white-matter tracts |
| T1 after gadolinium | optional | patient veins and sinuses (replaces the priors) |
| CT / CTA / post-implant CT | optional | bone, scalp, CTA arteries, implanted contacts |
| VENAT atlas file | optional | veins prior when there is no contrast T1 |

## Steps and outputs

| Step | Script | Output (in `--out`) | Page |
|---|---|---|---|
| 1. segmentation | FastSurfer | `aparc.DKTatlas+aseg.deep.nii.gz`, `mask.nii.gz`, `orig.nii.gz` | [Segmentation and head](segmentation-and-head.md) |
| 2. head mask | `head_mask.py` | `head.nii.gz` | [Segmentation and head](segmentation-and-head.md) |
| 3. arteries | `vessels_mra.py` | `vessels_auto.nii.gz`, `vessels_report.json` | [Arteries](arteries.md) |
| 3b. tracts | `tracts_dti.py` | `tracts/*.nii.gz`, `*.trk`, `tracts_report.json` | [White-matter tracts](white-matter-tracts.md) |
| 3c. veins | `veins_ct1.py` | `veins/veins.nii.gz`, `veins/sinuses.nii.gz` | [Veins, sinuses and CT](veins-sinuses-and-ct.md) |
| 3d. CT | `ct_layers.py` | `ct/` | [Veins, sinuses and CT](veins-sinuses-and-ct.md) |
| 3e. extras | `structural_extras.py` | `extras/sulci.nii.gz`, `skull_t1.nii.gz`, `sss_prior.nii.gz` | [Sulci, skull and priors](sulci-skull-and-priors.md) |
| 3f. venous prior | `atlas_priors.py` | `priors/veins_prior.nii.gz` | [Sulci, skull and priors](sulci-skull-and-priors.md) |
| 4. package | `seeg_prep.py` | `package/`: meshes, distance maps, `manifest.json`, eloquent cortex | [Eloquent cortex](eloquent-cortex.md), [Headset package](headset-package-and-landmarks.md) |
| 5. preview | `tools/render_preview.py` | `preview.png` | - |
| 6. headset files | `tools/export_headset.py` | `headset/` | [Headset package](headset-package-and-landmarks.md) |

## Patient folder used by the planner

| File | Used for |
|---|---|
| `orig.nii.gz` | T1 shown on the slices; defines the planning grid |
| `aparc.DKTatlas+aseg.deep.nii.gz` | labels of no-go and soft zones, anatomical frame, midline |
| `mask.nii.gz` | brain mask (`outside_brain` zone) |
| `head.nii.gz` | skin: entry points, where the straight part of the robot leaves the head |
| `vessels_auto.nii.gz`, `tracts/`, `extras/`, `priors/` | zones named in `robot.toml` |
| `headset/headset_manifest.json` | landmarks (allowed entry zone), head centre (headset coordinates) |
| `targets.json`, `regions.json`, `regions/` | written by the app |

Times on IXI057 (CPU): segmentation ~10 min (1-2 min with a GPU), tractography ~3 min (~15 min with the automatic bvec check), venous prior ~3 min. Patient data is never committed (`.gitignore`).

<!-- nav:bar -->
---
← [Brain layers and patient data](README.md) | [↑ Brain layers and patient data](README.md) | [Segmentation and head mask](segmentation-and-head.md) →
<!-- /nav:bar -->
