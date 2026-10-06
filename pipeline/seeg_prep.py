"""
seeg_prep.py - build the patient brain package for SEEG planning from segmented layers.

Usage:
    python seeg_prep.py --seg aparc.DKTatlas+aseg.deep.nii.gz --head head.nii.gz \
        --brainmask mask.nii.gz --vessels vessels_auto.nii.gz \
        --layer cst_L:tracts/cst_L.nii.gz:critical --out package/

The --seg input comes from FastSurfer run on the raw T1 (see run_pipeline.py).
All output coordinates are in millimetres in scanner space (RAS), so points picked in the
headset and computed trajectories use the same coordinate system.

Output (folder --out):
    meshes/<layer>.glb        3D meshes for Unity / Quest
    labels.nii.gz             full segmentation (DKT atlas + subcortical structures)
    dist_<structure>.nii.gz   distance maps [mm] to critical structures (for safety scoring)
    manifest.json             layer list, colours, region centroids, coordinate-space info
"""
import argparse, json, os
import numpy as np
import nibabel as nib
from scipy import ndimage
from skimage import measure
import trimesh

# ---- layer definitions (FreeSurfer aseg / aparc labels) ----
CORTEX = list(range(1000, 1036)) + list(range(2000, 2036)) + [3, 42]
LAYERS = {
    # name: (labels, RGBA colour, critical for trajectories)
    "white_matter":  ([2, 41, 77, 251, 252, 253, 254, 255, 85], [235, 230, 215, 255], False),
    "gray_matter":   (CORTEX,                                    [200, 140, 140, 110], False),
    "ventricles":    ([4, 5, 14, 15, 43, 44, 72],                [60, 140, 255, 220], True),
    "hippocampus":   ([17, 53],                                  [255, 200, 40, 255], False),
    "amygdala":      ([18, 54],                                  [255, 110, 40, 255], False),
    "thalamus":      ([10, 49],                                  [120, 200, 120, 255], False),
    "basal_ganglia": ([11, 12, 13, 26, 50, 51, 52, 58],          [170, 120, 220, 255], False),
    "brainstem":     ([16, 28, 60],                              [150, 150, 150, 255], True),
    "cerebellum":    ([7, 8, 46, 47],                            [190, 170, 120, 255], False),
}
CSF_LABELS = [24]

def mask_to_mesh(mask, affine, smooth_iter=15, target_faces=60000):
    if mask.sum() < 50:
        return None
    m = ndimage.binary_closing(mask, iterations=1)
    m = ndimage.gaussian_filter(m.astype(np.float32), 0.8)
    m = np.pad(m, 1)
    verts, faces, _, _ = measure.marching_cubes(m, 0.5)
    verts -= 1
    verts = nib.affines.apply_affine(affine, verts)          # voxels -> mm RAS
    mesh = trimesh.Trimesh(verts, faces, process=True)
    trimesh.smoothing.filter_taubin(mesh, iterations=smooth_iter)
    if len(mesh.faces) > target_faces:
        try:
            mesh = mesh.simplify_quadric_decimation(face_count=target_faces)
        except Exception:
            pass
    return mesh

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seg", required=True, help="aparc+aseg segmentation (NIfTI)")
    ap.add_argument("--head", help="head/scalp mask (NIfTI)")
    ap.add_argument("--brainmask", help="brain mask (used to approximate extra-cerebral CSF)")
    ap.add_argument("--vessels", help="vessel mask (NIfTI) - from MRA/CTA/contrast T1")
    ap.add_argument("--layer", action="append", default=[],
                    help="extra layer on its own grid: name:file.nii.gz[:critical][:R,G,B] "
                         "e.g. cst_L:tracts/cst_L.nii.gz:critical:255,80,80")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    os.makedirs(os.path.join(a.out, "meshes"), exist_ok=True)
    seg_img = nib.load(a.seg)
    seg = np.asanyarray(seg_img.dataobj).astype(np.int32)
    aff = seg_img.affine
    vox = seg_img.header.get_zooms()[:3]
    nib.save(nib.Nifti1Image(seg, aff), os.path.join(a.out, "labels.nii.gz"))

    manifest = {"space": "scanner RAS, mm", "voxel_mm": [float(v) for v in vox],
                "layers": [], "critical": []}
    masks = {k: (np.isin(seg, v[0]), aff, vox) for k, v in LAYERS.items()}

    # ELOQUENT CORTEX (atlas-based from DKT labels; to be replaced/complemented by fMRI)
    # Language: left-hemisphere dominance assumed (~95% of right-handers) - must be confirmed clinically.
    ELO = {
        "eloquent_motor":    ([1024, 2024], [255, 60, 60, 200]),    # precentral gyrus
        "eloquent_sensory":  ([1022, 2022], [255, 150, 60, 200]),   # postcentral gyrus
        "eloquent_visual":   ([1021, 2021], [80, 200, 255, 200]),   # pericalcarine cortex (V1)
        "eloquent_auditory": ([1034, 2034], [200, 120, 255, 200]),  # transverse temporal gyrus (Heschl)
    }
    for k, (labs, rgba) in ELO.items():
        masks[k] = (np.isin(seg, labs), aff, vox); LAYERS[k] = (labs, rgba, False)
    broca = np.isin(seg, [1018, 1020])                                  # pars opercularis + triangularis (L)
    stg = seg == 1030                                                   # superior temporal gyrus (L)
    if stg.any():                                                       # posterior half of STG ~ Wernicke area
        ys = nib.affines.apply_affine(aff, np.argwhere(stg))[:, 1]
        post = np.zeros_like(stg); idx = np.argwhere(stg)[ys < np.median(ys)]
        post[tuple(idx.T)] = True; stg = post
    lang = broca | stg | (seg == 1031)                                  # + supramarginal gyrus (L)
    masks["eloquent_language"] = (lang, aff, vox); LAYERS["eloquent_language"] = ([], [255, 230, 60, 200], False)
    elo_all = lang.copy()
    for k in ELO: elo_all |= masks[k][0]

    # CSF: CSF label from aseg + space between brain and brain mask (sulci, subarachnoid space)
    csf = np.isin(seg, CSF_LABELS)
    if a.brainmask:
        bm = np.asanyarray(nib.load(a.brainmask).dataobj) > 0
        csf |= bm & (seg == 0)
    masks["csf"] = (csf, aff, vox)
    LAYERS["csf"] = (CSF_LABELS, [120, 200, 255, 70], True)

    if a.head:
        head = np.asanyarray(nib.load(a.head).dataobj) > 0
        head = ndimage.binary_fill_holes(head)
        masks["scalp"] = (head, aff, vox)
        LAYERS["scalp"] = ([], [230, 190, 170, 60], False)

    if a.vessels:
        # vessels may have their own, finer grid (e.g. MRA 0.47 mm) - keep native resolution
        vimg = nib.load(a.vessels)
        masks["vessels"] = (np.asanyarray(vimg.dataobj) > 0, vimg.affine, vimg.header.get_zooms()[:3])
        LAYERS["vessels"] = ([], [220, 30, 30, 255], True)

    DEFAULT_COL = {"cst": [255, 80, 80], "arcuate": [255, 220, 60], "optic": [80, 200, 255],
                   "uncinate": [120, 255, 120], "ifof": [255, 120, 220], "sulci": [90, 170, 255],
                   "vein": [60, 90, 255], "sinus": [30, 40, 200], "skull": [240, 235, 220], "scalp": [230, 190, 170]}
    for spec in a.layer:
        parts = spec.split(":"); name, path = parts[0], parts[1]
        crit = "critical" in parts[2:]
        rgb = next((list(map(int, p.split(","))) for p in parts[2:] if "," in p),
                   next((c for k, c in DEFAULT_COL.items() if k in name), [200, 200, 200]))
        im = nib.load(path)
        masks[name] = (np.asanyarray(im.dataobj) > 0, im.affine, im.header.get_zooms()[:3])
        LAYERS[name] = ([], rgb + [255], crit)

    for name, (mask, m_aff, m_vox) in masks.items():
        mesh = mask_to_mesh(mask, m_aff, smooth_iter=5 if name in ("vessels", "veins") else 15,
                            target_faces=150000 if name == "vessels" else 60000)
        if mesh is None:
            print(f"  [!] {name}: empty mask, skipping"); continue
        rgba = LAYERS[name][1]
        mesh.visual.face_colors = rgba
        path = os.path.join("meshes", f"{name}.glb")
        mesh.export(os.path.join(a.out, path))
        manifest["layers"].append({"name": name, "file": path, "rgba": rgba,
                                   "faces": int(len(mesh.faces)),
                                   "volume_ml": round(float(mask.sum() * np.prod(m_vox)) / 1000, 2)})
        print(f"  {name:18s} {len(mesh.faces):7d} faces  {manifest['layers'][-1]['volume_ml']} ml")

        # distance map [mm] for critical structures
        if LAYERS[name][2]:
            d = ndimage.distance_transform_edt(~mask, sampling=m_vox).astype(np.float32)
            if m_aff is not aff:   # different grid -> resample the distance map onto the segmentation grid
                ijk = np.indices(seg.shape).reshape(3, -1).T
                src = nib.affines.apply_affine(np.linalg.inv(m_aff) @ aff, ijk).T
                d = ndimage.map_coordinates(d, src, order=1, mode="constant", cval=np.nan).reshape(seg.shape).astype(np.float32)
                manifest.setdefault("notes", []).append(f"{name}: distance map is NaN outside the exam's field of view")
            fn = f"dist_{name}.nii.gz"
            nib.save(nib.Nifti1Image(d, aff), os.path.join(a.out, fn))
            manifest["critical"].append({"name": name, "distance_map": fn})

    d = ndimage.distance_transform_edt(~elo_all, sampling=vox).astype(np.float32)
    nib.save(nib.Nifti1Image(d, aff), os.path.join(a.out, "dist_eloquent.nii.gz"))
    manifest["critical"].append({"name": "eloquent", "distance_map": "dist_eloquent.nii.gz",
                                 "note": "atlas-based (DKT); language assumed left-dominant"})

    if not a.vessels:
        manifest["warnings"] = ["NO VESSEL MASK - trajectories cannot be considered safe "
                                "without MRA/CTA/contrast T1."]

    # atlas regions available for picking targets "by name" (centre of mass in mm)
    regions = {}
    for l in np.unique(seg):
        if l == 0: continue
        c = ndimage.center_of_mass(seg == l)
        regions[int(l)] = [round(float(x), 2) for x in nib.affines.apply_affine(aff, c)]
    manifest["region_centroids_mm"] = regions

    with open(os.path.join(a.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print("Done ->", a.out)

if __name__ == "__main__":
    main()
