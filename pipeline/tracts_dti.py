"""
tracts_dti.py - drogi istoty bialej z DTI (bez MRtrix, czysty Python / DIPY).

Drogi krytyczne dla SEEG:
  cst_L / cst_R        droga korowo-rdzeniowa (ruch): kora przedsrodkowa <-> pien mozgu
  arcuate_L            peczek lukowaty (mowa, lewa polkula): okolica Broki <-> tylny plat skroniowy
  optic_rad_L / _R     promienistosc wzrokowa: wzgorze (LGN) <-> kora wzrokowa

Kroki:
 1. zlozenie wolumenow DTI w 4D + bvals/bvecs
 2. rejestracja sztywna b0 -> T1 (ta sama funkcja co dla MRA)
 3. segmentacja FastSurfer przeniesiona na siatke DTI (ROI dla traktografii)
 4. model tensora (FA, kierunek glowny), traktografia deterministyczna z ROI
 5. filtr: zostaja wlokna laczace oba ROI danej drogi
 6. maska gestosci wlokien -> NIfTI z affine w przestrzeni T1 (+ plik .trk do podgladu)

Uzycie:
  python tracts_dti.py --dti_dir IXI057_DTI --bvals bvals.txt --bvecs bvecs.txt \
      --t1 orig.nii.gz --seg aparc.DKTatlas+aseg.deep.nii.gz --out tracts/
"""
import argparse, glob, json, os
import numpy as np, nibabel as nib, SimpleITK as sitk
from scipy import ndimage
from dipy.core.gradients import gradient_table
from dipy.reconst.dti import TensorModel, fractional_anisotropy
from dipy.direction import peaks_from_model
from dipy.data import default_sphere
from dipy.tracking.local_tracking import LocalTracking
from dipy.tracking.stopping_criterion import ThresholdStoppingCriterion
from dipy.tracking.streamline import Streamlines
from dipy.tracking import utils as tutils
from vessels_mra import sitk_from_nib, register, LPS

LEFT = [2, 10, 11, 12, 13, 17, 18, 26, 28] + list(range(1000, 1036))
RIGHT = [41, 49, 50, 51, 52, 53, 54, 58, 60] + list(range(2000, 2036))
CEREB = [7, 8, 46, 47]
FRONTAL_L = [1003, 1012, 1014, 1027, 1028, 1032]; FRONTAL_R = [x + 1000 for x in FRONTAL_L]
TRACTS = {
    # nazwa: (ROI A, ROI B, etykiety wykluczajace, kolor)
    "cst_L":       ([1024],       [16],               RIGHT + CEREB,                              [255, 80, 80, 255]),
    "cst_R":       ([2024],       [16],               LEFT + CEREB,                               [255, 80, 80, 255]),
    "arcuate_L":   ([1018, 1020], [1030, 1015, 1031], RIGHT + CEREB + [10, 16, 11, 12, 13, 1021, 1005, 1013], [255, 220, 60, 255]),
    "optic_rad_L": ([10],         [1021, 1005, 1013], RIGHT + CEREB + [16] + FRONTAL_L,           [80, 200, 255, 255]),
    "optic_rad_R": ([49],         [2021, 2005, 2013], LEFT + CEREB + [16] + FRONTAL_R,            [80, 200, 255, 255]),
}

def load_dti(d):
    files = sorted(glob.glob(os.path.join(d, "*DTI-*.nii.gz")))
    imgs = [nib.load(f) for f in files]
    data = np.stack([np.asanyarray(i.dataobj).astype(np.float32) for i in imgs], -1)
    return data, imgs[0].affine, imgs[0].header.get_zooms()[:3], files

def read_grad(bvals, bvecs, n, data):
    """Gradienty. IXI: 17 wolumenow, a bvals/bvecs maja 16 kolumn (kol. 0 = b0).
    Test dopasowania tensora (residuum 0.051 vs 0.092 dla innych wariantow) pokazal, ze tabela
    odpowiada wolumenom 0-15; wolumen 16 jest dodatkowy i jest pomijany."""
    bv = np.loadtxt(bvals).ravel()
    bc = np.loadtxt(bvecs); bc = bc.T if bc.shape[0] == 3 else bc
    m = min(n, len(bv), len(bc))
    return bv[:m], bc[:m], m

def choose_flip(data, bvals, bvecs, daff, dvox, seg, n_seeds=1500):
    """Konwencja znakow bvecs rozni sie miedzy skanerami/eksportami. Metoda Jeurissena (2014):
    przy blednej konwencji wlokna sa krotkie, bo "skrecaja" w zlym kierunku. Dla kazdego wariantu
    robimy szybka traktografie z losowych punktow istoty bialej i wybieramy najdluzsze srednio wlokna."""
    wm = np.isin(seg, [2, 41])
    rng = np.random.default_rng(0)
    idx = np.argwhere(wm); idx = idx[rng.choice(len(idx), min(n_seeds, len(idx)), replace=False)]
    seeds = nib.affines.apply_affine(daff, idx.astype(float))
    results = {}
    for flip in [(1, 1, 1), (-1, 1, 1), (1, -1, 1), (1, 1, -1)]:
        g = gradient_table(bvals, bvecs=bvecs * np.array(flip), b0_threshold=50)
        m = TensorModel(g)
        fa = np.nan_to_num(fractional_anisotropy(m.fit(data, mask=wm | (seg > 0)).evals))
        pk = peaks_from_model(m, data, default_sphere, 0.5, 25, mask=seg > 0, npeaks=1)
        sl = Streamlines(LocalTracking(pk, ThresholdStoppingCriterion(fa, 0.15), seeds, daff, step_size=0.5))
        results[flip] = float(np.mean([len(x) for x in sl]) * 0.5) if len(sl) else 0.0
    best = max(results, key=results.get)
    return best, {",".join(map(str, k)): round(v, 1) for k, v in results.items()}

def main():
    ap = argparse.ArgumentParser()
    for k in ("dti_dir", "bvals", "bvecs", "t1", "seg", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--fa_stop", type=float, default=0.15)
    ap.add_argument("--seeds_per_voxel", type=int, default=2)
    ap.add_argument("--flip", help="wymus konwencje bvecs, np. 1,-1,1 (domyslnie wybor automatyczny)")
    ap.add_argument("--only", help="tylko wybrane drogi, np. cst_L,cst_R")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rep = {}

    print("1/6 wczytanie DTI ...")
    data, daff, dvox, files = load_dti(a.dti_dir)
    bvals, bvecs, m = read_grad(a.bvals, a.bvecs, data.shape[-1], data)
    data = data[..., :m]
    rep["dti"] = {"volumes": int(data.shape[-1]), "voxel_mm": [round(float(v), 2) for v in dvox],
                  "b_values": sorted(set(int(b) for b in bvals))}

    print("2/6 rejestracja b0 -> T1 ...")
    b0 = nib.Nifti1Image(data[..., bvals < 50].mean(-1), daff)
    tx, metric = register(nib.load(a.t1), b0)          # punkty T1 -> punkty DTI
    p = np.array(tx.GetParameters())
    rep["registration"] = {"rotation_deg": np.degrees(p[:3]).round(2).tolist(),
                           "translation_mm": p[3:].round(2).tolist(), "mutual_information": round(metric, 4)}
    print("   ", rep["registration"])

    print("3/6 segmentacja na siatce DTI ...")
    seg_s = sitk.Resample(sitk_from_nib(nib.load(a.seg), np.int32), sitk_from_nib(b0), tx,
                          sitk.sitkNearestNeighbor, 0, sitk.sitkInt32)
    seg = sitk.GetArrayFromImage(seg_s).transpose(2, 1, 0)
    brain = ndimage.binary_dilation(seg > 0, iterations=1)
    if a.flip:
        flip, sc = tuple(int(x) for x in a.flip.split(",")), "podane recznie"
    else:
        flip, sc = choose_flip(data, bvals, bvecs, daff, dvox, seg)
    gtab = gradient_table(bvals, bvecs=bvecs * np.array(flip), b0_threshold=50)
    rep["bvec_flip"] = list(flip); rep["orientation_score"] = sc
    print("    konwencja bvecs:", flip, "srednia dlugosc wlokien [mm] per wariant:", sc)

    print("4/6 tensor + traktografia ...")
    model = TensorModel(gtab)
    fa = fractional_anisotropy(model.fit(data, mask=brain).evals)
    fa = np.nan_to_num(fa); fa[~brain] = 0
    peaks = peaks_from_model(model, data, default_sphere, relative_peak_threshold=0.5,
                             min_separation_angle=25, mask=brain, npeaks=1)
    stop = ThresholdStoppingCriterion(fa, a.fa_stop)
    nib.save(nib.Nifti1Image(fa.astype(np.float32), daff), os.path.join(a.out, "fa_dti_space.nii.gz"))

    # nowy affine: woksel DTI -> swiat T1 (jak dla MRA)
    inv = tx.GetInverse()
    pts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], float)
    world = nib.affines.apply_affine(LPS @ daff, pts)
    mapped = np.array([inv.TransformPoint(tuple(map(float, w))) for w in world])
    t1aff = np.eye(4); t1aff[:3, 3] = mapped[0]; t1aff[:3, :3] = (mapped[1:] - mapped[0]).T
    t1aff = LPS @ t1aff

    print("5/6 drogi ...")
    rep["tracts"] = {}
    wm = np.isin(seg, [2, 41, 16, 28, 60])
    for name, (ra, rb, excl, _) in TRACTS.items():
        if a.only and name not in a.only.split(","): continue
        A0, B0 = np.isin(seg, ra), np.isin(seg, rb)
        if not A0.any() or not B0.any():
            print(f"   {name}: brak ROI"); continue
        A = ndimage.binary_dilation(A0, iterations=3); B = ndimage.binary_dilation(B0, iterations=3)
        X = np.isin(seg, excl) & ~A & ~B                                  # nie wolno przez to przejsc
        keep = []
        for S in (A0, B0):                                               # siew z obu koncow drogi
            # siew w istocie bialej tuz pod/obok ROI (kora ma niskie FA - tam traktografia sie zatrzymuje)
            S = ndimage.binary_dilation(S, iterations=2) & wm
            seeds = tutils.seeds_from_mask(S & (fa > a.fa_stop), daff, density=a.seeds_per_voxel)
            for s_ in LocalTracking(peaks, stop, seeds, daff, step_size=0.5, max_cross=1):
                if len(s_) < 20: continue
                e0, e1 = _vals(s_[[0, -1]], A, daff), _vals(s_[[0, -1]], B, daff)
                if not ((e0[0] and e1[1]) or (e0[1] and e1[0])): continue   # konce: jeden w A, drugi w B
                if _vals(s_, X, daff).any(): continue
                keep.append(s_)
        dens = tutils.density_map(keep, daff, seg.shape) if keep else np.zeros(seg.shape)
        mask = dens >= max(3, 0.05 * dens.max()) if keep else dens > 0
        mask = ndimage.binary_closing(mask, iterations=1)
        lab, n = ndimage.label(mask)
        if n > 1: mask = lab == (np.argmax(np.bincount(lab.ravel())[1:]) + 1)
        nib.save(nib.Nifti1Image(mask.astype(np.uint8), t1aff), os.path.join(a.out, f"{name}.nii.gz"))
        if keep:
            from dipy.io.streamline import save_tractogram
            from dipy.io.stateful_tractogram import StatefulTractogram, Space
            save_tractogram(StatefulTractogram(keep, b0, Space.RASMM), os.path.join(a.out, f"{name}_dti_space.trk"),
                            bbox_valid_check=False)
        rep["tracts"][name] = {"streamlines": len(keep), "volume_ml": round(float(mask.sum() * np.prod(dvox)) / 1000, 2)}
        print(f"   {name:12s} {len(keep):5d} wlokien  {rep['tracts'][name]['volume_ml']} ml")

    print("6/6 zapis raportu")
    json.dump(rep, open(os.path.join(a.out, "tracts_report.json"), "w"), indent=1)

def _vals(pts, roi, aff):
    ijk = np.round(nib.affines.apply_affine(np.linalg.inv(aff), pts)).astype(int)
    ijk = np.clip(ijk, 0, np.array(roi.shape) - 1)
    return roi[ijk[:, 0], ijk[:, 1], ijk[:, 2]]

def _hits(s, roi, aff):
    ijk = np.round(nib.affines.apply_affine(np.linalg.inv(aff), s)).astype(int)
    ok = np.all((ijk >= 0) & (ijk < roi.shape), 1)
    ijk = ijk[ok]
    return roi[ijk[:, 0], ijk[:, 1], ijk[:, 2]].any()

if __name__ == "__main__":
    main()
