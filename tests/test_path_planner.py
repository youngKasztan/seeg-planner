"""
Continuum-robot path planner on a synthetic head (no patient data needed):  python tests/test_path_planner.py
  1. an artery runs right above a target: the path must keep the margin and never bend tighter than the robot allows
  2. two targets on one vertical line: the planner must reach both with ONE path
  3. a target inside a no-go zone is reported, not planned
"""
import os, sys, tempfile
import numpy as np, nibabel as nib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "path_planner"))
import config, patient, planner

def synthetic_patient(folder):
    N = 101; aff = np.diag([1.0, 1, 1, 1]); aff[:3, 3] = -50                  # 1 mm grid, centre (0, 0, 0)
    X = np.stack(np.meshgrid(*[np.arange(N) - 50.0] * 3, indexing="ij"), -1)
    r = np.linalg.norm(X, axis=-1)
    head, brain = r <= 48, r <= 40
    lab = np.zeros((N, N, N), np.int16)
    x, y = X[..., 0], X[..., 1]
    lab[brain & (x < 0) & (y >= 0)] = 1003; lab[brain & (x < 0) & (y < 0)] = 1005
    lab[brain & (x >= 0) & (y >= 0)] = 2003; lab[brain & (x >= 0) & (y < 0)] = 2005
    vessel = (np.abs(X[..., 1] - 10) <= 1) & (np.abs(X[..., 2] - 15) <= 1) & brain                          # tube along x at y=10, z=15
    t1 = np.where(head, 80.0, 0.0) + np.where(brain, 40.0, 0.0)
    for name, a in (("orig", t1), ("aparc.DKTatlas+aseg.deep", lab), ("head", head), ("mask", brain), ("vessels_auto", vessel)):
        nib.save(nib.Nifti1Image(a.astype(np.float32 if name == "orig" else np.uint8 if name != "aparc.DKTatlas+aseg.deep" else np.int16), aff),
                 os.path.join(folder, name + ".nii.gz"))

cfg = config.load()
cfg["no_go"] = {"arteries": cfg["no_go"]["arteries"], "outside_brain": cfg["no_go"]["outside_brain"]}
cfg["avoid"] = {}
cfg["robot"]["max_entry_angle_deg"] = 35.0
with tempfile.TemporaryDirectory() as d:
    synthetic_patient(d)
    pt = patient.Patient(d, cfg, log=lambda *a: None)
    pl = planner.Planner(pt, cfg, log=lambda *a: None)
    rb = cfg["robot"]

    r = pl.plan_sequence(["T"], [np.array([0.0, 10.0, 0.0])])         # artery 15 mm straight above the target
    art = r.min_clearance_mm["arteries"]
    print(f"1. feasible {r.feasible}, artery clearance {art} mm (needs >= {cfg['no_go']['arteries']['margin_mm']}), "
          f"min bend radius {r.min_radius_mm:.0f} mm (needs >= {rb['min_bend_radius_mm']}), length {r.length_mm:.0f} mm")
    assert r.feasible and art >= cfg["no_go"]["arteries"]["margin_mm"] - 0.1 and r.min_radius_mm >= rb["min_bend_radius_mm"] * 0.97

    chosen, unc, _ = pl.plan_all({"A": [-20.0, -15.0, 0.0], "B": [-20.0, -15.0, -20.0]})
    print(f"2. targets A (upper) and B (lower) -> {len(chosen)} path(s): {[c.targets for c in chosen]}")
    assert len(chosen) == 1 and chosen[0].targets == ["A", "B"] and not unc

    chosen, unc, _ = pl.plan_all({"inside artery": [0.0, 10.0, 15.0]})
    print(f"3. target inside an artery -> not planned, reported: {unc} ({pl.target_problems})")
    assert unc == ["inside artery"] and not chosen
print("OK")
