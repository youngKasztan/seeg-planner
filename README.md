# SEEG Planner

Planning SEEG electrode trajectories on a patient-specific brain model displayed in Meta Quest 3.

**Status:** research prototype. Not for clinical use (would require medical-device certification, EU MDR).

## What the pipeline does

Raw patient exams -> segmentation -> layer extraction -> 3D package ready for planning.

```
python pipeline/run_pipeline.py --t1 T1.nii.gz --mra MRA.nii.gz \
    --dti_dir DTI/ --bvals bvals.txt --bvecs bvecs.txt \
    [--t1_gd T1_gd.nii.gz] [--ct CT.nii.gz --ct_postimplant] \
    --out results/PATIENT --fastsurfer /path/to/FastSurfer
```

| Step | Script | Input | Output |
|---|---|---|---|
| 1. Brain segmentation | FastSurfer (called from `run_pipeline.py`) | T1 | 95 atlas regions, brain mask |
| 2. Head mask | `pipeline/head_mask.py` | T1 | scalp |
| 3. Arteries | `pipeline/vessels_mra.py` | TOF-MRA + T1 | artery mask (MRA->T1 registration, Frangi filter) |
| 3b. White-matter tracts | `pipeline/tracts_dti.py` | DTI + T1 | corticospinal L/R, arcuate L, optic radiation L/R (DIPY) |
| 3c. Veins and sinuses | `pipeline/veins_ct1.py` | T1 before + after gadolinium | veins, sinuses (subtraction + 2-scale Frangi) - *not validated* |
| 3d. CT | `pipeline/ct_layers.py` | CT / CTA / post-implant CT | bone + thickness, scalp, CTA arteries, electrode contacts |
| Eloquent cortex | `pipeline/seeg_prep.py` | segmentation (DKT atlas) | motor, sensory, visual, auditory, language (language: left dominance assumed) |
| 4. Layer package | `pipeline/seeg_prep.py` | masks | `.glb` meshes, distance maps, `manifest.json` |
| 5. Preview | `tools/render_preview.py` | package | PNG with 6 views |
| Vessel check | `tools/render_vessel_check.py` | MRA + automatic + expert masks | MIP overlay + Dice |

## Results on test subject IXI057

- Segmentation: ~10 min on CPU (1-2 min with a GPU)
- Arteries vs expert manual segmentation: **Dice 0.78** (sensitivity 0.77, precision 0.80)
- White-matter tracts (DTI, 16 directions, 1.75x1.75x2 mm): CST L 7.8 ml / R 6.6 ml, arcuate L 5.5 ml, optic radiation L 12.1 ml / R 8.3 ml
  - bvec sign convention chosen automatically (mean streamline length 48 mm vs ~25 mm for the wrong variants)
  - IXI: 17 volumes but the gradient table has 16 - tensor fit showed it matches volumes 0-15 (residual 0.051 vs 0.092)
- Tractography ~3 min on CPU (~15 min including automatic bvec convention check)

![3D model](docs/IXI057_preview.png)
![Arteries vs experts](docs/IXI057_vessels_vs_experts.png)

## Missing / not validated

- Veins and sinuses: code ready (phantom test), no public patient with pre/post-contrast T1 -> [docs/veins_and_ct.md](docs/veins_and_ct.md)
- CT: code ready (phantom test), next step: SEEG patient with CT (Brainstorm Epileptogenicity dataset)
- Eloquent cortex from fMRI instead of the atlas
- White-matter tracts not yet compared with expert tractography

## Tests

```
python tests/test_ct_phantom.py
python tests/test_veins_phantom.py
```

## Test data

- IXI: https://brain-development.org/ixi-dataset/
- Expert vessel segmentations for IXI: https://zenodo.org/records/17393202
- FastSurfer weights: https://zenodo.org/records/10390573

Patient data is never stored in the repository (`.gitignore`).
