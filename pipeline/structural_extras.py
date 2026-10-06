"""
structural_extras.py - extra patient-derived layers from the T1 segmentation alone.

  sulci.nii.gz         sulcal CSF: space inside the brain's outer envelope that is not brain tissue.
                       Sulci hide small vessels, so SEEG entries through a sulcus are riskier.
  sss_prior.nii.gz     superior sagittal sinus PRIOR from anatomical rules: the sinus always runs along the
                       midline, in the gap between the brain envelope and the skull, above the corpus callosum.
                       Used when there is no contrast T1 / venography (VENAT covers intraparenchymal veins only).
  skull_t1.nii.gz      skull ESTIMATE from T1 when no CT exists: bone gives almost no MRI signal,
                       so it is the dark band between the bright scalp/fat and the brain envelope.
                       Approximate (a few mm) - replace with CT bone (ct_layers.py) when available.

Usage:
  python structural_extras.py --t1 orig.nii.gz --seg aparc.DKTatlas+aseg.deep.nii.gz \
      --head head.nii.gz --out extras/
"""
import argparse, json, os
import numpy as np, nibabel as nib
from scipy import ndimage
from skimage.filters import threshold_otsu
from skimage.morphology import ball

def largest(m):
    lab, n = ndimage.label(m)
    return m if n == 0 else lab == (np.argmax(np.bincount(lab.ravel())[1:]) + 1)

def main():
    ap = argparse.ArgumentParser()
    for k in ("t1", "seg", "head", "out"): ap.add_argument("--" + k, required=True)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    t1_img = nib.load(a.t1); t1 = np.asanyarray(t1_img.dataobj).astype(np.float32)
    seg = np.asanyarray(nib.load(a.seg).dataobj).astype(int)
    head = np.asanyarray(nib.load(a.head).dataobj) > 0
    vox = np.array(t1_img.header.get_zooms()[:3]); aff = t1_img.affine
    r = lambda mm: max(1, int(round(mm / vox.mean())))
    rep = {}

    print("1/3 sulci ...")
    brain = seg > 0
    envelope = ndimage.binary_closing(np.pad(brain, 10), structure=ball(r(6)))[10:-10, 10:-10, 10:-10]
    envelope = ndimage.binary_fill_holes(envelope)
    sulci = envelope & ~brain
    sulci = ndimage.binary_opening(sulci, iterations=1)
    nib.save(nib.Nifti1Image(sulci.astype(np.uint8), aff), os.path.join(a.out, "sulci.nii.gz"))
    rep["sulci_ml"] = round(float(sulci.sum() * vox.prod()) / 1000, 1)

    print("2/3 skull estimate from T1 ...")
    inner = ndimage.binary_dilation(envelope, iterations=r(1.5))           # brain + thin CSF layer
    d_scalp = ndimage.distance_transform_edt(head, sampling=vox)           # depth below skin [mm]
    d_brain = ndimage.distance_transform_edt(~envelope, sampling=vox)      # distance from brain envelope [mm]
    shell = head & ~inner & (d_scalp > 2.0) & (d_brain < 12.0)             # between skin and brain, cranium only
    thr = threshold_otsu(t1[shell])
    skull = shell & (t1 < thr)                                             # bone = dark on T1
    skull = ndimage.binary_closing(skull, iterations=2)
    skull = largest(ndimage.binary_opening(skull, iterations=1))
    nib.save(nib.Nifti1Image(skull.astype(np.uint8), aff), os.path.join(a.out, "skull_t1.nii.gz"))
    thick = 2 * ndimage.distance_transform_edt(skull, sampling=vox)
    rep.update({"skull_t1_ml": round(float(skull.sum() * vox.prod()) / 1000, 1),
                "skull_t1_thickness_mm_p50": round(float(np.percentile(thick[skull], 50)), 1) if skull.any() else None,
                "skull_origin": "ESTIMATE from T1 (no CT) - approximate"})
    print("3/3 superior sagittal sinus prior ...")
    ijk = np.argwhere(brain); xyz = nib.affines.apply_affine(aff, ijk)
    lh, rh = np.isin(seg, [2] + list(range(1000, 1036))), np.isin(seg, [41] + list(range(2000, 2036)))
    x_mid = 0.5 * (nib.affines.apply_affine(aff, np.argwhere(lh))[:, 0].max() + nib.affines.apply_affine(aff, np.argwhere(rh))[:, 0].min())
    vent = nib.affines.apply_affine(aff, np.argwhere(np.isin(seg, [4, 43])))
    allv = nib.affines.apply_affine(aff, np.indices(seg.shape).reshape(3, -1).T).reshape(seg.shape + (3,))
    gap = ~envelope & ~skull & head & (d_brain < 10.0)                     # between brain and skull
    sss = gap & (np.abs(allv[..., 0] - x_mid) < 5.0) & (allv[..., 2] > vent[:, 2].max())
    sss = ndimage.binary_closing(sss, iterations=1)
    sss = largest(sss) if sss.any() else sss
    nib.save(nib.Nifti1Image(sss.astype(np.uint8), aff), os.path.join(a.out, "sss_prior.nii.gz"))
    rep.update({"sss_prior_ml": round(float(sss.sum() * vox.prod()) / 1000, 2), "midline_x_mm": round(float(x_mid), 1),
                "sss_origin": "PRIOR from anatomical rules (midline gap above ventricles), not imaged"})
    json.dump(rep, open(os.path.join(a.out, "extras_report.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))

if __name__ == "__main__":
    main()
