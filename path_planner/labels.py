"""labels.py - names of FreeSurfer aseg + DKT atlas labels (shown next to each target)."""
ASEG = {2: "L cerebral white matter", 4: "L lateral ventricle", 5: "L inferior lateral ventricle", 7: "L cerebellum WM",
        8: "L cerebellum cortex", 10: "L thalamus", 11: "L caudate", 12: "L putamen", 13: "L pallidum",
        14: "3rd ventricle", 15: "4th ventricle", 16: "brainstem", 17: "L hippocampus", 18: "L amygdala",
        24: "CSF", 26: "L accumbens", 28: "L ventral DC", 31: "L choroid plexus", 41: "R cerebral white matter",
        43: "R lateral ventricle", 44: "R inferior lateral ventricle", 46: "R cerebellum WM", 47: "R cerebellum cortex",
        49: "R thalamus", 50: "R caudate", 51: "R putamen", 52: "R pallidum", 53: "R hippocampus", 54: "R amygdala",
        58: "R accumbens", 60: "R ventral DC", 63: "R choroid plexus", 77: "WM hypointensities"}
DKT = {2: "caudal anterior cingulate", 3: "caudal middle frontal", 5: "cuneus", 6: "entorhinal", 7: "fusiform",
       8: "inferior parietal", 9: "inferior temporal", 10: "isthmus cingulate", 11: "lateral occipital",
       12: "lateral orbitofrontal", 13: "lingual", 14: "medial orbitofrontal", 15: "middle temporal",
       16: "parahippocampal", 17: "paracentral", 18: "pars opercularis", 19: "pars orbitalis", 20: "pars triangularis",
       21: "pericalcarine", 22: "postcentral", 23: "posterior cingulate", 24: "precentral", 25: "precuneus",
       26: "rostral anterior cingulate", 27: "rostral middle frontal", 28: "superior frontal", 29: "superior parietal",
       30: "superior temporal", 31: "supramarginal", 34: "transverse temporal", 35: "insula"}

def name(label):
    label = int(label)
    if label in ASEG: return ASEG[label]
    if 1000 <= label < 1100 and label - 1000 in DKT: return "L " + DKT[label - 1000]
    if 2000 <= label < 2100 and label - 2000 in DKT: return "R " + DKT[label - 2000]
    return "outside brain" if label == 0 else f"label {label}"
