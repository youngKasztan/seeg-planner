"""
planner.py - path planning for a concentric-tube continuum robot (shape: robot_model.py).

The robot is pushed in straight first (any length), then two pre-curved tubes come out: arc 1 and arc 2,
each a circular arc of at most 35 mm with its own minimum radius and its own bending plane. For one ordered
list of targets the planner
  1. finds a coarse collision-free route on a grid (Dijkstra / minimum-cost path, skimage.graph.MCP):
     cheap where the brain is far from no-go zones, impassable inside them;
  2. fits the robot shape to that route and optimises it (Powell, penalty continuation). The shape is built
     backwards from the last target (tip direction -> arc 2 -> arc 1 -> straight back to the skin), so the tip
     is exactly on the target; the variables are the tip direction and length, curvature and plane of each arc.
     Hard limits: no-go clearance, arcs inside the brain, entry on the allowed skin zone, entry angle, straight
     part >= min_straight_mm, total length, earlier targets within target_pass_mm of the robot.
     Cost: length + soft zones + curvature_weight * bending (wide arcs preferred);
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
import warnings
from scipy.optimize import minimize, OptimizeWarning
warnings.filterwarnings("ignore", category=OptimizeWarning)   # Powell: start point on a bound is fine
from skimage.graph import MCP_Geometric
from scipy.spatial import cKDTree

import robot_model
from patient import Field

@dataclass
class PathResult:
    targets: list                    # target names in the order the robot reaches them
    entry: np.ndarray                # skin point, RAS mm
    points: np.ndarray               # sampled path (N x 3), entry -> last target
    feasible: bool
    cost: float
    length_mm: float
    min_radius_mm: float             # tightest arc used (1e9 = straight only)
    entry_angle_deg: float
    total_turn_deg: float            # arc 1 + arc 2 bending angle
    min_clearance_mm: dict = field(default_factory=dict)   # zone -> closest approach of the robot SURFACE
    problems: list = field(default_factory=list)
    labels: np.ndarray = None        # per point: 0 = straight, 1 = arc 1, 2 = arc 2 (robot_model)
    shape: dict = field(default_factory=dict)              # straight length, arc lengths, radii and planes

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
        self.head_f = Field(self.p.head.astype(np.float32), self.p.affine, 0.0)   # where the straight part leaves the head
        self.entry_tree = cKDTree(self.entry_pts) if len(self.entry_pts) else cKDTree(np.zeros((1, 3)) + 1e6)

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

    # ------------------------------------------------------------------ robot shape: straight + arc 1 + arc 2
    def _shape(self, x, tip, frame, via=None):
        """Decode x = [a, b, L2, k2, phi2, L1, k1, phi1] into the robot shape that ends exactly at tip.
        frame = (d0, e1, e2): the back direction at the tip is d0 + a e1 + b e2 (normalised).
        via (a target before the tip): arc 2 is the circular arc from the tip that passes exactly through via
        (fixed by the tip direction), so x = [a, b, L1, k1, phi1]; arc 2 beyond the robot's limits is reported
        in 'over' and penalised."""
        d0, e1, e2 = frame
        v = d0 + x[0] * e1 + x[1] * e2; v = v / np.linalg.norm(v)
        (L1max, k1max), (L2max, k2max) = robot_model.arc_limits(self.robot)
        step = self.pl["sample_step_mm"]
        over = 0.0
        if via is None:
            L2, k2, phi2 = np.clip(x[2], 0, L2max), np.clip(x[3], 0, k2max), x[4]
            L1, k1, phi1 = np.clip(x[5], 0, L1max), np.clip(x[6], 0, k1max), x[7]
        else:
            w = np.asarray(via, float) - tip; c = float(np.linalg.norm(w))
            cth = float(np.clip(v @ w / c, -1, 1)); th = float(np.arccos(cth))
            if th < 1e-4: k2, L2, phi2 = 0.0, c, 0.0
            else:
                perp = w - cth * c * v
                Rr = c / (2 * np.sin(th)); k2, L2 = 1.0 / Rr, 2 * th * Rr
                phi2 = self._phi_for(v, perp / np.linalg.norm(perp))
            over = max(0.0, k2 / k2max - 1.0) * 10.0 + max(0.0, L2 - L2max) / 5.0
            if L2 > 3 * (L1max + L2max): return None
            L1, k1, phi1 = np.clip(x[2], 0, L1max), np.clip(x[3], 0, k1max), x[4]
        p2, v1 = robot_model.arc(np.asarray(tip, float), v, k2, L2, phi2, step)
        p1, vb = robot_model.arc(p2[-1], v1, k1, L1, phi1, step)
        P0 = p1[-1]
        # straight part: from the start of arc 1 straight back until it leaves the head = the skin entry
        t = np.arange(0.0, self.robot["max_length_mm"] + 1.0, 0.5)
        h = self.head_f(P0 + np.outer(t, vb))
        out = np.where(h < 0.5)[0]
        if not len(out): return None                                   # never leaves the head: far too long
        i = out[0]
        if i == 0: L0 = 0.0
        else: L0 = t[i - 1] + (h[i - 1] - 0.5) / max(h[i - 1] - h[i], 1e-9) * (t[i] - t[i - 1])
        entry = P0 + vb * L0
        pts, lab = robot_model.assemble(entry, P0, p1, p2, step)
        return dict(points=pts, labels=lab, entry=entry, u=-vb, L=(L0, L1, L2), k=(k1, k2), phi=(phi1, phi2), over=over)

    def _evaluate(self, x, tip, frame, targets_mm, detail=False, w=1.0, via=None):
        p, rb = self.p, self.robot
        sh = self._shape(x, tip, frame, via)
        if sh is None: return None if detail else 1e9
        r, lab = sh["points"], sh["labels"]
        L0, L1, L2 = sh["L"]; k1, k2 = sh["k"]
        tol = self.pl["target_tolerance_mm"]
        near = np.min(np.linalg.norm(r[:, None, :] - targets_mm[None], axis=2), axis=1) < tol
        c_str, c_ign, c_out, soft = p.sample(r)
        inside = np.where(c_out > 0)[0]
        first_in = inside[0] if len(inside) else len(r)               # once inside the brain, stay inside;
        must_in = (np.arange(len(r)) >= first_in) | (lab > 0)          # the arcs are always inside the brain
        c_out_eff = np.where(must_in, c_out, 1e3)
        c_eff = np.minimum(c_str, np.where(near, 1e3, np.minimum(c_ign, c_out_eff)))
        b = 0.0 if detail else 0.5                                    # optimise with a small safety buffer
        viol = np.sum(np.clip(b - c_eff, 0, None) ** 2)
        # entry: on an allowed part of the skin (nearest allowed entry point), angle to the skin normal
        de, j = self.entry_tree.query(sh["entry"])
        eviol = max(0.0, de - 1.5 * self.pl["search_grid_mm"]) ** 2
        ang = np.degrees(np.arccos(np.clip(sh["u"] @ -self.entry_n[j], -1, 1)))
        aviol = max(0.0, ang - rb["max_entry_angle_deg"]) ** 2
        length = L0 + L1 + L2
        lviol = max(0.0, length - rb["max_length_mm"]) ** 2
        sviol = max(0.0, robot_model.min_straight(rb) - L0) ** 2
        # earlier targets of the sequence must lie on the robot
        miss = [float(np.min(np.linalg.norm(r - t, axis=1))) for t in targets_mm[:-1]]
        mviol = sum(max(0.0, m - 0.3) ** 2 for m in miss)
        dl = np.linalg.norm(np.diff(r, axis=0), axis=1)
        soft_cost = np.sum(0.5 * (soft[1:] + soft[:-1]) * dl)
        R1 = 1.0 / robot_model.arc_limits(rb)[0][1]
        bend = R1 ** 2 * (k1 ** 2 * L1 + k2 ** 2 * L2)                 # prefers wide arcs (large radius)
        cost = length + soft_cost + self.pl.get("curvature_weight", 0.5) * bend
        oviol = sh["over"] ** 2                                        # arc 2 to the 'via' target beyond the limits
        f = cost + w * (200.0 * viol + 20.0 * eviol + 5.0 * aviol + 2.0 * lviol + 5.0 * sviol + 200.0 * mviol + 200.0 * oviol)
        if not detail: return f
        return dict(cost=cost, viol=viol, angle=ang, length=length, points=r, labels=lab, entry=sh["entry"],
                    entry_dist=de, L=sh["L"], k=sh["k"], phi=sh["phi"], miss=miss, min_c=float(c_eff.min()))

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
        if len(tips) > 1:                                           # several targets: exact arc shapes first
            for init in self._arc_inits(tips):
                self._check_stop()
                res = self._optimise(names, tips, None, None, None, init=init)
                if res and (best is None or (res.feasible, -res.cost) > (best.feasible, -best.cost)): best = res
                if res and res.feasible: self.last_alternatives.append(res)
                if first_feasible and best is not None and best.feasible: return best
            # P = second-to-last target, where arc 1 meets arc 2: the robot may already be curved when it passes P
            mR, cumR = (self._mcp(names[-2], tips[-2]) if len(tips) == 2 else (m0, cum0))
            ecR = cumR[tuple(self.entry_idx.T)]; viaE = []
            for i in np.argsort(ecR):
                if not np.isfinite(ecR[i]): break
                if all(np.linalg.norm(self.entry_pts[i] - self.entry_pts[j]) > 25 for j in viaE): viaE.append(i)
                if len(viaE) >= 2: break
            for i in viaE:
                self._check_stop()
                route = np.vstack([self._route(mR, self.entry_idx[i])] + legs[:-1])   # skin -> ... -> P
                res = self._optimise_via(names, tips, self.entry_pts[i], route)
                if res and (best is None or (res.feasible, -res.cost) > (best.feasible, -best.cost)): best = res
                if res and res.feasible: self.last_alternatives.append(res)
                if first_feasible and best is not None and best.feasible: return best
        for i, route0 in starts:
            self._check_stop()
            res = self._optimise(names, tips, self.entry_pts[i], self.entry_n[i], [route0] + legs)
            if res and (best is None or (res.feasible, -res.cost) > (best.feasible, -best.cost)): best = res
            if res and res.feasible: self.last_alternatives.append(res)
            if first_feasible and best is not None and best.feasible: break
        return best

    @staticmethod
    def _phi_for(v, b):
        """Plane angle phi (robot_model.arc) that makes an arc starting with tangent v bend towards b."""
        n0 = robot_model._perp(v)
        return float(np.arctan2(b @ np.cross(v, n0), b @ n0))

    def _arc_inits(self, tips, n=6, keep=3):
        """Exact starting shapes for one path through several targets: a straight line through the earlier targets
        (pushed in from an allowed entry, or along the line of the first two targets for three), then one circular
        arc - split over arc 2 and arc 1 - that ends exactly on the last target. -> [(frame, x0)], best first."""
        (L1max, k1max), (L2max, k2max) = robot_model.arc_limits(self.robot)
        T, P = np.asarray(tips[-1], float), np.asarray(tips[-2], float)
        if len(tips) >= 3:
            d = P - np.asarray(tips[-3], float); dirs = [d / np.linalg.norm(d)]
        else:
            # entries whose straight line through P can still bend onto T with the tightest arc
            Lpt = float(np.linalg.norm(T - P))
            amax = float(np.degrees(np.arcsin(min(1.0, Lpt * k2max / 2)))) + 2.0
            dirs = [(P - self.entry_pts[i]) / np.linalg.norm(P - self.entry_pts[i])
                    for i in self._straight_entries(P, n, along=P - T, max_angle_deg=amax)]
        cands = []
        for d in dirs:
            for t in (0.0, 4.0, 8.0, 12.0):                         # the arc starts at P or a little after it
                S = P + d * t
                c = T - S; L = float(np.linalg.norm(c))
                if L < 1.0: continue
                u = c / L; cth = float(np.clip(d @ u, -1, 1)); th = float(np.arccos(cth))
                if th < 1e-3: k, s_len, nc = 0.0, L, robot_model._perp(d)
                else:
                    perp = u - cth * d; nc = perp / np.linalg.norm(perp)
                    Rr = L / (2 * np.sin(th)); k, s_len = 1.0 / Rr, 2 * th * Rr
                if k > k2max * 1.0001 or s_len > L1max + L2max: continue
                L2 = min(s_len, L2max); L1 = s_len - L2
                if L1 > 1e-6 and k > k1max * 1.0001: continue          # arc 1 cannot bend this tightly
                v_tip = np.cos(2 * th) * d + np.sin(2 * th) * nc if k > 0 else d
                v = -v_tip / np.linalg.norm(v_tip)
                if k > 0:
                    C = S + nc / k                                     # circle centre
                    phi2 = self._phi_for(v, (C - T) * k)
                    p2, v1 = robot_model.arc(T, v, k, L2, phi2)
                    phi1 = self._phi_for(v1, (C - p2[-1]) * k)
                else: phi2 = phi1 = 0.0
                e1 = robot_model._perp(v); frame = (v, e1, np.cross(v, e1))
                x0 = np.array([0, 0, L2, k, phi2, L1, min(k, k1max), phi1], float)
                f = self._evaluate(x0, T, frame, np.array(tips, float), w=1.0)
                cands.append((f, frame, x0))
        cands.sort(key=lambda c: c[0])
        return [(fr, x0) for _, fr, x0 in cands[:keep]]

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

    def _straight_entries(self, tip, n, along=None, max_angle_deg=30.0):
        """Entries from which a straight line to the target is already safe (best = short + far from soft zones).
        along: preferred direction from the target back to the entry (within 30 deg), for paths through several targets."""
        E, N = self.entry_pts, self.entry_n
        d = tip - E; L = np.linalg.norm(d, axis=1); u = d / L[:, None]
        ang = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", u, -N), -1, 1)))
        keep = (L < self.robot["max_length_mm"]) & (ang < self.robot["max_entry_angle_deg"])
        if along is not None:
            a = along / np.linalg.norm(along); keep &= (-u @ a) > np.cos(np.radians(max_angle_deg))
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
        R = 1.0 / max(k for _, k in robot_model.arc_limits(self.robot))  # tightest arc of the robot
        theta = np.degrees(np.arcsin(min(1.0, d / (2 * R)))) + 10.0
        V = self._arrival_dirs(a)
        if not len(V): return False
        ang = np.degrees(np.arccos(np.clip((-V) @ ((b - a) / d), -1, 1)))
        return bool(ang.min() <= theta)

    def _optimise(self, names, tips, E, nrm, routes, init=None):
        """Robot shape (straight + arc 1 + arc 2) close to the coarse route E -> targets, then optimised.
        The shape is built backwards from the last target, so the tip is exactly on it.
        init = (frame, x0): start from this shape instead of fitting one to the route (see _arc_inits)."""
        T = np.asarray(tips[-1], float); Tall = np.array(tips, float)
        (L1max, k1max), (L2max, k2max) = robot_model.arc_limits(self.robot)
        if init is not None:
            frame, x0 = init
            return self._refine(names, T, Tall, frame, np.asarray(x0, float))
        route = np.vstack([np.asarray(rt, float) for rt in routes])        # entry ... last target
        back = route[::-1]
        cl = np.r_[0, np.cumsum(np.linalg.norm(np.diff(back, axis=0), axis=1))]
        aim = back[min(np.searchsorted(cl, 10.0), len(back) - 1)] - T      # route direction ~10 mm before the tip
        if np.linalg.norm(aim) < 1e-6: aim = E - T
        d0 = aim / np.linalg.norm(aim); e1 = robot_model._perp(d0); e2 = np.cross(d0, e1)
        frame = (d0, e1, e2)
        bounds = [(-1.5, 1.5), (-1.5, 1.5), (0, L2max), (0, k2max), (-7, 7), (0, L1max), (0, k1max), (-7, 7)]
        calls = [0]
        def stop_check():
            calls[0] += 1
            if calls[0] % 200 == 0: self._check_stop()               # lets the Stop button interrupt an optimisation
        # 1. fit the shape to the coarse route (mean squared distance of the route to the robot)
        rpts = route[np.linalg.norm(route - E, axis=1) > 1.0]
        def fit(x):
            stop_check()
            sh = self._shape(x, T, frame)
            if sh is None: return 1e6
            d = cKDTree(sh["points"]).query(rpts)[0]
            return float(np.mean(d ** 2)) + 0.01 * np.sum((sh["entry"] - E) ** 2)
        best_x, best_f = None, np.inf
        for x0 in ([0, 0, 15, 0, 0, 15, 0, 0], [0, 0, 20, 0.5 * k2max, 0, 20, 0.5 * k1max, 0],
                   [0, 0, 20, 0.5 * k2max, np.pi, 20, 0.5 * k1max, np.pi]):
            try:
                o = minimize(fit, np.array(x0, float), method="Powell", bounds=bounds,
                             options=dict(maxfev=600, xtol=1e-2, ftol=1e-3))
            except Cancelled: raise
            if o.fun < best_f: best_x, best_f = o.x, o.fun
        return self._refine(names, T, Tall, frame, best_x)

    def _bounds_via(self):
        (L1max, k1max), _ = robot_model.arc_limits(self.robot)
        return [(-1.5, 1.5), (-1.5, 1.5), (0, L1max), (0, k1max), (-7, 7)]

    def _optimise_via(self, names, tips, E, route):
        """Several targets, the second-to-last one (P) exactly where arc 1 meets arc 2: arc 2 runs from P to the
        tip, arc 1 and the straight part are fitted to the coarse route skin -> P, then everything is optimised.
        Unlike _arc_inits the robot may already be curved when it passes P."""
        T, P = np.asarray(tips[-1], float), np.asarray(tips[-2], float); Tall = np.array(tips, float)
        d0 = (P - T) / np.linalg.norm(P - T); e1 = robot_model._perp(d0); frame = (d0, e1, np.cross(d0, e1))
        (L1max, k1max), _ = robot_model.arc_limits(self.robot)
        rpts = np.asarray(route, float); rpts = rpts[np.linalg.norm(rpts - E, axis=1) > 1.0]
        calls = [0]
        def fit(x):
            calls[0] += 1
            if calls[0] % 200 == 0: self._check_stop()
            sh = self._shape(x, T, frame, via=P)
            if sh is None: return 1e6
            dd = cKDTree(sh["points"]).query(rpts)[0]
            return float(np.mean(dd ** 2)) + 0.01 * np.sum((sh["entry"] - E) ** 2) + 100.0 * sh["over"] ** 2
        best_x, best_f = None, np.inf
        for x0 in ([0, 0, 15, 0, 0], [0, 0, 25, 0.5 * k1max, 0], [0, 0, 25, 0.5 * k1max, np.pi]):
            o = minimize(fit, np.array(x0, float), method="Powell", bounds=self._bounds_via(),
                         options=dict(maxfev=600, xtol=1e-2, ftol=1e-3))
            if o.fun < best_f: best_x, best_f = o.x, o.fun
        return self._refine(names, T, Tall, frame, best_x, via=P)

    def _bounds(self):
        (L1max, k1max), (L2max, k2max) = robot_model.arc_limits(self.robot)
        return [(-1.5, 1.5), (-1.5, 1.5), (0, L2max), (0, k2max), (-7, 7), (0, L1max), (0, k1max), (-7, 7)]

    def _refine(self, names, T, Tall, frame, x, via=None):
        """Penalty continuation: soft first, then strict (Powell, derivative-free: the skin entry moves in jumps)."""
        bounds = self._bounds() if via is None else self._bounds_via()
        calls = [0]
        def stop_check():
            calls[0] += 1
            if calls[0] % 200 == 0: self._check_stop()
        def fun(x, w):
            stop_check()
            return self._evaluate(x, T, frame, Tall, w=w, via=via)
        d = None
        try:
            for w in (0.2, 1.0, 5.0, 25.0):
                opt = minimize(fun, x, args=(w,), method="Powell", bounds=bounds,
                               options=dict(maxfev=self.pl["optimizer_iterations"] * 8, xtol=1e-2, ftol=1e-4))
                x = opt.x
                d = self._evaluate(x, T, frame, Tall, detail=True, via=via)
                if d is None: return None
                if w >= 1.0 and not self._result(names, d).problems: break
        except Cancelled:
            raise
        except Exception as ex:
            self.log(f"    optimisation failed: {ex}"); return None
        return self._result(names, d)

    def _result(self, names, d):
        rb, problems = self.robot, []
        L0, L1, L2 = d["L"]; k1, k2 = d["k"]
        if d["min_c"] < -0.1: problems.append(f"enters a no-go zone ({-d['min_c']:.1f} mm too close)")
        if d["entry_dist"] > 1.5 * self.pl["search_grid_mm"] + 0.5: problems.append("entry outside the allowed skin zone")
        if d["angle"] > rb["max_entry_angle_deg"] + 0.5: problems.append(f"entry angle {d['angle']:.0f} deg")
        if d["length"] > rb["max_length_mm"] + 0.5: problems.append(f"too long ({d['length']:.0f} mm)")
        if L0 < robot_model.min_straight(rb) - 0.5: problems.append(f"straight part only {L0:.0f} mm")
        (L1max, k1max), (L2max, k2max) = robot_model.arc_limits(rb)
        if k2 > k2max * 1.03 or L2 > L2max + 0.5: problems.append(f"arc 2 out of range ({L2:.0f} mm, R {1 / max(k2, 1e-9):.0f} mm)")
        for n, m in zip(names[:-1], d["miss"]):
            if m > self.pl.get("target_pass_mm", 1.0): problems.append(f"misses {n} by {m:.1f} mm")
        pts = d["points"]
        clear = {}
        r = rb["diameter_mm"] / 2
        for zname, fld in self.p.zone_dist.items():
            if zname in self.cfg.get("no_go", {}) and "outside_of" in self.cfg["no_go"][zname]: continue
            clear[zname] = round(float(fld(pts).min() - r), 1)
        used = [(L, k) for L, k in ((L1, k1), (L2, k2)) if L > 0.5 and k > 1e-5]
        rmin = min((1 / k for _, k in used), default=1e9)
        shape = {"straight_mm": round(float(L0), 1),
                 "arc1_mm": round(float(L1), 1), "arc1_radius_mm": round(float(1 / max(k1, 1e-9)), 1) if k1 > 1e-5 else None,
                 "arc1_plane_deg": round(float(np.degrees(d["phi"][0])) % 360, 1),
                 "arc2_mm": round(float(L2), 1), "arc2_radius_mm": round(float(1 / max(k2, 1e-9)), 1) if k2 > 1e-5 else None,
                 "arc2_plane_deg": round(float(np.degrees(d["phi"][1])) % 360, 1)}
        turn = float(np.degrees(k1 * L1 + k2 * L2))
        return PathResult(list(names), d["entry"], pts, not problems, float(d["cost"]), float(d["length"]),
                          float(rmin), float(d["angle"]), turn, clear, problems, d["labels"], shape)

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

    # ------------------------------------------------------------------ target regions
    def _skin_field(self):
        """Coarse cost of the cheapest route from any allowed skin entry to every grid cell (one Dijkstra, cached)."""
        if getattr(self, "_skin_cum", None) is None:
            m = MCP_Geometric(self.g_cost, fully_connected=True)
            self._skin_cum, _ = m.find_costs([tuple(i) for i in self.entry_idx])
        return self._skin_cum

    def region_tip(self, name, mask, n_try=3, edge_mm=1.5, spread_mm=5.0):
        """Tip point for a target region (boolean volume on the patient grid): anywhere inside the region.
        Safe points (clear of every strict no-go zone) at least edge_mm inside the region's edge are preferred;
        they are ranked by the coarse route cost from the skin, the n_try best (spread_mm apart) are planned in
        full and the tip of the cheapest feasible path is returned. -> (tip RAS mm or None, message)."""
        ijk = np.argwhere(mask)
        if not len(ijk): return None, "the region is empty"
        if len(ijk) > 20000: ijk = ijk[np.random.default_rng(0).choice(len(ijk), 20000, replace=False)]
        pts = self.p.vox_to_mm(ijk)
        safe = self.p.C_strict(pts) > 0.3
        if not safe.any(): return None, "the whole region lies in no-go zones (or too close to them)"
        lo, hi = ijk.min(0), ijk.max(0) + 1                         # distance to the region's edge, on its bounding box
        sub = np.pad(mask[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]], 1)
        depth = ndimage.distance_transform_edt(sub, sampling=self.p.vox)[tuple((ijk - lo + 1).T)]
        inner = safe & (depth >= min(edge_mm, depth[safe].max()))
        cum = self._skin_field()
        gi = np.array([self.g_idx(q) for q in pts[inner]])
        cost = cum[tuple(gi.T)]
        cand, P = [], pts[inner]
        for i in np.argsort(cost):
            if not np.isfinite(cost[i]): break
            if all(np.linalg.norm(P[i] - c) >= spread_mm for c in cand): cand.append(P[i])
            if len(cand) >= n_try: break
        if not cand: return None, "no route from the skin reaches the region"
        best = None
        for c in cand:
            self._check_stop()
            res = self.plan_sequence((name,), [c], n_entries=2)
            if res and (best is None or (res.feasible, -res.cost) > (best[1].feasible, -best[1].cost)): best = (c, res)
        if best is None: return cand[0], "no smooth path found yet - using the easiest point of the region"
        c, res = best
        return c, (f"tip at ({c[0]:.1f}, {c[1]:.1f}, {c[2]:.1f}), {'reachable' if res.feasible else 'not reachable yet'}"
                   f", {len(cand)} point(s) of the region tried")

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
                 f" (length {res.length_mm:.0f} mm: {robot_model.shape_text(res.shape)})")

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
