"""
Planner test on a synthetic head (no patient data needed):  python tests/test_planner.py
  1. a vessel runs right above a target: the shortest (straight down) path must be rejected and the chosen
     path must keep >= 2 mm from the vessel
  2. two targets on one horizontal line: they must share ONE electrode (fewer electrodes, same safety)
"""
import os, sys
import numpy as np
from scipy import ndimage
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "planner"))
import trajectory_planner as tp

N = 121; aff = np.eye(4); aff[:3, 3] = -60                       # 1 mm grid, centre at (0, 0, 0)
X = np.stack(np.meshgrid(*[np.arange(N) - 60] * 3, indexing="ij"), -1).astype(float)
r = np.linalg.norm(X, axis=-1)
head, brain = r <= 55, r <= 45
vessel = (np.abs(X[..., 1]) <= 1) & (np.abs(X[..., 2] - 12) <= 1) & brain        # tube along x, 12 mm above the origin
dist_v = ndimage.distance_transform_edt(~vessel).astype(np.float32)
maps = tp.DistanceMaps({"vessels": (dist_v, aff)})

def fn(mask):
    inv = np.linalg.inv(aff)
    def f(p):
        i = np.round(inv[:3, :3] @ p + inv[:3, 3]).astype(int)
        return bool(np.all(i >= 0) and np.all(i < N) and mask[tuple(i)])
    return f

k = np.arange(6000) + 0.5                                       # Fibonacci points on the scalp sphere
phi, th = np.arccos(1 - 2 * k / 6000), np.pi * (1 + 5 ** 0.5) * k
nrm = np.c_[np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)]
pts = 55 * nrm
allowed = pts[:, 2] > -15                                        # no entries from below
s = tp.Settings(max_length_mm=80)

chosen, unc, _ = tp.plan({"T": [0, 0, 0]}, maps, pts, nrm, allowed, fn(head), fn(brain), s)
e = chosen[0]
straight_ok, *_ = tp.evaluate_lines(np.array([[0, 0, 55.0]]), np.zeros(3), maps, np.array([[0, 0, 1.0]]), s)
print(f"1. straight-down path feasible: {bool(straight_ok[0])}; chosen entry {np.round(e.entry, 1)}, "
      f"min vessel distance {e.min_dist['vessels']} mm")
assert not straight_ok[0] and e.min_dist["vessels"] >= 2.0 and not unc

chosen, unc, cands = tp.plan({"A": [0, -20, -5], "B": [20, -20, -5]}, maps, pts, nrm, allowed, fn(head), fn(brain), s)
print(f"2. targets A, B -> {len(chosen)} electrode(s): {[c.targets for c in chosen]}")
assert len(chosen) == 1 and set(chosen[0].targets) == {"A", "B"} and not unc
print("OK")
