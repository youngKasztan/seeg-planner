"""
layers.py - display layers of the app (the same layers as the headset model), with colours and origin.

Planning zones come from robot.toml; the layers below are for looking only (they do not change the plan).
Each layer is either a set of segmentation labels or a mask file in the patient folder.
"""
CORTEX = list(range(1000, 1036)) + list(range(2000, 2036)) + [3, 42]

# (key, group, source, colour RGB 0-1, origin)
CATALOG = [
    ("gray_matter", "Anatomy", {"labels": CORTEX}, (0.78, 0.55, 0.55), "patient"),
    ("white_matter", "Anatomy", {"labels": [2, 41, 77, 251, 252, 253, 254, 255, 85]}, (0.92, 0.90, 0.84), "patient"),
    ("ventricles", "Anatomy", {"labels": [4, 5, 14, 15, 43, 44, 72]}, (0.24, 0.55, 1.0), "patient"),
    ("csf", "Anatomy", {"labels": [24]}, (0.47, 0.78, 1.0), "patient"),
    ("hippocampus", "Anatomy", {"labels": [17, 53]}, (1.0, 0.78, 0.16), "patient"),
    ("amygdala", "Anatomy", {"labels": [18, 54]}, (1.0, 0.43, 0.16), "patient"),
    ("thalamus", "Anatomy", {"labels": [10, 49]}, (0.47, 0.78, 0.47), "patient"),
    ("basal_ganglia", "Anatomy", {"labels": [11, 12, 13, 26, 50, 51, 52, 58]}, (0.67, 0.47, 0.86), "patient"),
    ("brainstem", "Anatomy", {"labels": [16, 28, 60]}, (0.59, 0.59, 0.59), "patient"),
    ("cerebellum", "Anatomy", {"labels": [7, 8, 46, 47]}, (0.75, 0.67, 0.47), "patient"),
    ("sulci", "Anatomy", {"mask": ["extras/sulci.nii.gz"]}, (0.35, 0.67, 1.0), "patient"),
    ("eloquent_motor", "Eloquent cortex", {"labels": [1024, 2024]}, (1.0, 0.24, 0.24), "atlas function"),
    ("eloquent_sensory", "Eloquent cortex", {"labels": [1022, 2022]}, (1.0, 0.59, 0.24), "atlas function"),
    ("eloquent_visual", "Eloquent cortex", {"labels": [1021, 2021]}, (0.31, 0.78, 1.0), "atlas function"),
    ("eloquent_auditory", "Eloquent cortex", {"labels": [1034, 2034]}, (0.78, 0.47, 1.0), "atlas function"),
    ("eloquent_language", "Eloquent cortex", {"labels": [1018, 1020, 1030, 1031]}, (1.0, 0.90, 0.24), "atlas function"),
    ("cst_L", "White-matter tracts", {"mask": ["tracts/cst_L.nii.gz"]}, (1.0, 0.31, 0.31), "patient"),
    ("cst_R", "White-matter tracts", {"mask": ["tracts/cst_R.nii.gz"]}, (1.0, 0.31, 0.31), "patient"),
    ("arcuate_L", "White-matter tracts", {"mask": ["tracts/arcuate_L.nii.gz"]}, (1.0, 0.86, 0.24), "patient"),
    ("optic_rad_L", "White-matter tracts", {"mask": ["tracts/optic_rad_L.nii.gz"]}, (0.31, 0.78, 1.0), "patient"),
    ("optic_rad_R", "White-matter tracts", {"mask": ["tracts/optic_rad_R.nii.gz"]}, (0.31, 0.78, 1.0), "patient"),
    ("uncinate_L", "White-matter tracts", {"mask": ["tracts/uncinate_L.nii.gz"]}, (0.47, 1.0, 0.47), "patient"),
    ("uncinate_R", "White-matter tracts", {"mask": ["tracts/uncinate_R.nii.gz"]}, (0.47, 1.0, 0.47), "patient"),
    ("ifof_L", "White-matter tracts", {"mask": ["tracts/ifof_L.nii.gz"]}, (1.0, 0.47, 0.86), "patient"),
    ("ifof_R", "White-matter tracts", {"mask": ["tracts/ifof_R.nii.gz"]}, (1.0, 0.47, 0.86), "patient"),
    ("arteries", "Vessels", {"mask": ["vessels_auto.nii.gz"]}, (0.86, 0.12, 0.12), "patient"),
    ("veins_prior", "Vessels", {"mask": ["priors/veins_prior.nii.gz"]}, (0.24, 0.35, 1.0), "PRIOR"),
    ("sinus_sss_prior", "Vessels", {"mask": ["extras/sss_prior.nii.gz"]}, (0.12, 0.16, 0.78), "PRIOR"),
    ("skull_t1", "Head", {"mask": ["extras/skull_t1.nii.gz"]}, (0.94, 0.92, 0.86), "ESTIMATE"),
    ("scalp", "Head", {"mask": ["head.nii.gz"]}, (0.90, 0.75, 0.67), "patient"),
]
GROUPS = ["Anatomy", "Eloquent cortex", "White-matter tracts", "Vessels", "Head"]

# colours for the planning zones in robot.toml, matched by name
ZONE_COLOURS = [("arter", (0.86, 0.12, 0.12)), ("vein", (0.24, 0.35, 1.0)), ("sinus", (0.12, 0.16, 0.78)),
                ("ventric", (0.24, 0.55, 1.0)), ("choroid", (0.75, 0.2, 0.55)), ("midline", (0.85, 0.85, 0.3)),
                ("hypothal", (0.55, 0.85, 0.35)), ("nuclei", (0.67, 0.47, 0.86)), ("brainstem", (0.59, 0.59, 0.59)), ("cerebell", (0.75, 0.67, 0.47)),
                ("outside", (0.35, 0.35, 0.35)), ("sulci", (0.35, 0.67, 1.0)), ("eloquent", (1.0, 0.75, 0.2)),
                ("cortico", (1.0, 0.31, 0.31)), ("optic", (0.31, 0.78, 1.0)), ("tract", (1.0, 0.47, 0.86))]

def zone_colour(name, default=(1.0, 0.3, 0.3)):
    for key, col in ZONE_COLOURS:
        if key in name: return col
    return default
