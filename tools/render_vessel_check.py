"""render_vessel_check.py - visual check of automatic arteries vs expert segmentation (MIP from above).
yellow = both, red = automatic only, green = experts only.
Usage: python tools/render_vessel_check.py --mra MRA.nii.gz --auto vessels_auto.nii.gz --truth labels.nii.gz --out check.png"""
import argparse, json
import numpy as np, nibabel as nib, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt

def main():
    ap = argparse.ArgumentParser()
    for k in ("mra", "auto", "truth", "out"): ap.add_argument("--" + k, required=True)
    a = ap.parse_args()
    mra = np.asanyarray(nib.load(a.mra).dataobj).astype(float)
    au = np.asanyarray(nib.load(a.auto).dataobj) > 0      # same voxel grid as the MRA
    gt = np.asanyarray(nib.load(a.truth).dataobj) > 0
    dice = 2 * (au & gt).sum() / (au.sum() + gt.sum())
    mip = mra.max(2); g, m = gt.max(2), au.max(2)
    rgb = np.zeros(mip.shape + (4,)); rgb[m & g] = [1, 1, 0, .8]; rgb[m & ~g] = [1, 0, 0, .8]; rgb[g & ~m] = [0, 1, 0, .8]
    fig, ax = plt.subplots(figsize=(8, 8.6), facecolor="black")
    ax.imshow(np.rot90(mip), cmap="gray", vmax=np.percentile(mip, 99.5)); ax.imshow(np.rot90(rgb)); ax.axis("off")
    ax.set_title(f"Arteries, MIP from above - Dice {dice:.2f}\nyellow = both   red = automatic only   green = experts only",
                 color="w", fontsize=12)
    plt.tight_layout(); plt.savefig(a.out, dpi=90, facecolor="black"); print("check ->", a.out, "Dice", round(dice, 3))

if __name__ == "__main__":
    main()
