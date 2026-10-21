"""
electrode.py - recording contacts of the SEEG electrode carried by the robot.

The electrode is not one continuous conductor: it has short contacts at a fixed spacing (robot.toml [electrode],
default every 5 mm). The deepest contact sits at the tip, i.e. on the last target of the path; the others follow
back along the curved path every contact_spacing_mm of arc length. A target is "on a contact" when the centre of
some contact is within on_target_mm of it - that is what the app shows, so you can see that the electrode really
records at every target and not between two contacts.

Contacts are numbered from the tip: contact 1 = deepest (the usual SEEG convention).
"""
from dataclasses import dataclass, field
import numpy as np

DEFAULTS = {"contact_spacing_mm": 5.0, "contact_length_mm": 2.0, "first_contact_mm": 0.0,
            "n_contacts": 0, "on_target_mm": 1.5}


def settings(cfg):
    e = dict(DEFAULTS); e.update(cfg.get("electrode", {}))
    return e


@dataclass
class Contacts:
    centres: np.ndarray                 # K x 3, RAS mm, contact 1 (tip) first
    tangents: np.ndarray                # K x 3 unit vectors along the path (towards the tip)
    depth_mm: np.ndarray                # K, arc length from the tip to the contact centre
    on_target: dict = field(default_factory=dict)   # target name -> (contact number 1.., distance mm)
    hits: set = field(default_factory=set)          # contact indices (0-based) that lie on a target


def _arclength(P):
    return np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]


def contacts(points, cfg, targets=None):
    """Contacts along a path (points: entry -> tip, RAS mm). targets: {name: RAS mm} of the targets on this path.
    Contacts stop at the end of the straight entry (skin and bone) unless n_contacts limits them earlier."""
    e = settings(cfg)
    P = np.asarray(points, float)
    s = _arclength(P); L = s[-1]
    skip = float(cfg.get("robot", {}).get("straight_entry_mm", 0.0))
    d = e["first_contact_mm"] + e["contact_spacing_mm"] * np.arange(int(L / max(e["contact_spacing_mm"], 0.1)) + 2)
    d = d[d <= max(L - skip, 0.0)]
    if int(e["n_contacts"]) > 0: d = d[:int(e["n_contacts"])]
    pos = L - d                                                        # arc position from the entry
    C = np.stack([np.interp(pos, s, P[:, i]) for i in range(3)], 1)
    T = np.gradient(P, axis=0); T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    Tc = np.stack([np.interp(pos, s, T[:, i]) for i in range(3)], 1)
    Tc /= np.maximum(np.linalg.norm(Tc, axis=1, keepdims=True), 1e-9)
    out = Contacts(C, Tc, d)
    for name, t in (targets or {}).items():
        if not len(C): break
        dist = np.linalg.norm(C - np.asarray(t, float), axis=1)
        k = int(dist.argmin())
        out.on_target[name] = (k + 1, float(dist[k]))
        if dist[k] <= e["on_target_mm"]: out.hits.add(k)
    return out


def for_path(path, cfg, all_targets):
    """Contacts of a planner PathResult, checked against the targets that path is meant to reach."""
    return contacts(path.points, cfg, {n: all_targets[n] for n in path.targets if n in all_targets})


def summary(c, cfg):
    """Short text for the path list, e.g. '18 contacts | T1: #1 0.0 mm | T2: #7 1.2 mm'."""
    tol = settings(cfg)["on_target_mm"]
    parts = [f"{len(c.centres)} contacts"]
    for n, (k, dist) in c.on_target.items():
        parts.append(f"{n}: #{k} {dist:.1f} mm" + ("" if dist <= tol else " NOT ON A CONTACT"))
    return " | ".join(parts)
