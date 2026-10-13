"""
planner.py - curved path planning for a continuum robot.

For one ordered list of targets the planner
  1. finds a coarse collision-free route on a grid (Dijkstra / minimum-cost path, skimage.graph.MCP):
     cheap where the brain is far from no-go zones, impassable inside them;
  2. turns it into a smooth robot path: a straight entry part (through skin and bone) followed by a cubic
     spline through the targets, and optimises the spline so that it
       - keeps the robot body out of every no-go zone (hard),
       - never bends tighter than the robot's minimum bend radius (hard),
       - respects the entry angle, total turning and maximum length (hard),
       - is short, sweeping (low curvature) and far from soft zones (cost);
  3. checks the result against all hard limits; a path that fails any of them is rejected.

Several targets: every target alone, plus ordered groups of 2-3 nearby targets on one path, are planned;
an integer program then picks the cheapest set of paths covering all targets
(cost = path cost + insertion_cost_mm per insertion), so the program decides itself whether targets
share a path.
"""
import itertools, time
from dataclasses import dataclass, field
import numpy as np
from scipy import ndimage
from scipy.interpolate import CubicSpline
from scipy.optimize import minimize
from skimage.graph import MCP_Geometric

@dataclass
class PathResult:
    targets: list                    # target names in the order the robot reaches them
    entry: np.ndarray                # skin point, RAS mm
    points: np.ndarray               # sampled path (N x 3), entry -> last target
    feasible: bool
    cost: float
    length_mm: float
    min_radius_mm: float
    entry_angle_deg: float
    total_turn_deg: float
    min_clearance_mm: dict = field(default_factory=dict)   # zone -> closest approach of the robot SURFACE
    problems: list = field(default_factory=list)

class Planner:
    def __init__(self, patient, cfg, log=print, progress=None):
        self.p, self.cfg, self.log, self.progress = patient, cfg, log, progress or (lambda f, msg="": None)
        self.robot, self.pl = cfg["robot"], cfg["planning"]
        self._build_search_grid()
        self._build_entries()
        self.mcp = {}

    # ------------------------------------------------------------------ coarse grid
    def _build_search_grid(self):
        p, g = self.p, self.pl["search_grid_mm"]
        f = p.vox / g                                             # zoom factors
        zoom = lambda a, order: ndimage.zoom(a, f, order=order)
        strict, ign, out = zoom(p.C_strict.data, 1), zoom(p.C_ignorable.data, 1), zoom(p.C_outside.data, 1)
        head = zoom(p.head.astype(np.uint8), 0) > 0
        soft = zoom(p.soft.data, 1)
        clear = np.minimum(strict, ign)
        cost = 1.0 + soft + 3.0 * np.exp(-np.clip(clear, 0, None) / 2.0)
        cost = np.where(out > 0, cost, 2.5)                       # outside the brain (scalp, bone, CSF): only to get in
        cost[(clear <= 0) | ~head] = np.inf
        self.g_cost, self.g_ign_free = cost, (strict > 0) & head  # g_ign_free: passable if ignorable zones are skipped
        # ndimage.zoom maps output index o to input index o * (n_in - 1) / (n_out - 1)
        sc = (np.array(p.shape) - 1) / (np.array(cost.shape) - 1)
        A = p.affine.copy(); A[:3, :3] = p.affine[:3, :3] * sc[None, :]
        self.g_aff, self.g_inv = A, np.linalg.inv(A)

    def g_idx(self, pt):
        i = np.round(self.g_inv[:3, :3] @ pt + self.g_inv[:3, 3]).astype(int)
        return tuple(np.clip(i, 0, np.array(self.g_cost.shape) - 1))

    def g_mm(self, idx):
        """Grid index -> RAS mm. idx: (3,) or (3, N)."""
        idx = np.asarray(idx, float)
        return self.g_aff[:3, :3] @ idx + (self.g_aff[:3, 3:4] if idx.ndim == 2 else self.g_aff[:3, 3])

    # ------------------------------------------------------------------ entry points on the skin
    def _build_entries(self):
        p, g = self.p, self.pl["search_grid_mm"]
        head = ndimage.zoom(p.head.astype(np.uint8), p.vox / g, order=0) > 0
        surf = head & ~ndimage.binary_erosion(head)
        idx = np.argwhere(surf)
        sm = ndimage.gaussian_filter(head.astype(np.float32), 2.0)
        grad = np.stack(np.gradient(sm), -1)[tuple(idx.T)]
        n = -grad @ self.g_aff[:3, :3].T                           # outward normal in mm space
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        pts = self.g_mm(idx.T).T
        c, F = p.frame
        q = (pts - c) @ F.T
        ok = self._entry_zone(q)
        self.entry_idx, self.entry_pts, self.entry_n = idx[ok], pts[ok], n[ok]
        self.log(f"  {ok.sum()} allowed entry points on the skin")

    def _entry_zone(self, q):
        z, lm = self.cfg.get("entry_zone", {}), self.p.landmarks_q()
        ok = np.ones(len(q), bool)
        if not lm:
            self.p.warnings.append("no headset landmarks: entry zone = upper half of the head only")
            return q[:, 2] > np.percentile(q[:, 2], 50)
        n = lm.get("nasion")
        if n is not None:
            if z.get("exclude_face", True): ok &= ~((q[:, 1] > n[1] - 35) & (q[:, 2] < n[2] + 15))
            if z.get("exclude_frontal_sinus", True):
                ok &= ~((np.abs(q[:, 0] - n[0]) < 25) & (q[:, 2] < n[2] + 40) & (q[:, 1] > n[1] - 40))
            ok &= np.abs(q[:, 0] - n[0]) > z.get("exclude_midline_mm", 15)
        trag = [lm[k] for k in ("left_tragus", "right_tragus", "left_preauricular", "right_preauricular") if k in lm]
        if trag:
            ok &= q[:, 2] > max(t[2] for t in trag) + z.get("min_height_above_tragus_mm", 5)
            for t in trag: ok &= np.linalg.norm(q - t, axis=1) > z.get("ear_exclusion_radius_mm", 30)
        return ok

    # ------------------------------------------------------------------ coarse routes
    def _mcp(self, name, tip):
        """Minimum-cost field from a target to every grid cell (one Dijkstra per target, cached)."""
        key = tuple(np.round(np.asarray(tip, float), 2))           # cache by position (names can change)
        if key in self.mcp: return self.mcp[key]
        cost = self.g_cost.copy()
        # cells close to the target are passable even inside zones that may touch targets (e.g. ventricles)
        r = self.pl["target_tolerance_mm"] / self.pl["search_grid_mm"]
        ti = np.array(self.g_idx(tip))
        lo, hi = np.maximum(ti - int(r) - 1, 0), np.minimum(ti + int(r) + 2, cost.shape)
        sub = np.indices(hi - lo).reshape(3, -1).T + lo
        near = sub[np.linalg.norm(sub - ti, axis=1) <= r]
        free = self.g_ign_free[tuple(near.T)]
        cost[tuple(near[free].T)] = np.minimum(np.nan_to_num(cost[tuple(near[free].T)], posinf=2.0), 2.0)
        m = MCP_Geometric(cost, fully_connected=True)
        cum, _ = m.find_costs([tuple(ti)])
        self.mcp[key] = (m, cum)
        return m, cum

    def _route(self, m, start_idx):
        """Grid route from start_idx to the target of MCP m, as RAS mm points."""
        path = m.traceback(tuple(start_idx))                       # target ... start
        return self.g_mm(np.array(path[::-1]).T).T

    # ------------------------------------------------------------------ smooth robot path
    def _spline(self, x, E, frame, waypoints, n_free):
        """Decode optimisation variables into the sampled robot path."""
        ax, ay = x[0], x[1]
        nin, e1, e2 = frame
        u = nin + ax * e1 + ay * e2; u /= np.linalg.norm(u)
        Ls = self.robot["straight_entry_mm"]
        S = E + u * Ls
        free = x[2:].reshape(-1, 3)
        pts, k = [S], 0
        for wp, nf in zip(waypoints, n_free):
            pts += list(free[k:k + nf]); k += nf; pts.append(wp)
        P = np.array(pts)
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        if np.any(seg < 1e-3): seg = np.maximum(seg, 1e-3)
        s = np.concatenate([[0], np.cumsum(seg)])
        if not np.isfinite(s[-1]) or s[-1] > 5 * self.robot["max_length_mm"]: return None   # diverged
        cs = CubicSpline(s, P, bc_type=((1, u), (2, np.zeros(3))))
        step = self.pl["sample_step_mm"]
        ss = np.linspace(0, s[-1], max(int(s[-1] / step) + 2, 4))
        r, d1, d2 = cs(ss), cs(ss, 1), cs(ss, 2)
        sp = np.linalg.norm(d1, axis=1)
        kappa = np.linalg.norm(np.cross(d1, d2), axis=1) / np.maximum(sp, 1e-6) ** 3
        straight = E + u[None] * np.linspace(0, Ls, max(int(Ls / step), 2))[:, None]
        dl = np.linalg.norm(np.diff(r, axis=0), axis=1)
        length = Ls + dl.sum()
        turn = np.sum(0.5 * (kappa[1:] + kappa[:-1]) * dl)
        return straight, r, kappa, dl, u, length, turn

    def _evaluate(self, x, E, frame, waypoints, n_free, targets_mm, detail=False, w=1.0):
        p, rb = self.p, self.robot
        sp = self._spline(x, E, frame, waypoints, n_free)
        if sp is None:
            if detail: return None
            return 1e9
        straight, r, kappa, dl, u, length, turn = sp
        tol = self.pl["target_tolerance_mm"]
        near = np.min(np.linalg.norm(r[:, None, :] - targets_mm[None], axis=2), axis=1) < tol
        c_str_s, c_ign_s = p.C_strict(straight), p.C_ignorable(straight)
        c_str, c_ign, c_out = p.C_strict(r), p.C_ignorable(r), p.C_outside(r)
        inside = np.where(c_out > 0)[0]
        first_in = inside[0] if len(inside) else len(r)            # once inside the brain, stay inside
        c_out_eff = np.where(np.arange(len(r)) >= first_in, c_out, 1e3)
        c_eff = np.minimum(c_str, np.where(near, 1e3, np.minimum(c_ign, c_out_eff)))
        c_ent = np.minimum(c_str_s, c_ign_s)
        b = 0.0 if detail else 0.5                                  # optimise with a small safety buffer
        viol = np.sum(np.clip(b - c_eff, 0, None) ** 2) + np.sum(np.clip(b - c_ent, 0, None) ** 2)
        kmax = (1.0 if detail else 0.93) / rb["min_bend_radius_mm"]
        kviol = np.sum((np.clip(kappa - kmax, 0, None) / kmax) ** 2)
        ang = np.degrees(np.arccos(np.clip(u @ frame[0], -1, 1)))
        aviol = max(0.0, ang - rb["max_entry_angle_deg"]) ** 2
        lviol = max(0.0, length - rb["max_length_mm"]) ** 2
        turn_deg = np.degrees(turn)
        tviol = max(0.0, turn_deg - rb["max_total_turn_deg"]) ** 2
        soft = np.sum(p.soft(r)[:-1] * dl) + np.sum(p.soft(straight)) * self.pl["sample_step_mm"]
        smooth = rb["min_bend_radius_mm"] ** 2 * np.sum(kappa[:-1] ** 2 * dl)  # prefers wide, sweeping curves
        cost = length + soft + self.pl.get("curvature_weight", 0.5) * smooth
        f = cost + w * (200.0 * viol + 500.0 * kviol + 5.0 * aviol + 2.0 * lviol + 1.0 * tviol)
        if not detail: return f
        return dict(cost=cost, viol=viol, kappa_max=kappa.max(), angle=ang, length=length, turn=turn_deg,
                    points=np.vstack([straight, r[1:]]), min_c=min(c_eff.min(), c_ent.min()))

    def plan_sequence(self, names, tips, n_entries=None):
        """Best feasible path that reaches the given targets in this order (or the best infeasible attempt)."""
        tips = [np.asarray(t, float) for t in tips]
        m0, cum0 = self._mcp(names[0], tips[0])
        ec = cum0[tuple(self.entry_idx.T)]
        order = np.argsort(ec)
        chosen = []                                                 # spread-out entry candidates
        for i in order:
            if not np.isfinite(ec[i]): break
            if all(np.linalg.norm(self.entry_pts[i] - self.entry_pts[j]) > 25 for j in chosen): chosen.append(i)
            if len(chosen) >= (n_entries or self.pl["entry_candidates"]): break
        legs = []                                                   # routes between consecutive targets
        for a in range(1, len(tips)):
            seg = tips[a - 1] + (tips[a] - tips[a - 1]) * np.linspace(0, 1, 30)[:, None]
            if (self.p.C_strict(seg) > 0).all():                    # straight connection is safe: use it
                legs.append(seg); continue
            m, cum = self._mcp(names[a], tips[a])
            if not np.isfinite(cum[self.g_idx(tips[a - 1])]): return None
            legs.append(self._route(m, self.g_idx(tips[a - 1])))
        starts = [(i, self._route(m0, self.entry_idx[i])) for i in chosen]
        straight = self._straight_entries(tips[0], 2)                # straight lines are also good starting guesses
        if len(tips) > 1:                                           # ... and continuing the line through the targets
            straight = self._straight_entries(tips[0], 2, along=tips[0] - tips[1]) + straight
        for i in straight:
            starts.append((i, self.entry_pts[i] + (tips[0] - self.entry_pts[i]) * np.linspace(0, 1, 40)[:, None]))
        best = None
        for i, route0 in starts:
            res = self._optimise(names, tips, self.entry_pts[i], self.entry_n[i], [route0] + legs)
            if res and (best is None or (res.feasible, -res.cost) > (best.feasible, -best.cost)): best = res
        return best

    def _straight_entries(self, tip, n, along=None):
        """Entries from which a straight line to the target is already safe (best = short + far from soft zones).
        along: preferred direction from the target back to the entry (within 30 deg), for paths through several targets."""
        E, N = self.entry_pts, self.entry_n
        d = tip - E; L = np.linalg.norm(d, axis=1); u = d / L[:, None]
        ang = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", u, -N), -1, 1)))
        keep = (L < self.robot["max_length_mm"]) & (ang < self.robot["max_entry_angle_deg"])
        if along is not None:
            a = along / np.linalg.norm(along); keep &= (-u @ a) > np.cos(np.radians(30))
        sel = np.where(keep)[0]
        if not len(sel): return []
        t = np.linspace(0, 1, 100)
        pts = E[sel, None] + d[sel, None] * t[None, :, None]
        near = np.linalg.norm(pts - tip, axis=2) < self.pl["target_tolerance_mm"]
        co = self.p.C_outside(pts); inside = np.maximum.accumulate(co > 0, axis=1)
        ok = ((self.p.C_strict(pts) > 0.3) & ((self.p.C_ignorable(pts) > 0.3) | near) & ((co > 0) | ~inside | near)).all(1)
        sel = sel[ok]
        if not len(sel): return []
        score = L[sel] + (self.p.soft(pts[ok]).sum(1) * L[sel] / 100)
        out = []
        for j in sel[np.argsort(score)]:
            if all(np.linalg.norm(E[j] - E[k]) > 20 for k in out): out.append(j)
            if len(out) >= n: break
        return out

    def _free_dirs(self, tip):
        """Directions from the target along which a 15 mm straight approach is collision-free (cached)."""
        key = tuple(np.round(tip, 2))
        if not hasattr(self, "_dir_cache"): self._dir_cache = {}
        if key not in self._dir_cache:
            rng = np.random.default_rng(0); D = rng.normal(size=(3000, 3)); D /= np.linalg.norm(D, axis=1, keepdims=True)
            t = np.linspace(self.pl["target_tolerance_mm"] + 0.5, 15, 24)
            pts = tip[None, None] + D[:, None] * t[None, :, None]
            ok = ((self.p.C_strict(pts) > 0.5) & (self.p.C_ignorable(pts) > 0.5) & (self.p.C_outside(pts) > 0)).all(1)
            self._dir_cache[key] = D[ok]
        return self._dir_cache[key]

    def _optimise(self, names, tips, E, nrm, routes):
        nin = -nrm
        a = np.cross(nin, [1, 0, 0]); a = a if np.linalg.norm(a) > 0.1 else np.cross(nin, [0, 1, 0])
        e1 = a / np.linalg.norm(a); e2 = np.cross(nin, e1); frame = (nin, e1, e2)
        Ls = self.robot["straight_entry_mm"]
        # initial entry direction: towards the coarse route ~ Ls + 10 mm in, clamped to the allowed angle
        r0 = routes[0]; d = np.linalg.norm(r0 - E, axis=1)
        aim = r0[min(np.searchsorted(d, Ls + 10), len(r0) - 1)] - E; aim /= np.linalg.norm(aim)
        t = np.tan(np.radians(min(np.degrees(np.arccos(np.clip(aim @ nin, -1, 1))), self.robot["max_entry_angle_deg"] * 0.8)))
        lat = aim - (aim @ nin) * nin; lat = lat / max(np.linalg.norm(lat), 1e-9)
        x0 = [t * (lat @ e1), t * (lat @ e2)]
        n_free, ctrl = [], []
        for k, route in enumerate(routes):
            if k == 0:                                               # skip the part covered by the straight entry
                route = route[np.linalg.norm(route - E, axis=1) > Ls]
            L = np.sum(np.linalg.norm(np.diff(route, axis=0), axis=1)) if len(route) > 1 else 0
            nf = int(np.clip(round(L / 20.0), 2, 5))      # one free point per ~20 mm of route
            if len(route) < 2: route = np.array([E + nin * Ls, tips[k]])
            cl = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(route, axis=0), axis=1))])
            leg = [route[np.argmin(np.abs(cl - cl[-1] * j / (nf + 1)))] for j in range(1, nf + 1)]
            # the last free point sets the final approach: put it on a collision-free straight line to the target,
            # as close as possible to the direction the coarse route comes from
            free = self._free_dirs(np.asarray(tips[k], float))
            if len(free) and cl[-1] > 12:
                back = route[np.argmin(np.abs(cl - (cl[-1] - 12)))] - tips[k]; back /= max(np.linalg.norm(back), 1e-9)
                v = free[np.argmax(free @ back)]
                leg[-1] = tips[k] + v * min(10.0, 0.5 * cl[-1])
            ctrl += leg
            n_free.append(nf)
        x0 = np.concatenate([x0, np.array(ctrl).ravel()])
        T = np.array(tips)
        x = x0
        try:                                                        # penalty continuation: soft first, then strict
            for w in (0.2, 1.0, 5.0, 25.0):
                fun = lambda x, w=w: self._evaluate(x, E, frame, tips, n_free, T, w=w)
                x = minimize(fun, x, method="L-BFGS-B", options=dict(maxiter=self.pl["optimizer_iterations"], eps=1e-3)).x
                d = self._evaluate(x, E, frame, tips, n_free, T, detail=True)
                if d is None: return None
                if w >= 1.0 and not self._result(names, E, d).problems: break
        except Exception as ex:
            self.log(f"    optimisation failed: {ex}"); return None
        return self._result(names, E, d)

    def _result(self, names, E, d):
        rb, problems = self.robot, []
        if d["min_c"] < -0.1: problems.append(f"enters a no-go zone ({-d['min_c']:.1f} mm too close)")
        if d["kappa_max"] > 1.03 / rb["min_bend_radius_mm"]:
            problems.append(f"bends too tightly (radius {1 / d['kappa_max']:.0f} mm)")
        if d["angle"] > rb["max_entry_angle_deg"] + 0.5: problems.append(f"entry angle {d['angle']:.0f} deg")
        if d["length"] > rb["max_length_mm"] + 0.5: problems.append(f"too long ({d['length']:.0f} mm)")
        if d["turn"] > rb["max_total_turn_deg"] + 1: problems.append(f"turns {d['turn']:.0f} deg in total")
        pts = d["points"]
        clear = {}
        r = rb["diameter_mm"] / 2
        for zname, fld in self.p.zone_dist.items():
            if zname in self.cfg.get("no_go", {}) and "outside_of" in self.cfg["no_go"][zname]: continue
            clear[zname] = round(float(fld(pts).min() - r), 1)
        return PathResult(list(names), E, pts, not problems, float(d["cost"]), float(d["length"]),
                          float(1 / max(d["kappa_max"], 1e-9)), float(d["angle"]), float(d["turn"]), clear, problems)

    # ------------------------------------------------------------------ target checks
    def check_target(self, tip):
        """List of strict no-go zones the target itself is too close to: [(zone, clearance_mm), ...]."""
        r, out = self.robot["diameter_mm"] / 2, []
        for name, z in self.cfg.get("no_go", {}).items():
            if name not in self.p.zone_dist or z.get("ignore_near_targets", False) or "outside_of" in z: continue
            c = float(self.p.zone_dist[name](np.asarray(tip, float)[None])[0]) - z["margin_mm"] - r
            if c < 0: out.append((name, round(c + z["margin_mm"] + r, 1)))
        return out

    def safe_nearby(self, tip, radius=5.0, step=0.5):
        """Closest point within radius that satisfies all strict zones (same brain region if possible)."""
        tip = np.asarray(tip, float)
        g = np.arange(-radius, radius + 1e-6, step)
        off = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
        off = off[np.linalg.norm(off, axis=1) <= radius]
        cand = tip + off
        ok = self.p.C_strict(cand) > 0.3
        lab = self.p.label_at(tip)
        same = np.array([self.p.label_at(c) == lab for c in cand]) if lab else np.ones(len(cand), bool)
        for m in (ok & same, ok):
            if m.any():
                c = cand[m]; return c[np.argmin(np.linalg.norm(c - tip, axis=1))]
        return None

    # ------------------------------------------------------------------ several targets
    def plan_all(self, targets):
        """targets: {name: RAS mm}. Returns (chosen paths, names not reachable, all evaluated candidates)."""
        t0 = time.time()
        P = {n: np.asarray(v, float) for n, v in targets.items()}
        self.target_problems = {}
        for n, v in P.items():
            bad = self.check_target(v)
            if bad:
                self.target_problems[n] = "target too close to " + ", ".join(f"{z} ({d} mm)" for z, d in bad)
                self.log(f"  {n}: {self.target_problems[n]} - move it or use 'Snap to safe point'")
        names = [n for n in P if n not in self.target_problems]
        cands = []
        seqs = [(n,) for n in names]
        kmax = int(self.pl["max_targets_per_path"])
        for k in range(2, min(kmax, len(names)) + 1):
            for perm in itertools.permutations(names, k):
                if all(np.linalg.norm(P[perm[i]] - P[perm[i + 1]]) <= self.pl["group_max_distance_mm"] for i in range(k - 1)):
                    seqs.append(perm)
        feasible_pairs = set()
        for j, seq in enumerate(seqs):
            if len(seq) == 3 and not ((seq[0], seq[1]) in feasible_pairs and (seq[1], seq[2]) in feasible_pairs): continue
            self.progress(j / len(seqs), f"planning {' -> '.join(seq)}")
            res = self.plan_sequence(seq, [P[n] for n in seq])
            if res is None: continue
            self.log(f"  {' -> '.join(seq)}: {'OK' if res.feasible else 'rejected: ' + '; '.join(res.problems)}"
                     f" (length {res.length_mm:.0f} mm, min radius {res.min_radius_mm:.0f} mm)")
            cands.append(res)
            if res.feasible and len(seq) == 2: feasible_pairs.add(seq)
        chosen, uncovered = self._select(names, [c for c in cands if c.feasible])
        uncovered = list(self.target_problems) + uncovered
        self.progress(1.0, f"done in {time.time() - t0:.0f} s")
        return chosen, uncovered, cands

    def _select(self, names, feas):
        from scipy.optimize import milp, LinearConstraint, Bounds
        if not feas: return [], names
        A = np.array([[1.0 if n in c.targets else 0.0 for c in feas] for n in names])
        cover = A.sum(1) > 0
        cost = np.array([c.cost + self.pl["insertion_cost_mm"] for c in feas])
        res = milp(cost, constraints=LinearConstraint(A[cover], lb=1, ub=np.inf), integrality=np.ones(len(feas)), bounds=Bounds(0, 1))
        chosen = [c for c, x in zip(feas, res.x) if x > 0.5] if res.success else []
        return chosen, [n for n, cv in zip(names, cover) if not cv]
