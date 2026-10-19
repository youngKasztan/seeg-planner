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
share a path. The number of groups grows fast with the number of targets, so groups are
  - skipped when they provably cannot beat separate paths (their length alone is already too long),
  - tried in the most promising order first (coarse route cost) and not re-tried once one order works,
  - planned only until time_limit_s; groups left over are skipped and reported in the log.
Planning can be stopped at any time (should_stop callback -> Cancelled).
"""
import itertools, time
from dataclasses import dataclass, field
import numpy as np
from scipy import ndimage
from scipy.interpolate import CubicSpline   # noqa: F401  (reference implementation, see clamped_spline)
from scipy.optimize import minimize
from skimage.graph import MCP_Geometric

def clamped_spline(s, P, u, ss):
    """Cubic spline through points P (n+1 x 3) at parameters s, first derivative u at the start and zero second
    derivative at the end; returns position, 1st and 2nd derivative at ss.
    Same result as scipy CubicSpline(s, P, bc_type=((1, u), (2, 0))) but ~5x faster for the few knots used here
    (the optimiser evaluates it ~10 000 times per path)."""
    n = len(s) - 1
    h = np.diff(s); dlt = np.diff(P, axis=0) / h[:, None]
    A = np.zeros((n + 1, n + 1)); B = np.empty((n + 1, 3))
    A[0, 0] = 1.0; B[0] = u                                         # clamped start: slope = u
    if n > 1:                                                       # continuity of the 2nd derivative
        i = np.arange(1, n)
        A[i, i - 1], A[i, i], A[i, i + 1] = h[1:], 2 * (h[:-1] + h[1:]), h[:-1]
        B[1:n] = 3 * (h[1:, None] * dlt[:-1] + h[:-1, None] * dlt[1:])
    A[n, n - 1], A[n, n] = 1.0, 2.0; B[n] = 3 * dlt[n - 1]           # natural end: 2nd derivative = 0
    m = np.linalg.solve(A, B)                                       # slopes at the knots
    c2 = (3 * dlt - 2 * m[:-1] - m[1:]) / h[:, None]
    c3 = (m[:-1] + m[1:] - 2 * dlt) / (h ** 2)[:, None]
    i = np.clip(np.searchsorted(s, ss, side="right") - 1, 0, n - 1)
    x = (ss - s[i])[:, None]
    r = P[i] + m[i] * x + c2[i] * x ** 2 + c3[i] * x ** 3
    d1 = m[i] + 2 * c2[i] * x + 3 * c3[i] * x ** 2
    d2 = 2 * c2[i] + 6 * c3[i] * x
    return r, d1, d2

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

class Cancelled(Exception):
    """Raised when the user stops the planning."""

class Planner:
    def __init__(self, patient, cfg, log=print, progress=None):
        self.p, self.cfg, self.log, self.progress = patient, cfg, log, progress or (lambda f, msg="": None)
        self.robot, self.pl = cfg["robot"], cfg["planning"]
        self.should_stop = lambda: False                             # set by the app (Stop button)
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
        u = nin + ax * e1 + ay * e2; u /= np.sqrt(u @ u)
        Ls = self.robot["straight_entry_mm"]
        S = E + u * Ls
        free = x[2:].reshape(-1, 3)
        pts, k = [S[None]], 0
        for wp, nf in zip(waypoints, n_free):
            pts += [free[k:k + nf], np.asarray(wp, float)[None]]; k += nf
        P = np.concatenate(pts)
        seg = np.sqrt((np.diff(P, axis=0) ** 2).sum(1))
        if np.any(seg < 1e-3): seg = np.maximum(seg, 1e-3)
        s = np.concatenate([[0], np.cumsum(seg)])
        if not np.isfinite(s[-1]) or s[-1] > 5 * self.robot["max_length_mm"]: return None   # diverged
        step = self.pl["sample_step_mm"]
        ss = np.linspace(0, s[-1], max(int(s[-1] / step) + 2, 4))
        r, d1, d2 = clamped_spline(s, P, u, ss)
        sp = np.sqrt((d1 ** 2).sum(1))
        cr = d1[:, [1, 2, 0]] * d2[:, [2, 0, 1]] - d1[:, [2, 0, 1]] * d2[:, [1, 2, 0]]   # cross product
        kappa = np.sqrt((cr ** 2).sum(1)) / np.maximum(sp, 1e-6) ** 3
        straight = E + u[None] * np.linspace(0, Ls, max(int(Ls / step), 2))[:, None]
        dl = np.sqrt((np.diff(r, axis=0) ** 2).sum(1))
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
        ns = len(straight)
        st, ig, ou, so = p.sample(np.vstack([straight, r]))         # one coordinate transform for all fields
        c_str_s, c_ign_s, soft_s = st[:ns], ig[:ns], so[:ns]
        c_str, c_ign, c_out, soft_r = st[ns:], ig[ns:], ou[ns:], so[ns:]
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
        soft = np.sum(soft_r[:-1] * dl) + np.sum(soft_s) * self.pl["sample_step_mm"]
        smooth = rb["min_bend_radius_mm"] ** 2 * np.sum(kappa[:-1] ** 2 * dl)  # prefers wide, sweeping curves
        cost = length + soft + self.pl.get("curvature_weight", 0.5) * smooth
        f = cost + w * (200.0 * viol + 500.0 * kviol + 5.0 * aviol + 2.0 * lviol + 1.0 * tviol)
        if not detail: return f
        return dict(cost=cost, viol=viol, kappa_max=kappa.max(), angle=ang, length=length, turn=turn_deg,
                    points=np.vstack([straight, r[1:]]), min_c=min(c_eff.min(), c_ent.min()))

    def plan_sequence(self, names, tips, n_entries=None, n_straight=2, first_feasible=False):
        """Best feasible path that reaches the given targets in this order (or the best infeasible attempt).
        first_feasible: stop at the first start that gives a feasible path (used for groups, to save time)."""
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
        starts = []
        if len(tips) > 1 and np.linalg.norm(tips[0] - tips[1]) > 1e-6:   # continuing the line through the targets first
            for i in self._straight_entries(tips[0], n_straight, along=tips[0] - tips[1]):
                starts.append((i, self.entry_pts[i] + (tips[0] - self.entry_pts[i]) * np.linspace(0, 1, 40)[:, None]))
        used = {i for i, _ in starts}
        starts += [(i, self._route(m0, self.entry_idx[i])) for i in chosen]
        for i in self._straight_entries(tips[0], n_straight):         # straight lines are also good starting guesses
            if i in used: continue                                  # same straight line already tried
            starts.append((i, self.entry_pts[i] + (tips[0] - self.entry_pts[i]) * np.linspace(0, 1, 40)[:, None]))
        best, self.last_alternatives = None, []
        for i, route0 in starts:
            self._check_stop()
            res = self._optimise(names, tips, self.entry_pts[i], self.entry_n[i], [route0] + legs)
            if res and (best is None or (res.feasible, -res.cost) > (best.feasible, -best.cost)): best = res
            if res and res.feasible: self.last_alternatives.append(res)
            if first_feasible and best is not None and best.feasible: break
        return best

    def alternatives(self, k=3, min_entry_gap_mm=15.0):
        """Up to k feasible results of the last plan_sequence, cheapest first, with entries at least
        min_entry_gap_mm apart (used when the best path collides with the path to another target)."""
        out = []
        for r in sorted(self.last_alternatives, key=lambda r: r.cost):
            if all(np.linalg.norm(r.entry - o.entry) >= min_entry_gap_mm for o in out): out.append(r)
            if len(out) >= k: break
        return out

    def _check_stop(self):
        if self.should_stop(): raise Cancelled()

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

    def _arrival_dirs(self, tip):
        """Unit vectors v such that the robot can arrive at tip coming from tip + v (8 mm chord collision-free,
        with 1 mm tolerance for the bend of the real curve). Cached."""
        key = tuple(np.round(tip, 2))
        if not hasattr(self, "_arr_cache"): self._arr_cache = {}
        if key not in self._arr_cache:
            rng = np.random.default_rng(1); D = rng.normal(size=(6000, 3)); D /= np.linalg.norm(D, axis=1, keepdims=True)
            t = np.linspace(self.pl["target_tolerance_mm"] + 0.5, 8.0, 12)
            pts = tip[None, None] + D[:, None] * t[None, :, None]
            ok = ((self.p.C_strict(pts) > -1.0) & (self.p.C_ignorable(pts) > -1.0)).all(1)   # may come from outside the brain
            self._arr_cache[key] = D[ok]
        return self._arr_cache[key]

    def order_possible(self, a, b):
        """Necessary condition for a path that passes target a and then reaches target b.
        A curve that leaves a with tangent t and has curvature <= 1/R reaches a point at distance d only if the
        angle between t and the chord a->b is <= asin(d / 2R) (the circular arc is the extreme case). The tangent
        at a is the direction the robot arrives from, which must be collision-free (_arrival_dirs). 10 deg of
        slack covers the chord approximation and the direction sampling."""
        a, b = np.asarray(a, float), np.asarray(b, float)
        d = np.linalg.norm(b - a)
        if d < 1e-6: return True
        R = self.robot["min_bend_radius_mm"] / 1.03                 # the same tolerance as the final check
        theta = np.degrees(np.arcsin(min(1.0, d / (2 * R)))) + 10.0
        V = self._arrival_dirs(a)
        if not len(V): return False
        ang = np.degrees(np.arccos(np.clip((-V) @ ((b - a) / d), -1, 1)))
        return bool(ang.min() <= theta)

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
        calls = [0]
        def fun(x, w):
            calls[0] += 1
            if calls[0] % 200 == 0: self._check_stop()               # lets the Stop button interrupt an optimisation
            return self._evaluate(x, E, frame, tips, n_free, T, w=w)
        try:                                                        # penalty continuation: soft first, then strict
            for w in (0.2, 1.0, 5.0, 25.0):
                opt = minimize(fun, x, args=(w,), method="L-BFGS-B",
                               options=dict(maxiter=self.pl["optimizer_iterations"], eps=1e-3))
                x = opt.x
                d = self._evaluate(x, E, frame, tips, n_free, T, detail=True)
                if d is None: return None
                if w >= 1.0 and not self._result(names, E, d).problems: break
                # the line search could not move at all with this penalty weight: a heavier one starts from the
                # same point and gets stuck the same way (measured on IXI057), so stop here and save the time
                if w >= 1.0 and opt.nit == 0: break
        except Cancelled:
            raise
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
        limit = float(self.pl.get("time_limit_s", 120))
        P = {n: np.asarray(v, float) for n, v in targets.items()}
        self.target_problems = {}
        for n, v in P.items():
            bad = self.check_target(v)
            if bad:
                self.target_problems[n] = "target too close to " + ", ".join(f"{z} ({d} mm)" for z, d in bad)
                self.log(f"  {n}: {self.target_problems[n]} - move it or use 'Snap to safe point'")
        names = [n for n in P if n not in self.target_problems]
        self.progress(0.0, "preparing the route search")
        groups = self._candidate_groups(names, P)
        n_jobs, done = max(len(names) + len(groups), 1), 0
        cands, single = [], {}

        # 1. every target alone (always planned, full search)
        for n in names:
            self._check_stop()
            self.progress(done / n_jobs, f"planning {n}  ({time.time() - t0:.0f} s)")
            res = self.plan_sequence((n,), [P[n]])
            done += 1
            if res is None: self.log(f"  {n}: no route to the skin"); continue
            self._log_result((n,), res)
            if res.feasible:
                single[n] = res
                cands += self.alternatives()                        # best path + other entries, in case of collisions
            else: cands.append(res)

        # 2. groups of 2-3 targets on one path, most promising first, within the time limit
        ins, skipped_time, pruned, stopped = self.pl["insertion_cost_mm"], 0, 0, False
        for gi, (members, orders) in enumerate(groups):
            done = len(names) + gi
            if self.should_stop(): stopped = True; break
            pairs_ok = len(members) == 2 or all(frozenset(pq) in self._feasible_sets(cands)
                                                for pq in itertools.combinations(members, 2))
            if not pairs_ok: continue                               # a triple only makes sense if its pairs work
            if time.time() - t0 > limit: skipped_time += 1; continue
            if self._cannot_win(members, orders, P, cands, single, ins): pruned += 1; continue
            try:
                for seq in orders:                                  # cheapest coarse route first
                    if time.time() - t0 > limit: break
                    self.progress(done / n_jobs, f"planning {' -> '.join(seq)}  ({time.time() - t0:.0f} s)")
                    res = self.plan_sequence(seq, [P[n] for n in seq], first_feasible=True)
                    if res is None: continue
                    self._log_result(seq, res); cands.append(res)
                    if res.feasible: break                          # other orders of the same targets are not tried
            except Cancelled:
                stopped = True; break
        if stopped: self.log("  stopped by the user - using the paths found so far")
        if pruned: self.log(f"  {pruned} group(s) skipped: they cannot be shorter than separate paths")
        if skipped_time:
            self.log(f"  time limit {limit:.0f} s reached: {skipped_time} group(s) not tried "
                     f"(raise time_limit_s in robot.toml to try them)")
        chosen, uncovered = self._select(names, [c for c in cands if c.feasible])
        uncovered = list(self.target_problems) + uncovered
        for n, why in self.collision_notes.items():
            self.target_problems[n] = why; self.log(f"  {n}: not used - {why}")
        self.progress(1.0, f"done in {time.time() - t0:.0f} s")
        return chosen, uncovered, cands

    def _log_result(self, seq, res):
        self.log(f"  {' -> '.join(seq)}: {'OK' if res.feasible else 'rejected: ' + '; '.join(res.problems)}"
                 f" (length {res.length_mm:.0f} mm, min radius {res.min_radius_mm:.0f} mm)")

    @staticmethod
    def _feasible_sets(cands):
        return {frozenset(c.targets) for c in cands if c.feasible}

    def _coarse_cost(self, seq, P):
        """Cost of the coarse grid routes skin -> seq[0] -> seq[1] ... (inf if a leg has no route)."""
        _, cum0 = self._mcp(seq[0], P[seq[0]])
        c = float(np.min(cum0[tuple(self.entry_idx.T)])) if len(self.entry_idx) else np.inf
        for a in range(1, len(seq)):
            _, cum = self._mcp(seq[a], P[seq[a]])
            c += float(cum[self.g_idx(P[seq[a - 1]])])
        return c

    def _candidate_groups(self, names, P):
        """[(members, orders sorted by coarse cost)], groups sorted by their best coarse cost."""
        kmax, dmax = int(self.pl["max_targets_per_path"]), self.pl["group_max_distance_mm"]
        out = []
        for k in range(2, min(kmax, len(names)) + 1):
            for members in itertools.combinations(names, k):
                orders = [seq for seq in itertools.permutations(members)
                          if all(np.linalg.norm(P[seq[i]] - P[seq[i + 1]]) <= dmax and
                                 self.order_possible(P[seq[i]], P[seq[i + 1]]) for i in range(k - 1))]
                if not orders: continue
                costs = [self._coarse_cost(seq, P) for seq in orders]
                orders = [o for _, o in sorted(zip(costs, orders), key=lambda t: t[0])]
                out.append((members, orders, k, min(costs)))
        out.sort(key=lambda g: (g[2], g[3]))                          # pairs before triples, then by promise
        return [(m, o) for m, o, _, _ in out]

    def _cannot_win(self, members, orders, P, cands, single, ins):
        """True if any path through these targets is provably at least as expensive as covering them with paths
        already found (path cost >= path length >= distance from the nearest allowed entry + target-to-target)."""
        if not all(n in single for n in members): return False
        best_cover = sum(single[n].cost for n in members) + ins * len(members)
        for c in cands:                                             # e.g. a pair + the third target alone
            if c.feasible and 1 < len(c.targets) < len(members) and set(c.targets) <= set(members):
                rest = [n for n in members if n not in c.targets]
                best_cover = min(best_cover, c.cost + ins + sum(single[n].cost + ins for n in rest))
        lb = min(float(np.min(np.linalg.norm(self.entry_pts - P[seq[0]], axis=1))) +
                 sum(np.linalg.norm(P[seq[i]] - P[seq[i + 1]]) for i in range(len(seq) - 1)) for seq in orders)
        return lb + ins >= best_cover

    def conflicts(self, feas):
        """Pairs (i, j) of paths that must not be used together: their bodies come closer than
        min_path_distance_mm, or their skin entries are closer than min_entry_distance_mm."""
        from scipy.spatial import cKDTree
        gap = self.robot["diameter_mm"] + float(self.pl.get("min_path_distance_mm", 2.0))
        egap = float(self.pl.get("min_entry_distance_mm", 10.0))
        trees = [cKDTree(c.points) for c in feas]
        out = []
        for i, j in itertools.combinations(range(len(feas)), 2):
            a, b = feas[i], feas[j]
            if set(a.targets) & set(b.targets): out.append((i, j)); continue   # same target twice: never both
            d = trees[i].query(b.points, k=1)[0].min()
            if d < gap or np.linalg.norm(a.entry - b.entry) < egap: out.append((i, j))
        return out

    def _select(self, names, feas):
        """Cheapest set of non-colliding paths that reaches as many targets as possible."""
        from scipy.optimize import milp, LinearConstraint, Bounds
        self.collision_notes = {}
        if not feas: return [], list(names)
        nc, nt = len(feas), len(names)
        A = np.array([[1.0 if n in c.targets else 0.0 for c in feas] for n in names])
        big = 1e6                                                   # cost of leaving a target without a path
        cost = np.concatenate([[c.cost + self.pl["insertion_cost_mm"] for c in feas], np.full(nt, big)])
        rows, lb, ub = [np.hstack([A, np.eye(nt)])], [np.ones(nt)], [np.full(nt, np.inf)]   # path or "not reached"
        conf = self.conflicts(feas)
        if conf:
            C = np.zeros((len(conf), nc + nt))
            for r, (i, j) in enumerate(conf): C[r, i] = C[r, j] = 1.0
            rows.append(C); lb.append(np.zeros(len(conf))); ub.append(np.ones(len(conf)))
        res = milp(cost, constraints=LinearConstraint(np.vstack(rows), np.concatenate(lb), np.concatenate(ub)),
                   integrality=np.ones(nc + nt), bounds=Bounds(0, 1))
        if not res.success: return [], list(names)
        chosen = [c for c, x in zip(feas, res.x[:nc]) if x > 0.5]
        covered = {n for c in chosen for n in c.targets}
        uncovered = [n for n in names if n not in covered]
        # explain targets lost to collisions (they had a path, but it clashes with a chosen one)
        for n in uncovered:
            if A[names.index(n)].any():
                self.collision_notes[n] = "its paths come too close to another chosen path"
        return chosen, uncovered
