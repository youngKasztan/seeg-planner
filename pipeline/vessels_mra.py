"""
vessels_mra.py - automatyczna ekstrakcja tetnic z surowego TOF-MRA.

Kroki:
 1. rejestracja sztywna MRA -> T1 pacjenta (SimpleITK, mutual information)
 2. maska mozgu z segmentacji T1 przeniesiona na siatke MRA (odcina naczynia skory i tluszcz)
 3. filtr naczyniowy Frangiego (wieloskalowy) + prog jasnosci TOF
 4. usuniecie drobnych wysp (szum)
 5. zapis maski naczyn z affine w przestrzeni T1 (gotowa dla seeg_prep.py --vessels)
 6. (opcjonalnie) porownanie z reczna segmentacja ekspertow: Dice, czulosc, precyzja

Uzycie:
  python vessels_mra.py --mra MRA.nii.gz --t1 orig.nii.gz --brainmask mask.nii.gz --out vessels.nii.gz [--truth labels.nii.gz]
"""
import argparse, json
import numpy as np, nibabel as nib, SimpleITK as sitk
from scipy import ndimage
from skimage.filters import frangi

LPS = np.diag([-1., -1., 1., 1.])

def sitk_from_nib(img, dtype=np.float32):
    """nibabel (RAS) -> SimpleITK (LPS) z zachowaniem geometrii."""
    a = LPS @ img.affine
    zooms = np.sqrt((a[:3, :3] ** 2).sum(0))
    im = sitk.GetImageFromArray(np.asanyarray(img.dataobj).astype(dtype).transpose(2, 1, 0))
    im.SetSpacing([float(z) for z in zooms]); im.SetOrigin([float(o) for o in a[:3, 3]])
    im.SetDirection([float(x) for x in (a[:3, :3] / zooms).flatten()])
    return im

def register(t1, mra):
    fixed = sitk.Normalize(sitk_from_nib(t1)); moving = sitk.Normalize(sitk_from_nib(mra))
    # IXI: badania z jednej sesji -> naglowki juz prawie zgodne; start od tozsamosci
    init = sitk.Euler3DTransform(); init.SetCenter(fixed.TransformContinuousIndexToPhysicalPoint(
        [s / 2 for s in fixed.GetSize()]))
    R = sitk.ImageRegistrationMethod()
    R.SetMetricAsMattesMutualInformation(32); R.SetMetricSamplingStrategy(R.RANDOM)
    R.SetMetricSamplingPercentage(0.05, seed=1); R.SetInterpolator(sitk.sitkLinear)
    R.SetOptimizerAsRegularStepGradientDescent(1.0, 1e-4, 200); R.SetOptimizerScalesFromPhysicalShift()
    R.SetShrinkFactorsPerLevel([4, 2, 1]); R.SetSmoothingSigmasPerLevel([2, 1, 0])
    R.SetInitialTransform(init, inPlace=False)
    tx = R.Execute(fixed, moving)       # mapuje punkty T1 -> punkty MRA
    return tx, R.GetMetricValue()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mra", required=True); ap.add_argument("--t1", required=True)
    ap.add_argument("--brainmask", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--truth"); ap.add_argument("--report")
    a = ap.parse_args()
    mra_img, t1_img = nib.load(a.mra), nib.load(a.t1)
    rep = {}

    print("1/5 rejestracja MRA -> T1 ...")
    tx, metric = register(t1_img, mra_img)
    inv = tx.GetInverse()                               # punkty MRA -> punkty T1
    p = np.array(tx.GetParameters()); rep["registration"] = {
        "rotation_deg": np.degrees(p[:3]).round(2).tolist(), "translation_mm": p[3:].round(2).tolist(),
        "mutual_information": round(metric, 4)}
    print("   ", rep["registration"])

    print("2/5 maska mozgu na siatce MRA ...")
    mra_s = sitk_from_nib(mra_img)
    bm = sitk.Resample(sitk_from_nib(nib.load(a.brainmask), np.uint8), mra_s, tx, sitk.sitkNearestNeighbor, 0)
    brain = sitk.GetArrayFromImage(bm).transpose(2, 1, 0) > 0
    brain = ndimage.binary_dilation(brain, iterations=4)          # ~2 mm zapasu na naczynia przy powierzchni

    print("3/5 filtr Frangiego ...")
    img = np.asanyarray(mra_img.dataobj).astype(np.float32)
    lo, hi = np.percentile(img[brain], [1, 99.9]); img = np.clip((img - lo) / (hi - lo), 0, 1)
    box = ndimage.find_objects(brain.astype(np.uint8))[0]
    v = np.zeros_like(img)
    v[box] = frangi(img[box], sigmas=[1, 1.5, 2, 3], black_ridges=False, alpha=0.5, beta=0.5, gamma=None)
    v[~brain] = 0

    print("4/5 progowanie + czyszczenie ...")
    inten_thr = np.percentile(img[brain], 97.5)                    # TOF: krew = najjasniejsze 2-3% mozgu
    vthr = np.percentile(v[brain], 97.0)
    ves = (v > vthr) & (img > inten_thr)
    ves = ndimage.binary_closing(ves, iterations=1)
    lab, n = ndimage.label(ves); sizes = ndimage.sum(ves, lab, range(1, n + 1))
    ves = np.isin(lab, 1 + np.where(sizes >= 30)[0])              # usun wyspy < 30 wokseli
    rep["vessel_voxels"] = int(ves.sum()); rep["vessel_volume_ml"] = round(float(ves.sum() * np.prod(mra_img.header.get_zooms()[:3])) / 1000, 2)

    if a.truth:
        gt = np.asanyarray(nib.load(a.truth).dataobj) > 0
        tp = (ves & gt).sum()
        rep["vs_expert"] = {"dice": round(2 * tp / (ves.sum() + gt.sum()), 3),
                            "sensitivity": round(tp / gt.sum(), 3), "precision": round(tp / max(ves.sum(), 1), 3)}
        print("   porownanie z ekspertami:", rep["vs_expert"])

    print("5/5 zapis (affine w przestrzeni T1) ...")
    # nowy affine: woksel MRA -> punkt MRA (LPS) -> T1 (LPS) -> RAS
    pts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], float)
    world = nib.affines.apply_affine(LPS @ mra_img.affine, pts)
    mapped = np.array([inv.TransformPoint(tuple(map(float, w))) for w in world])
    new = np.eye(4); new[:3, 3] = mapped[0]; new[:3, :3] = (mapped[1:] - mapped[0]).T
    new = LPS @ new
    nib.save(nib.Nifti1Image(ves.astype(np.uint8), new), a.out)
    if a.report:
        json.dump(rep, open(a.report, "w"), indent=1)
    print(json.dumps(rep, indent=1))

if __name__ == "__main__":
    main()
