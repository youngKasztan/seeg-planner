# Veins, sinuses and CT - how to add them properly

## Veins and dural sinuses

**Conclusion:** the only reliable source is an exam in which venous blood is bright - ideally a **3D T1 after gadolinium** (standard before SEEG in most centres). TOF-MRA deliberately suppresses venous blood, so our angiography cannot provide veins.

| Option | What it gives | Assessment |
|---|---|---|
| **T1 before + after gadolinium (subtraction)** | sinuses + cortical and bridging veins, ~1 mm | **chosen** - `pipeline/veins_ct1.py` |
| MR venography (PC-MRV) / CT venography | sinuses and large veins | good alternative, same code (input = vascular image) |
| SWI | small veins (dark) | good for veins, poor for sinuses; needs contrast inversion |
| Venous atlas registered to the patient | only the approximate position of large sinuses | **not for planning** - cortical veins are individual |
| Guessing from non-contrast T1 | nothing reliable | rejected |

**How `veins_ct1.py` works:**
1. registration T1+Gd -> T1,
2. intensity normalisation (white-matter median = 1) and subtraction: only enhancing structures remain,
3. vesselness filter at two scales: sinuses (6-10 mm diameter) and veins (1-3 mm),
4. removal of TOF arteries (arteries also enhance after gadolinium),
5. separate `veins` and `sinuses` layers, both critical (distance map).

**Status:** tested on a phantom (`tests/test_veins_phantom.py`: sinus detected 70%, vein 100%). No public patient with pre/post-contrast T1 + TOF - validation waits for data.

## CT

CT has four uses in SEEG - each is a separate layer or result:

| Use | Source | Output | Why |
|---|---|---|---|
| **Skull bone** | CT (HU > 300) | `skull.nii.gz` + bone thickness map | entry point, drilling angle, bone thickness along the trajectory |
| **Scalp** | CT (HU > -300) | `scalp.nii.gz` | more accurate than from MRI (no distortion) |
| **Arteries from CTA** | CTA (HU 150-600 inside the skull, outside bone) | `arteries_cta.nii.gz` | when there is no MR angiography |
| **Electrodes after implantation** | post-implant CT (HU > 2000) | `contacts.json` (contact positions in mm) | compare plan vs. actual placement, validate the planner |

In practice **registration to the robot / stereotactic frame** (e.g. Cirq, ROSA, Autoguide) is also done on CT, so the plan must be transferable to CT space. Everything here lives in T1 space and CT is rigidly registered to it (`ct_layers.py`), so the transform is known.

**Status:** tested on a phantom (`tests/test_ct_phantom.py`: 8/8 contacts, bone detected). Next step: a real SEEG patient with CT - the Brainstorm "Epileptogenicity" tutorial dataset (pre-op MRI + post-implant CT; free Brainstorm account required to download).
