"""
atlas_priors.py - probabilistic (atlas-based) layers for exams the patient does NOT have.

Used only when the patient-specific exam is missing. Every output is marked as a PRIOR in the
manifest: it shows where a structure usually is in the population, not where it is in this patient.

Currently:
  * veins / dural sinuses from the VENAT probabilistic venous atlas (Huck et al. 2019,
    7T QSM of 20 subjects, MNI152 space, 0.5 mm) -> used when there is no contrast T1 / venography.

Steps:
 1. register the MNI152 template to the patient T1 (affine + B-spline deformable, SimpleITK)
 2. warp the atlas probability map into the patient T1 grid
 3. save the probability map and a thresholded "likely vein" mask (affine = patient T1 space)

Usage:
  python atlas_priors.py --t1 orig.nii.gz --brainmask mask.nii.gz \
      --venat VENAT_PartialVolume.nii.gz --out priors/
Atlas download: https://figshare.com/articles/dataset/VENAT_Probability_map_nii_gz/7205960
"""
import argparse, json, os
import numpy as np, nibabel as nib, SimpleITK as sitk
from scipy import ndimage
from vessels_mra import sitk_from_nib

def mni_template():
    from nilearn import datasets
    return datasets.load_mni152_template(resolution=1)

def register_mni_to_patient(t1_img, mask_img, tpl_img):
    """Returns a transform mapping patient points -> MNI points (fixed = patient)."""
    t1 = np.asanyarray(t1_img.dataobj).astype(np.float32)
    brain = np.asanyarray(mask_img.dataobj) > 0
    fixed = sitk_from_nib(nib.Nifti1Image(t1 * brain, t1_img.affine))
    moving = sitk_from_nib(tpl_img)
    # note: no intensity normalisation - MOMENTS initialisation needs non-negative intensities

    def method(lr, iters):
        R = sitk.ImageRegistrationMethod()
        R.SetMetricAsMattesMutualInformation(48); R.SetMetricSamplingStrategy(R.RANDOM)
        R.SetMetricSamplingPercentage(0.1, seed=1); R.SetInterpolator(sitk.sitkLinear)
        R.SetOptimizerAsRegularStepGradientDescent(lr, 1e-4, iters, relaxationFactor=0.6)
        R.SetOptimizerScalesFromPhysicalShift()
        R.SetShrinkFactorsPerLevel([4, 2, 1]); R.SetSmoothingSigmasPerLevel([2, 1, 0])
        return R
    # rigid first (robust), then affine (head size/shape), then B-spline (local shape)
    rigid0 = sitk.CenteredTransformInitializer(fixed, moving, sitk.VersorRigid3DTransform(),
                                               sitk.CenteredTransformInitializerFilter.MOMENTS)
    R = method(2.0, 200); R.SetInitialTransform(rigid0, inPlace=True)
    R.Execute(fixed, moving)
    print("    rigid done, MI", round(R.GetMetricValue(), 4), flush=True)
    affine = sitk.AffineTransform(3); affine.SetCenter(rigid0.GetCenter())
    affine.SetMatrix(rigid0.GetMatrix()); affine.SetTranslation(rigid0.GetTranslation())
    R = method(0.5, 300); R.SetInitialTransform(affine, inPlace=True)
    R.Execute(fixed, moving)
    m_aff = R.GetMetricValue()
    print("    affine done, MI", round(m_aff, 4), flush=True)

    # deformable refinement (coarse B-spline grid, ~3 cm control-point spacing)
    bs = sitk.BSplineTransformInitializer(fixed, [4, 4, 4])
    R2 = sitk.ImageRegistrationMethod()
    R2.SetMetricAsMattesMutualInformation(48); R2.SetMetricSamplingStrategy(R2.RANDOM)
    R2.SetMetricSamplingPercentage(0.02, seed=1); R2.SetInterpolator(sitk.sitkLinear)
    R2.SetOptimizerAsLBFGSB(gradientConvergenceTolerance=1e-5, numberOfIterations=40)
    R2.SetShrinkFactorsPerLevel([4, 2]); R2.SetSmoothingSigmasPerLevel([2, 1])
    R2.SetMovingInitialTransform(affine)
    R2.SetInitialTransform(bs, inPlace=True)
    R2.Execute(fixed, moving)
    tx = sitk.CompositeTransform([affine, bs])
    return tx, {"affine_mi": round(m_aff, 4), "bspline_mi": round(R2.GetMetricValue(), 4)}

def main():
    ap = argparse.ArgumentParser()
    for k in ("t1", "brainmask", "venat", "out"): ap.add_argument("--" + k, required=True)
    ap.add_argument("--vein_threshold", type=float, default=0.15,
                    help="partial-volume probability above which a voxel is shown as 'likely vein'")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    t1_img, mask_img = nib.load(a.t1), nib.load(a.brainmask)

    print("1/3 registering MNI152 template -> patient T1 (affine + B-spline) ...")
    tx, rep = register_mni_to_patient(t1_img, mask_img, mni_template())
    print("   ", rep)

    print("2/3 warping VENAT probability map into patient space ...")
    ref = sitk_from_nib(t1_img)
    venat = sitk_from_nib(nib.load(a.venat))
    prob = sitk.GetArrayFromImage(sitk.Resample(venat, ref, tx, sitk.sitkLinear, 0.0)).transpose(2, 1, 0)
    prob = np.clip(prob, 0, 1).astype(np.float32)
    nib.save(nib.Nifti1Image(prob, t1_img.affine), os.path.join(a.out, "veins_prior_probability.nii.gz"))

    print("3/3 thresholding ...")
    veins = prob > a.vein_threshold
    lab, n = ndimage.label(veins); sz = ndimage.sum(veins, lab, range(1, n + 1))
    veins = np.isin(lab, 1 + np.where(sz >= 20)[0])
    nib.save(nib.Nifti1Image(veins.astype(np.uint8), t1_img.affine), os.path.join(a.out, "veins_prior.nii.gz"))
    vox = t1_img.header.get_zooms()[:3]
    rep.update({"atlas": "VENAT (Huck et al. 2019), MNI152, 0.5 mm",
                "threshold": a.vein_threshold, "veins_prior_ml": round(float(veins.sum() * np.prod(vox)) / 1000, 2),
                "origin": "PRIOR - population atlas registered to patient, NOT patient-specific"})
    json.dump(rep, open(os.path.join(a.out, "priors_report.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))

if __name__ == "__main__":
    main()
