"""
registration.py - patient-to-image registration maths (reference implementation for the headset app).

  kabsch(P, Q)            rigid transform that maps landmark points P (model) onto Q (measured on the patient)
  icp(points, surface)    refine with many surface points (e.g. touched with the controller) against the scalp mesh
  fre / tre               fiducial / target registration error in mm

The Unity C# script (unity/Assets/SeegPlanner/LandmarkRegistration.cs) implements the same kabsch().
Run this file to self-test with a synthetic head: python tools/registration.py
"""
import numpy as np

def kabsch(P, Q):
    """Find R, t minimising sum ||R p_i + t - q_i||^2 (P, Q: N x 3, N >= 3, same order)."""
    P, Q = np.asarray(P, float), np.asarray(Q, float)
    cp, cq = P.mean(0), Q.mean(0)
    H = (P - cp).T @ (Q - cq)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))            # avoid reflections
    D = np.diag([1, 1, d])
    Rm = Vt.T @ D @ U.T
    return Rm, cq - Rm @ cp

def apply(Rm, t, X):
    return np.asarray(X) @ Rm.T + t

def fre(Rm, t, P, Q):
    return float(np.sqrt(((apply(Rm, t, P) - Q) ** 2).sum(1).mean()))

def icp(points, surface_vertices, Rm=np.eye(3), t=np.zeros(3), iters=30):
    """Iterative closest point: refine (Rm, t) so measured points lie on the model surface.
    points: measured on the patient (N x 3); surface_vertices: model scalp vertices (M x 3).
    Returns the transform model -> patient."""
    from scipy.spatial import cKDTree
    tree = cKDTree(surface_vertices)
    Rinv, tinv = Rm.T, -Rm.T @ t                         # patient -> model
    for _ in range(iters):
        x = apply(Rinv, tinv, points)
        _, idx = tree.query(x)
        Rinv, tinv = kabsch(points, surface_vertices[idx])
    return Rinv.T, -Rinv.T @ tinv

def _selftest():
    rng = np.random.default_rng(1)
    # synthetic "scalp": ellipsoid 75 x 95 x 80 mm
    u, v = rng.uniform(0, 2 * np.pi, 4000), rng.uniform(0.2, np.pi / 2 + 0.6, 4000)
    S = np.c_[75 * np.cos(u) * np.sin(v), 95 * np.sin(u) * np.sin(v), 80 * np.cos(v)]
    lm = S[rng.choice(len(S), 5, replace=False)]                       # 5 landmarks on the model
    ang = np.radians([8, -12, 20]); cx, cy, cz = np.cos(ang); sx, sy, sz = np.sin(ang)
    Rtrue = (np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
             @ np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]))
    ttrue = np.array([120.0, -40.0, 300.0])
    measured = apply(Rtrue, ttrue, lm) + rng.normal(0, 2.0, lm.shape)   # 2 mm touch error per landmark
    Rm, t = kabsch(lm, measured)
    target = np.array([[10, 20, 30.0]])                                 # deep target (e.g. hippocampus)
    tre_l = np.linalg.norm(apply(Rm, t, target) - apply(Rtrue, ttrue, target))
    surf_pts = apply(Rtrue, ttrue, S[rng.choice(len(S), 60, replace=False)]) + rng.normal(0, 1.0, (60, 3))
    Ri, ti = icp(surf_pts, S, Rm, t)
    tre_i = np.linalg.norm(apply(Ri, ti, target) - apply(Rtrue, ttrue, target))
    print(f"landmarks only: FRE {fre(Rm, t, lm, measured):.2f} mm, target error {tre_l:.2f} mm")
    print(f"+ ICP on 60 surface points: target error {tre_i:.2f} mm")
    assert tre_l < 6 and tre_i < 6
    print("OK")

if __name__ == "__main__":
    _selftest()
