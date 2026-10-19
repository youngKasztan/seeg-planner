"""
layers.py - display-only layers of the app, with colours and origin.

Planning zones come from robot.toml; the layers below are for looking only (they do not change the plan).
Each layer is either a set of segmentation labels or a mask file in the patient folder.
"""
CORTEX = list(range(1000, 1036)) + list(range(2000, 2036)) + [3, 42]

# (key, group, source, colour RGB 0-1, origin)
# Only layers that are NOT already a planning zone in robot.toml: ventricles, brainstem, cerebellum, sulci,
# arteries, veins, sagittal sinus, eloquent cortex and the white-matter tracts are shown from their zone rows.
CATALOG = [
    ("gray_matter", "Anatomy", {"labels": CORTEX}, (0.78, 0.55, 0.55), "patient"),
    ("white_matter", "Anatomy", {"labels": [2, 41, 77, 251, 252, 253, 254, 255, 85]}, (0.92, 0.90, 0.84), "patient"),
    ("csf", "Anatomy", {"labels": [24]}, (0.47, 0.78, 1.0), "patient"),
    ("hippocampus", "Anatomy", {"labels": [17, 53]}, (1.0, 0.78, 0.16), "patient"),
    ("amygdala", "Anatomy", {"labels": [18, 54]}, (1.0, 0.43, 0.16), "patient"),
    ("thalamus", "Anatomy", {"labels": [10, 49]}, (0.47, 0.78, 0.47), "patient"),
    ("basal_ganglia", "Anatomy", {"labels": [11, 12, 13, 26, 50, 51, 52, 58]}, (0.67, 0.47, 0.86), "patient"),
    ("skull_t1", "Head", {"mask": ["extras/skull_t1.nii.gz"]}, (0.94, 0.92, 0.86), "ESTIMATE"),
    ("scalp", "Head", {"mask": ["head.nii.gz"]}, (0.90, 0.75, 0.67), "patient"),
]
GROUPS = ["Anatomy", "Head"]

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
