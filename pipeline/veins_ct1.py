"""
veins_ct1.py - veins and dural sinuses from T1 before and after contrast (gadolinium).

Rationale:
  * TOF-MRA deliberately suppresses venous blood -> veins cannot be extracted from it
  * after gadolinium, arteries, veins and sinuses all enhance -> subtract the pre-contrast T1
    (only enhancing structures remain), then remove what is already an artery on TOF
  * sinuses (superior sagittal, transverse, sigmoid, straight) are large 5-10 mm "tubes" ->
    separate layer from a large-scale filter; cortical and bridging veins -> small scale

Steps:
 1. rigid registration: T1+Gd -> T1 (T1 = planning space)
 2. intensity normalisation (white-matter median = 1) and subtraction: sub = post - pre
 3. Frangi filter at two scales: small vessels (0.5-1.5 mm) and sinuses (3-5 mm)
 4. artery removal: voxels inside the (1 mm dilated) TOF artery mask
 5. output: veins.nii.gz, sinuses.nii.gz (affine in T1 space)

Usage:
  python veins_ct1.py --pre T1.nii.gz --post T1_gd.nii.gz --seg aparc.DKTatlas+aseg.deep.nii.gz \
      --out veins/ [--arteries vessels_auto.nii.gz]
Status: code ready, NOT validated - no public patient with pre/post-contrast T1 and TOF available yet.
"""
import argparse, json, os
import numpy as np, nibabel as nib, SimpleITK as sitk
from scipy import ndimage
from skimage.filters import frangi
from vessels_mra import sitk_from_nib, register

def resample_to(img_mov, img_ref, tx, interp=sitk.sitkLinear):
    r = sitk.Resample(sitk_from_nib(img_mov), sitk_from_nib(img_ref), tx, interp, 0.0)
    return sitk.GetArrayFromImage(r).transpose(2, 1, 0)

def main():
    ap = argparse.ArgumentParser()
    for k in ("pre", "post", "seg", "out"): ap.add_argument("--" + k, required=True)
    ap.add_argument("--arteries", help="artery mask from TOF-MRA, removed from the venous layers")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    pre_img, post_img, seg_img = nib.load(a.pre), nib.load(a.post), nib.load(a.seg)

    print("1/5 registering T1+Gd -> T1 ...")
    tx, _ = register(pre_img, post_img)
    post = resample_to(post_img, pre_img, tx)
    pre = np.asanyarray(pre_img.dataobj).astype(np.float32)
    seg = resample_to(seg_img, pre_img, sitk.Transform(), sitk.sitkNearestNeighbor).astype(int)

    print("2/5 subtraction ...")
    wm = np.isin(seg, [2, 41])
    pre /= np.median(pre[wm]); post /= np.median(post[wm])
    sub = np.clip(post - pre, 0, None)
    head = ndimage.binary_dilation(seg > 0, iterations=12)       # brain + ~1 cm (sinuses, surface veins)
    sub[~head] = 0
    sub /= np.percentile(sub[head], 99.5) + 1e-6; sub = np.clip(sub, 0, 1)

    vox = pre_img.header.get_zooms()[:3]; s = lambda mm: [m / float(np.mean(vox)) for m in mm]
    print("3/5 Frangi: small vessels and sinuses ...")
    small = frangi(sub, sigmas=s([0.5, 1.0, 1.5]), black_ridges=False)
    large = frangi(sub, sigmas=s([3, 4, 5]), black_ridges=False)
    veins = (small > np.percentile(small[head], 98)) & (sub > 0.15)
    sinuses = (large > np.percentile(large[head], 99)) & (sub > 0.25)
    sinuses = ndimage.binary_opening(sinuses, iterations=1)
    lab, n = ndimage.label(sinuses); sz = ndimage.sum(sinuses, lab, range(1, n + 1))
    sinuses = np.isin(lab, 1 + np.argsort(sz)[::-1][:6])          # a few largest components = sinus system

    if a.arteries:
        print("4/5 removing arteries ...")
        art_img = nib.load(a.arteries)
        art = resample_to(art_img, pre_img, sitk.Transform(), sitk.sitkNearestNeighbor) > 0
        art = ndimage.binary_dilation(art, iterations=1)
        veins &= ~art; sinuses &= ~art
    veins &= ~sinuses
    lab, n = ndimage.label(veins); sz = ndimage.sum(veins, lab, range(1, n + 1))
    veins = np.isin(lab, 1 + np.where(sz >= 20)[0])

    print("5/5 saving ...")
    for m, n in ((veins, "veins.nii.gz"), (sinuses, "sinuses.nii.gz")):
        nib.save(nib.Nifti1Image(m.astype(np.uint8), pre_img.affine), os.path.join(a.out, n))
    rep = {"veins_ml": round(float(veins.sum() * np.prod(vox)) / 1000, 2),
           "sinuses_ml": round(float(sinuses.sum() * np.prod(vox)) / 1000, 2), "validated": False}
    json.dump(rep, open(os.path.join(a.out, "veins_report.json"), "w"), indent=1); print(rep)

if __name__ == "__main__":
    main()
