"""head_mask.py - maska glowy (skora) z T1: prog Otsu, najwieksza skladowa, wypelnienie dziur.
Uzycie: python head_mask.py --t1 orig.nii.gz --out head.nii.gz
Docelowo zastapione maska z CT (kosc + skora), gdy CT jest dostepne."""
import argparse
import numpy as np, nibabel as nib
from scipy import ndimage
from skimage.filters import threshold_otsu

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--t1", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    img = nib.load(a.t1); t1 = np.asanyarray(img.dataobj).astype(float)
    h = t1 > threshold_otsu(t1) * 0.5
    lab, _ = ndimage.label(h); h = lab == np.argmax(np.bincount(lab.ravel())[1:]) + 1
    h = ndimage.binary_closing(h, iterations=3)
    h = np.stack([ndimage.binary_fill_holes(s) for s in h], 0)
    nib.save(nib.Nifti1Image(h.astype(np.uint8), img.affine), a.out)
    print(f"head mask: {h.sum() / 1000:.0f} ml -> {a.out}")

if __name__ == "__main__":
    main()
