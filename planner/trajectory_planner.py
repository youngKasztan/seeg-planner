"""
trajectory_planner.py - SEEG electrode trajectory planning on the patient package.

Idea
  Every electrode is a straight line from an entry point on the scalp to its deepest point (the tip).
  For each target the planner tries many entry points, rejects lines that come too close to critical
  structures (hard limits), scores the rest (soft risk: closeness to structures, length, drilling angle)
  and keeps the best. Targets that lie (almost) on one line can share an electrode, because an SEEG
  electrode has 5-18 contacts along its shaft. A small integer program then picks the set of electrodes
  that covers all targets with the fewest electrodes and the lowest total risk.

All coordinates are scanner RAS millimetres (same as the package). Distances to structures come from the
distance maps dist_<structure>.nii.gz written by pipeline/seeg_prep.py (NaN = outside that exam's field of view).

Research prototype - the rules and weights below are defaults, not clinically validated.
"""
from dataclasses import dataclass, field
import itertools
import numpy as np
import nibabel as nib
from scipy import ndimage

# structure name prefix -> hard minimum distance [mm] (None = no hard limit), soft scale [mm], weight,
#                          ignore within this many mm of the tip (structures that naturally touch targets)
RULES = {
    "vessels":         (2.0, 4.0, 10.0, 0.0),   # arteries from MRA/CTA - the main bleeding risk
    "veins":           (2.0, 4.0, 6.0, 0.0),    # veins from contrast T1 (patient)
    "sinuses":         (5.0, 5.0, 10.0, 0.0),
    "sinus_sss_prior": (4.0, 5.0, 6.0, 0.0),    # PRIOR (rules), still a hard limit: the sinus is always there
    "veins_prior":     (None, 3.0, 3.0, 0.0),   # PRIOR (atlas): soft only, it is not this patient's anatomy
    "brainstem":       (5.0, 5.0, 10.0, 3.0),   # incl. ventral diencephalon (FreeSurfer 28/60)
    "ventricles":      (2.0, 3.0, 3.0, 4.0),    # hippocampus/amygdala lie next to the temporal horn
    "sulci":           (None, 1.5, 2.0, 3.0),   # crossing a sulcus = small pial vessels
    "eloquent":        (None, 3.0, 1.5, 3.0),
    "cst":             (None, 3.0, 2.0, 3.0),
    "arcuate":         (None, 3.0, 1.0, 3.0),
    "optic_rad":       (None, 3.0, 1.5, 3.0),
    "uncinate":        (None, 3.0, 0.5, 3.0),
    "ifof":            (None, 3.0, 0.5, 3.0),
}

@dataclass
class Settings:
    max_length_mm: float = 100.0        # entry (skin) to tip
    max_angle_deg: float = 35.0         # between the electrode and the skin normal (drilling angle)
    step_mm: float = 0.5                # sampling step along the line
    entry_spacing_mm: float = 3.0       # spacing of candidate entry points on the scalp
    share_tolerance_mm: float = 3.0     # a target counts as "on" an electrode if within this distance of its axis
    electrode_cost: float = 1.0         # cost of one extra electrode (bleeding, infection, time)
    length_weight: float = 0.01         # per mm
    angle_weight: float = 0.02          # per degree
    unknown_weight: float = 2.0         # fraction of the path outside the vessel exam (not checked)
    contact_length_mm: float = 2.0      # DIXI-like electrode: 2 mm contacts, 3.5 mm pitch
    contact_pitch_mm: float = 3.5
    electrode_models: tuple = (5, 8, 10, 12, 15, 18)
    max_target_shift_mm: float = 4.0    # a region target may move this far (inside the region) away from vessels

def rule_for(name):
    for k in sorted(RULES, key=len, reverse=True):
        if name.startswith(k): return RULES[k]
    return None

class DistanceMaps:
    """Trilinear sampling of the package's distance maps at points given in RAS mm."""
    def __init__(self, maps):                       # maps: {name: (array, affine)}
        self.maps = {n: (np.asarray(a, np.float32), np.linalg.inv(aff)) for n, (a, aff) in maps.items()}

    @classmethod
    def from_package(cls, package, manifest):
        import os
        maps = {}
        for c in manifest["critical"]:
            if rule_for(c["name"]) is None: continue
            img = nib.load(os.path.join(package, c["distance_map"]))
            maps[c["name"]] = (np.asanyarray(img.dataobj), img.affine)
        return cls(maps)

    def sample(self, name, pts):
        arr, inv = self.maps[name]
        ijk = nib.affines.apply_affine(inv, pts.reshape(-1, 3)).T
        return ndimage.map_coordinates(arr, ijk, order=1, mode="constant", cval=np.nan).reshape(pts.shape[:-1])

@dataclass
class Trajectory:
    targets: list                   # names of targets on this electrode, deepest first
    entry: np.ndarray               # RAS mm, on the skin
    tip: np.ndarray                 # RAS mm, deepest point
    length_mm: float
    angle_deg: float
    min_dist: dict                  # structure -> minimum distance along the path [mm] (None = not imaged)
    risk: float
    warnings: list = field(default_factory=list)
    contacts: list = field(default_factory=list)
    electrode: str = ""

def evaluate_lines(entries, tip, maps, normals, s: Settings):
    """Score straight lines from many entries (N x 3) to one tip. Returns feasible mask, risk, details."""
    d = tip[None] - entries
    L = np.linalg.norm(d, axis=1); u = d / np.maximum(L, 1e-9)[:, None]
    cosang = np.clip(np.einsum("ij,ij->i", u, -normals), -1, 1)
    ang = np.degrees(np.arccos(cosang))
    ok = (L <= s.max_length_mm) & (ang <= s.max_angle_deg)
    n = int(np.ceil(s.max_length_mm / s.step_mm)) + 1
    t = np.arange(n) * s.step_mm                              # distance from the tip backwards
    risk = s.length_weight * L + s.angle_weight * ang
    mins = {}
    idx = np.where(ok)[0]
    if len(idx):
        pts = tip[None, None, :] - u[idx, None, :] * t[None, :, None]   # (k, n, 3), from tip outward
        inside = t[None, :] <= L[idx, None]
        for name in maps.maps:
            hard, scale, w, ignore_tip = rule_for(name)
            dist = maps.sample(name, pts)
            valid = inside & (t[None, :] >= ignore_tip)
            known = valid & ~np.isnan(dist)
            dmin = np.where(known, dist, np.inf).min(1)
            dmin = np.where(known.any(1), dmin, np.nan)
            mins[name] = np.full(len(entries), np.nan); mins[name][idx] = dmin
            if hard is not None:
                bad = np.nan_to_num(dmin, nan=np.inf) < hard
                ok[idx[bad]] = False
            r = w * np.exp(-np.nan_to_num(dmin, nan=np.inf) / scale)
            if name.startswith("vessels"):                    # path not covered by the vessel exam
                frac = 1 - known.sum(1) / np.maximum(valid.sum(1), 1)
                r = r + s.unknown_weight * frac
            risk[idx] += r
    return ok, risk, L, ang, mins

def place_contacts(tip, entry, brain_mask_fn, s: Settings):
    """Contacts from the tip outward while still inside the brain; choose the smallest electrode model that fits."""
    u = (entry - tip) / np.linalg.norm(entry - tip)
    centres = []
    k = 0
    while True:
        c = tip + u * (s.contact_length_mm / 2 + k * s.contact_pitch_mm)
        if np.linalg.norm(c - tip) > np.linalg.norm(entry - tip) or not brain_mask_fn(c): break
        centres.append(c); k += 1
    n_in = len(centres)
    model = next((m for m in s.electrode_models if m >= n_in), s.electrode_models[-1])
    return [c.round(2).tolist() for c in centres[:model]], f"{model} contacts ({n_in} inside the brain)"

def adjust_target(tip, region_pts, maps, s: Settings):
    """Targets are regions, not points: if the region centre is too close to a hard-limit structure,
    move the tip (inside the region, at most max_target_shift_mm) to the point with the largest safety margin."""
    def margin(P):
        m = np.full(len(P), np.inf)
        for name in maps.maps:
            hard, _, _, ignore_tip = rule_for(name)
            if hard is None or ignore_tip > 0: continue
            d = maps.sample(name, P); m = np.minimum(m, np.where(np.isnan(d), np.inf, d - hard))
        return m
    if margin(tip[None])[0] >= 1.0 or region_pts is None: return tip, 0.0
    P = region_pts[np.linalg.norm(region_pts - tip, axis=1) <= s.max_target_shift_mm]
    if not len(P): return tip, 0.0
    m = margin(P); score = np.minimum(m, 3.0) - 0.1 * np.linalg.norm(P - tip, axis=1)
    best = P[np.argmax(score)]
    return best, float(np.linalg.norm(best - tip))

def best_single(target_name, tip, entries, normals, maps, s, top=3):
    ok, risk, L, ang, mins = evaluate_lines(entries, tip, maps, normals, s)
    order = [i for i in np.argsort(risk) if ok[i]][:top]
    out = []
    for i in order:
        md = {k: (None if np.isnan(v[i]) else round(float(v[i]), 1)) for k, v in mins.items()}
        out.append(Trajectory([target_name], entries[i], tip, float(L[i]), float(ang[i]), md, float(risk[i])))
    return out

def exit_point(start, direction, head_fn, max_mm=150, step=0.5):
    """Walk from a point inside the head along a direction until leaving the head; return the last inside point."""
    p = start.copy(); last = None
    for k in range(int(max_mm / step)):
        q = start + direction * k * step
        if head_fn(q): last = q
        elif last is not None: return last
    return None

def shared_candidates(targets, maps, head_fn, scalp_pts, scalp_normals, entry_allowed, s):
    """Electrodes through 2 or 3 targets: the line through them, tip at the deepest one, extended to the skin."""
    from scipy.spatial import cKDTree
    tree = cKDTree(scalp_pts)
    names = list(targets)
    out = []
    for r in (2, 3):
        for combo in itertools.combinations(names, r):
            P = np.array([targets[n] for n in combo])
            c = P.mean(0)
            _, _, Vt = np.linalg.svd(P - c); u = Vt[0]
            if np.max(np.linalg.norm(np.cross(P - c, u), axis=1)) > s.share_tolerance_mm: continue
            for sign in (1, -1):                               # which end is the skin side
                v = u * sign
                proj = (P - c) @ v
                tip = c + v * proj.min()                       # deepest target projected on the axis
                e = exit_point(tip, v, head_fn)
                if e is None: continue
                dj, j = tree.query(e)
                if not entry_allowed[j] or dj > 2 * s.entry_spacing_mm: continue   # face, ear, neck ...
                ok, risk, L, ang, mins = evaluate_lines(e[None], tip, maps, scalp_normals[j][None], s)
                if not ok[0]: continue
                order = [combo[i] for i in np.argsort(proj)]
                md = {k: (None if np.isnan(m[0]) else round(float(m[0]), 1)) for k, m in mins.items()}
                out.append(Trajectory(order, e, tip, float(L[0]), float(ang[0]), md, float(risk[0])))
    return out

def choose(targets, candidates, s):
    """Pick electrodes so every target is covered at least once, minimising (#electrodes * cost + risk)."""
    from scipy.optimize import milp, LinearConstraint, Bounds
    names = list(targets)
    if not candidates: return [], names
    A = np.array([[1.0 if n in c.targets else 0.0 for c in candidates] for n in names])
    cost = np.array([s.electrode_cost + c.risk for c in candidates])
    coverable = A.sum(1) > 0
    res = milp(cost, constraints=LinearConstraint(A[coverable], lb=1, ub=np.inf),
               integrality=np.ones(len(candidates)), bounds=Bounds(0, 1))
    if not res.success: return [], names
    chosen = [c for c, x in zip(candidates, res.x) if x > 0.5]
    return chosen, [n for n, cv in zip(names, coverable) if not cv]

def plan(targets, maps, scalp_pts, scalp_normals, entry_allowed, head_fn, brain_fn, s=Settings()):
    """targets: {name: RAS mm}. Returns (chosen trajectories, uncovered target names, all candidates)."""
    E, N = scalp_pts[entry_allowed], scalp_normals[entry_allowed]
    cands = []
    for name, tip in targets.items():
        cands += best_single(name, np.asarray(tip, float), E, N, maps, s)
    cands += shared_candidates({k: np.asarray(v, float) for k, v in targets.items()}, maps, head_fn, scalp_pts, scalp_normals,
                               entry_allowed, s)
    chosen, uncovered = choose(targets, cands, s)
    for t in chosen:
        t.contacts, t.electrode = place_contacts(t.tip, t.entry, brain_fn, s)
        for k, v in t.min_dist.items():
            rule = rule_for(k)
            if v is not None and v < rule[1] and rule[0] is None: t.warnings.append(f"{k}: {v} mm")
        if t.min_dist.get("vessels") is None: t.warnings.append("vessels not imaged along this path")
    return chosen, uncovered, cands
