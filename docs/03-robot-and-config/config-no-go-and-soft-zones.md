<!-- nav:crumb -->
[Docs home](../README.md) › [Robot and configuration](README.md) › **No-go and soft zones**
<!-- /nav:crumb -->

# No-go and soft zones

> **In short:** a **no-go zone** must never be touched; the robot surface keeps at least `margin_mm` from it. A **soft zone** may be crossed, but every millimetre near it costs extra, so the planner avoids it when that is cheap.

## How a zone is defined

```toml
[no_go.arteries]                 # [no_go.<name>] = hard, [avoid.<name>] = soft
mask = ["vessels_auto.nii.gz"]   # mask file(s) in the patient folder
margin_mm = 2.0
ignore_near_targets = false
```

| Key | Zone type | Meaning |
|---|---|---|
| `labels = [...]` | both | segmentation labels (FreeSurfer aseg / DKT) |
| `mask = ["file", ...]` | both | binary NIfTI files in the patient folder; a missing file skips the zone with a warning |
| `computed = "midline"` | both | the surface between the hemispheres, computed from the segmentation |
| `outside_of = "mask.nii.gz"` | no-go | everything outside this mask (`outside_brain`) |
| `margin_mm` | no-go | required gap between the robot surface and the zone (the robot radius is added automatically) |
| `ignore_near_targets` | no-go | `true` = not checked within `target_tolerance_mm` (3 mm) of a target, so targets next to the zone stay reachable |
| `weight`, `scale_mm` | soft | cost per mm of path $`= w\,e^{-d/s}`$, $`d`$ = distance to the zone |

A new table automatically appears in the app's layer list, in the planning and in the headset export. Its colour is chosen from its name (`path_planner/layers.py`: names containing `arter` red, `vein` blue, `ventric` light blue, ...).

## No-go zones

| Zone | Labels / file | Margin (mm) | Ignored near targets | Why |
|---|---|---|---|---|
| `arteries` | `vessels_auto.nii.gz` | 2.0 | no | bleeding |
| `ventricles` | 4, 5, 14, 15, 43, 44, 72 | 1.5 | **yes** | CSF leak, path deviation; targets often lie on the ventricle wall |
| `choroid_plexus` | 31, 63 | 1.0 | no | vascular tissue inside the ventricles |
| `midline` | `computed = "midline"` | 1.0 | no | falx and sinus: a path never crosses to the other hemisphere |
| `hypothalamus_optic_chiasm` | 28, 60, 85 | 2.0 | no | endocrine / vision |
| `brainstem` | 16 | 3.0 | no | vital functions |
| `cerebellum` | 7, 8, 46, 47 | 1.0 | no | not a supratentorial SEEG route |
| `sagittal_sinus` | `extras/sss_prior.nii.gz` | 3.0 | no | large vein (PRIOR) |
| `veins_prior` | `priors/veins_prior.nii.gz` | 1.0 | no | veins (PRIOR, no venography) |
| `corticospinal_tract` | `tracts/cst_L.nii.gz`, `tracts/cst_R.nii.gz` | 1.0 | no | motor pathway |
| `optic_radiation` | `tracts/optic_rad_L.nii.gz`, `tracts/optic_rad_R.nii.gz` | 1.0 | no | visual field |
| `outside_brain` | `outside_of = "mask.nii.gz"` | 1.0 | yes | after the straight entry the robot must stay inside the brain |

## Soft zones

| Zone | Labels / file | `weight` | `scale_mm` | Why |
|---|---|---|---|---|
| `deep_grey_nuclei` | 10, 11, 12, 13, 26, 49, 50, 51, 52, 58 | 1.0 | 2.0 | thalamus, basal ganglia: may be targets, so not forbidden |
| `sulci` | `extras/sulci.nii.gz` | 1.0 | 1.5 | hidden surface vessels |
| `eloquent_cortex` | 1024, 2024, 1022, 2022, 1021, 2021, 1034, 2034, 1018, 1020, 1030, 1031 | 2.0 | 3.0 | motor, sensory, visual, auditory, language |
| `other_tracts` | arcuate L, uncinate L/R, IFOF L/R | 0.5 | 3.0 | language and memory pathways |

Cost per mm of path for these values:

| Zone | inside | at 1 mm | at 3 mm | at 6 mm |
|---|---|---|---|---|
| deep grey nuclei | 1.00 | 0.61 | 0.22 | 0.05 |
| sulci | 1.00 | 0.51 | 0.14 | 0.02 |
| eloquent cortex | 2.00 | 1.43 | 0.74 | 0.27 |
| other tracts | 0.50 | 0.36 | 0.18 | 0.07 |

Path length itself costs 1 per mm, so 10 mm through eloquent cortex costs as much as 20 mm of extra path.

How margins become safety maps: [Safety maps](../05-path-planning/safety-maps.md).

<!-- nav:bar -->
---
← [Allowed entry zone](config-entry-zone.md) | [↑ Robot and configuration](README.md) | [Planner app (desktop)](../04-planner-app/README.md) →
<!-- /nav:bar -->
