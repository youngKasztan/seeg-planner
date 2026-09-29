"""
ct_layers.py - CT-derived layers for SEEG planning.

Why CT matters in SEEG:
  * skull bone     -> entry point, drilling angle, bone thickness along the trajectory
  * scalp          -> more accurate than from MRI (no geometric distortion)
  * CTA (optional) -> arteries when there is no MR angiography
  * post-implant CT (optional) -> electrode/contact positions: plan vs. actual placement
  * registration to the robot / stereotactic frame is usually done on CT

Steps:
 1. rigid registration CT -> T1 (mutual information, same function as for MRA/DTI)
 2. bone: HU > 300, largest component, small holes closed; bone thickness map [mm]
 3. scalp: HU > -300, holes filled
 4. --cta: arteries = contrast (HU 150-600) inside the skull, outside bone (+ Frangi filter)
 5. --postimplant: metal (HU > 2000) -> components = contacts/electrodes, centres in mm (JSON)
All masks are saved on the CT grid with an affine converted to T1 space
(seeg_prep.py accepts them through --layer).

Usage:
  python ct_layers.py --ct CT.nii.gz --t1 orig.nii.gz --out ct/ [--cta] [--postimplant]
"""
import argparse, json, os
import numpy as np, nibabel as nib
from scipy import ndimage
from vessels_mra import register, LPS

def affine_to_t1(tx, aff):
    inv = tx.GetInverse()
    pts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], float)
    world = nib.affines.apply_affine(LPS @ aff, pts)
    m = np.array([inv.TransformPoint(tuple(map(float, w))) for w in world])
    out = np.eye(4); out[:3, 3] = m[0]; out[:3, :3] = (m[1:] - m[0]).T
    return LPS @ out

def largest(mask):
    lab, n = ndimage.label(mask)
    if n == 0: return mask
    return lab == (np.argmax(np.bincount(lab.ravel())[1:]) + 1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ct", required=True); ap.add_argument("--t1", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--cta", action="store_true"); ap.add_argument("--postimplant", action="store_true")
    ap.add_argument("--no_register", action="store_true", help="CT is already in T1 space")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    ct_img = nib.load(a.ct); hu = np.asanyarray(ct_img.dataobj).astype(np.float32)
    vox = ct_img.header.get_zooms()[:3]; rep = {}

    if a.no_register:
        aff = ct_img.affine
    else:
        print("1/5 registering CT -> T1 ...")
        # clip HU to the soft-tissue range so mutual information is not dominated by bone
        soft = nib.Nifti1Image(np.clip(hu, -100, 200), ct_img.affine)
        tx, metric = register(nib.load(a.t1), soft)
        aff = affine_to_t1(tx, ct_img.affine)
        p = np.array(tx.GetParameters())
        rep["registration"] = {"rotation_deg": np.degrees(p[:3]).round(2).tolist(), "translation_mm": p[3:].round(2).tolist()}

    save = lambda m, n: nib.save(nib.Nifti1Image(m.astype(np.uint8), aff), os.path.join(a.out, n))

    print("2/5 bone ...")
    bone = largest(hu > 300)
    bone = ndimage.binary_closing(bone, iterations=1)
    save(bone, "skull.nii.gz")
    thick = 2 * ndimage.distance_transform_edt(bone, sampling=vox)      # approximate local thickness [mm]
    nib.save(nib.Nifti1Image(thick.astype(np.float32), aff), os.path.join(a.out, "skull_thickness_mm.nii.gz"))
    rep["skull_volume_ml"] = round(float(bone.sum() * np.prod(vox)) / 1000, 1)
    rep["skull_thickness_mm_p50_p95"] = [round(float(np.percentile(thick[bone], q)), 1) for q in (50, 95)] if bone.any() else None

    print("3/5 scalp ...")
    head = largest(hu > -300)
    head = np.stack([ndimage.binary_fill_holes(s) for s in head], -1) if head.ndim == 3 else head
    save(head, "scalp.nii.gz")

    # intracranial space = filled skull without bone
    inside = np.stack([ndimage.binary_fill_holes(s) for s in np.moveaxis(bone, -1, 0)], -1) & ~bone
    inside = ndimage.binary_erosion(inside, iterations=1)

    if a.cta:
        print("4/5 arteries from CTA ...")
        from skimage.filters import frangi
        c = (hu > 150) & (hu < 600) & inside & ~ndimage.binary_dilation(bone, iterations=2)
        img = np.clip((hu - 100) / 400, 0, 1) * inside
        v = frangi(img, sigmas=[1, 1.5, 2, 3], black_ridges=False)
        ves = c & (v > np.percentile(v[inside], 97))
        lab, n = ndimage.label(ves); sz = ndimage.sum(ves, lab, range(1, n + 1))
        ves = np.isin(lab, 1 + np.where(sz >= 30)[0])
        save(ves, "arteries_cta.nii.gz"); rep["cta_vessel_ml"] = round(float(ves.sum() * np.prod(vox)) / 1000, 2)

    if a.postimplant:
        print("5/5 electrodes from post-implant CT ...")
        metal = (hu > 2000) & ndimage.binary_dilation(inside, iterations=3)
        lab, n = ndimage.label(metal)
        cents = ndimage.center_of_mass(metal, lab, range(1, n + 1))
        sizes = ndimage.sum(metal, lab, range(1, n + 1))
        contacts = [{"xyz_mm": [round(float(x), 2) for x in nib.affines.apply_affine(aff, c)], "voxels": int(s)}
                    for c, s in zip(cents, sizes) if s >= 3]
        save(metal, "metal.nii.gz")
        json.dump(contacts, open(os.path.join(a.out, "contacts.json"), "w"), indent=1)
        rep["metal_components"] = len(contacts)

    json.dump(rep, open(os.path.join(a.out, "ct_report.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))

if __name__ == "__main__":
    main()
