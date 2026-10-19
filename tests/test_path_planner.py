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

    # 4. Stop button: planning raises Cancelled during the single paths ...
    pl.should_stop = lambda: True
    try: pl.plan_all({"A": [-20.0, -15.0, 0.0]}); raise AssertionError("not stopped")
    except planner.Cancelled: pass
    # ... and keeps the single paths if it is stopped while trying groups
    flag = {"stop": False}
    pl.progress = lambda f, msg="": flag.update(stop=flag["stop"] or "->" in msg)   # first group starts -> press Stop
    pl.should_stop = lambda: flag["stop"]
    chosen, unc, _ = pl.plan_all({"A": [-20.0, -15.0, 0.0], "B": [-20.0, -15.0, -20.0], "C": [20.0, -15.0, 0.0]})
    print(f"4. stopped during groups -> {len(chosen)} path(s), not reached: {unc}")
    assert chosen and all(c.feasible for c in chosen)
    pl.should_stop, pl.progress = (lambda: False), (lambda f, msg="": None)

    # 5. time limit 0 s: every target alone is still planned, no group is tried
    pl.pl = dict(pl.pl, time_limit_s=0)
    chosen, unc, cands = pl.plan_all({"A": [-20.0, -15.0, 0.0], "B": [-20.0, -15.0, -20.0]})
    print(f"5. time limit 0 s -> candidates {[c.targets for c in cands]}")
    assert all(len(c.targets) == 1 for c in cands) and len(chosen) == 2 and not unc

    # 6. collisions between paths: the two cheapest paths cross, so the selection must use the alternative
    def line(a, b, targets, cost):
        a, b = np.array(a, float), np.array(b, float)
        pts = a + (b - a) * np.linspace(0, 1, 60)[:, None]
        return planner.PathResult(targets, a, pts, True, cost, 0, 1e9, 0, 0)
    P1 = line([-40, 0, 20], [10, 0, 0], ["P"], 50)               # P and Q cross at (0, 0, 4)
    Q1 = line([40, 0, 20], [-10, 0, 0], ["Q"], 50)
    Q2 = line([40, 40, 20], [-10, 0, 0], ["Q"], 60)              # a bit longer, but far from P1 at the crossing
    print(f"6. conflicts {pl.conflicts([P1, Q1, Q2])}")
    chosen, unc = pl._select(["P", "Q"], [P1, Q1, Q2])
    print(f"   chosen {[(c.targets, c.cost) for c in chosen]}, not reached {unc}")
    assert (0, 1) in pl.conflicts([P1, Q1, Q2]) and sorted(c.cost for c in chosen) == [50, 60] and not unc
    chosen, unc = pl._select(["P", "Q"], [P1, Q1])              # no alternative: one target is reported
    assert len(chosen) == 1 and len(unc) == 1 and unc[0] in pl.collision_notes

    # 7. midline no-go zone: a line from the left to the right hemisphere is blocked, a left-only line is not
    cfg7 = dict(cfg, no_go=dict(cfg["no_go"], midline={"computed": "midline", "margin_mm": 1.0}))
    pt7 = patient.Patient(d, cfg7, log=lambda *a: None)
    cross = np.array([[-20.0, 10.0, 0.0]]) + np.array([[1.0, 0, 0]]) * np.linspace(0, 40, 81)[:, None]
    left = np.array([[-30.0, 10.0, 0.0]]) + np.array([[1.0, 0, 0]]) * np.linspace(0, 20, 41)[:, None]
    print(f"7. midline zone: crossing line min clearance {pt7.C_strict(cross).min():.1f} mm, left-only line {pt7.C_strict(left).min():.1f} mm")
    assert pt7.C_strict(cross).min() < 0 < pt7.C_strict(left).min()
print("OK")
