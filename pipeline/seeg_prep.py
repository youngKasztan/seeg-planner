"""
seeg_prep.py - automatyczny pipeline: badania pacjenta -> pakiet warstw mozgu do planowania SEEG.

Uzycie:
    python seeg_prep.py --seg aparc+aseg.nii.gz --head Head.nii.gz --out pacjent_725751
    # opcjonalnie: --vessels naczynia_mask.nii.gz  (maska naczyn z MRA/CTA/T1+kontrast)

Docelowo krok --seg bedzie generowany automatycznie przez FastSurfer z surowego T1 (DICOM -> NIfTI).
Wszystkie wspolrzedne wyjsciowe sa w milimetrach przestrzeni skanera (RAS), wiec punkty
zaznaczone w okularach i obliczenia trajektorii dzialaja w tym samym ukladzie.

Wyjscie (folder --out):
    meshes/<warstwa>.glb      siatki 3D do Unity / Quest
    labels.nii.gz             pelna segmentacja (atlas Desikan-Killiany + struktury podkorowe)
    dist_<struktura>.nii.gz   mapy odleglosci [mm] do struktur krytycznych (do oceny bezpieczenstwa)
    manifest.json             lista warstw, kolory, nazwy obszarow, info o ukladzie wspolrzednych
"""
import argparse, json, os
import numpy as np
import nibabel as nib
from scipy import ndimage
from skimage import measure
import trimesh

# ---- definicje warstw (etykiety FreeSurfer aseg / aparc) ----
CORTEX = list(range(1000, 1036)) + list(range(2000, 2036)) + [3, 42]
LAYERS = {
    # nazwa: (etykiety, kolor RGBA, krytyczna_dla_trajektorii)
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
    verts = nib.affines.apply_affine(affine, verts)          # voksele -> mm RAS
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
    ap.add_argument("--seg", required=True, help="segmentacja aparc+aseg (NIfTI)")
    ap.add_argument("--head", help="maska glowy/skory (NIfTI)")
    ap.add_argument("--brainmask", help="maska mozgu (do przyblizenia CSF zewnatrzmozgowego)")
    ap.add_argument("--vessels", help="maska naczyn (NIfTI) - z MRA/CTA/T1+Gd")
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

    # CSF: 3. komora/CSF z aseg + przestrzen miedzy mozgiem a maska mozgu (bruzdy, przestrzen podpajeczynowkowa)
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
        # naczynia moga miec wlasna, drobniejsza siatke (np. MRA 0.47 mm) - zostawiamy natywna rozdzielczosc
        vimg = nib.load(a.vessels)
        masks["vessels"] = (np.asanyarray(vimg.dataobj) > 0, vimg.affine, vimg.header.get_zooms()[:3])
        LAYERS["vessels"] = ([], [220, 30, 30, 255], True)

    for name, (mask, m_aff, m_vox) in masks.items():
        mesh = mask_to_mesh(mask, m_aff, smooth_iter=5 if name in ("vessels",) else 15,
                            target_faces=150000 if name == "vessels" else 60000)
        if mesh is None:
            print(f"  [!] {name}: pusta maska, pomijam"); continue
        rgba = LAYERS[name][1]
        mesh.visual.face_colors = rgba
        path = os.path.join("meshes", f"{name}.glb")
        mesh.export(os.path.join(a.out, path))
        manifest["layers"].append({"name": name, "file": path, "rgba": rgba,
                                   "faces": int(len(mesh.faces)),
                                   "volume_ml": round(float(mask.sum() * np.prod(m_vox)) / 1000, 2)})
        print(f"  {name:14s} {len(mesh.faces):7d} trojkatow  {manifest['layers'][-1]['volume_ml']} ml")

        # mapa odleglosci [mm] dla struktur krytycznych
        if LAYERS[name][2]:
            d = ndimage.distance_transform_edt(~mask, sampling=m_vox).astype(np.float32)
            if m_aff is not aff:   # inna siatka -> przepróbkuj mape odleglosci na siatke segmentacji
                ijk = np.indices(seg.shape).reshape(3, -1).T
                src = nib.affines.apply_affine(np.linalg.inv(m_aff) @ aff, ijk).T
                d = ndimage.map_coordinates(d, src, order=1, mode="constant", cval=np.nan).reshape(seg.shape).astype(np.float32)
                manifest.setdefault("notes", []).append(f"{name}: mapa odleglosci NaN poza polem widzenia badania")
            fn = f"dist_{name}.nii.gz"
            nib.save(nib.Nifti1Image(d, aff), os.path.join(a.out, fn))
            manifest["critical"].append({"name": name, "distance_map": fn})

    if not a.vessels:
        manifest["warnings"] = ["BRAK MASKI NACZYN - trajektorie nie moga byc uznane za bezpieczne "
                                "bez MRA/CTA/T1 z kontrastem."]

    # regiony atlasu dostepne do wyboru celow "po nazwie" (srodek ciezkosci w mm)
    regions = {}
    for l in np.unique(seg):
        if l == 0: continue
        c = ndimage.center_of_mass(seg == l)
        regions[int(l)] = [round(float(x), 2) for x in nib.affines.apply_affine(aff, c)]
    manifest["region_centroids_mm"] = regions

    with open(os.path.join(a.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print("Gotowe ->", a.out)

if __name__ == "__main__":
    main()
