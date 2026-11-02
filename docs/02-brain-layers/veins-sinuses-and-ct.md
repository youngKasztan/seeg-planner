<!-- nav:crumb -->
[Docs home](../README.md) › [Brain layers and patient data](README.md) › **Veins, sinuses and CT**
<!-- /nav:crumb -->

# Veins, sinuses and CT

## Veins and sinuses from a contrast T1

> **In short:** TOF-MRA hides venous blood. After gadolinium all vessels light up, so subtracting the T1 before contrast leaves the vessels; removing what is already an artery leaves the veins.

`pipeline/veins_ct1.py` - code ready, phantom test only, **not validated** on a patient (no public data with pre/post contrast T1 + TOF).

1. rigid registration T1+Gd -> T1;
2. both normalised so that the white-matter median = 1; subtraction post - pre (negative values set to 0), limited to the brain + ~1 cm, scaled to the 99.5th percentile;
3. Frangi at two scales: 0.5 / 1 / 1.5 mm (cortical and bridging veins, kept above the 98th percentile and subtraction > 0.15) and 3 / 4 / 5 mm (sinuses, 99th percentile and > 0.25, the 6 largest components);
4. voxels of the 1 mm dilated artery mask removed;
5. `veins/veins.nii.gz`, `veins/sinuses.nii.gz`.

When available they replace the priors of [Sulci, skull and priors](sulci-skull-and-priors.md).

## CT layers

> **In short:** CT shows bone precisely, which is where the robot has to drill. A post-implant CT shows where the contacts really ended up.

`pipeline/ct_layers.py` - phantom test only:

| Option | Layer | Rule |
|---|---|---|
| always | bone | HU > 300, largest component, small holes closed; bone thickness map in mm |
| always | scalp | HU > -300, holes filled |
| `--cta` | arteries | contrast HU 150-600 inside the skull, outside bone, + Frangi |
| `--postimplant` | electrode contacts | metal HU > 2000 -> connected components -> centres in mm (JSON), to compare plan vs actual placement |

Registration CT -> T1 rigid, mutual information. More: [veins_and_ct.md](../veins_and_ct.md).

<!-- nav:bar -->
---
← [White-matter tracts from DTI](white-matter-tracts.md) | [↑ Brain layers and patient data](README.md) | [Sulci, skull and priors](sulci-skull-and-priors.md) →
<!-- /nav:bar -->
