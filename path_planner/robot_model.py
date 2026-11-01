"""
robot_model.py - the shape the robot can take.

The robot is built like a concentric-tube robot:
  1. a straight part pushed out first, of any length (through skin and bone and on into the brain);
  2. arc 1: a pre-curved tube comes out of the straight part - a circular arc, length 0..arc1_max_length_mm,
     radius >= arc1_min_radius_mm;
  3. arc 2: a thinner pre-curved tube comes out of arc 1 and carries the tip - a circular arc, length
     0..arc2_max_length_mm, radius >= arc2_min_radius_mm.
Each tube can be rotated about its axis, so every arc can bend in its own plane (angle phi).
The inner tube is thinner, so it can be bent more tightly without overstraining the material
(strain = tube radius / bend radius): arc 2 may have the larger curvature (smaller minimum radius) - set both
minimum radii in robot.toml. Wider arcs are preferred by the planner (cost on curvature^2 x length).

The planner builds the shape BACKWARDS from the target, so the tip is always exactly on the target:
  tip direction -> arc 2 -> arc 1 -> straight line back to the skin (its length follows from where it leaves the
  head). Variables: 2 for the tip direction, (length, curvature, plane) for each arc.

Point labels: 0 = straight, 1 = arc 1, 2 = arc 2.
"""
import numpy as np

SEGMENT_NAMES = {0: "straight", 1: "arc 1", 2: "arc 2"}
SEGMENT_COLOURS = {0: (0.2, 0.8, 1.0), 1: (1.0, 0.85, 0.0), 2: (1.0, 0.45, 0.0)}    # cyan, yellow, orange


def arc_limits(robot):
    """[(max length, max curvature)] for arc 1 and arc 2."""
    return [(float(robot.get("arc1_max_length_mm", 35.0)), 1.0 / float(robot.get("arc1_min_radius_mm", 50.0))),
            (float(robot.get("arc2_max_length_mm", 35.0)), 1.0 / float(robot.get("arc2_min_radius_mm", 30.0)))]


def min_straight(robot):
    return float(robot.get("min_straight_mm", robot.get("straight_entry_mm", 15.0)))


def _perp(v):
    a = np.cross(v, [0.0, 0.0, 1.0])
    if a @ a < 1e-6: a = np.cross(v, [0.0, 1.0, 0.0])
    return a / np.linalg.norm(a)


def arc(p, v, kappa, L, phi, step=1.0):
    """Circular arc starting at p with unit tangent v, curvature kappa, length L, bent towards the direction
    obtained by rotating a reference normal of v by phi. -> (points incl. p, tangent at the end)."""
    n = max(int(np.ceil(L / step)), 1)
    s = np.linspace(0.0, L, n + 1)
    n0 = _perp(v); b = np.cos(phi) * n0 + np.sin(phi) * np.cross(v, n0)
    k = max(float(kappa), 1e-9)
    ks = k * s
    pts = p + np.outer(np.sin(ks) / k, v) + np.outer((1.0 - np.cos(ks)) / k, b)
    return pts, np.cos(k * L) * v + np.sin(k * L) * b


def backward(tip, v_back, L2, k2, phi2, L1, k1, phi1, step=1.0):
    """Arcs built from the tip backwards. v_back: unit vector from the tip back along the robot.
    -> (arc 2 points tip->arc1, arc 1 points ->straight, direction pointing back out of the straight part)."""
    p2, v1 = arc(np.asarray(tip, float), v_back, k2, L2, phi2, step)
    p1, v0 = arc(p2[-1], v1, k1, L1, phi1, step)
    return p2, p1, v0


def assemble(entry, p0, p1, p2, step=1.0):
    """Points entry -> tip and their segment labels (0 straight, 1 arc 1, 2 arc 2)."""
    L0 = float(np.linalg.norm(p0 - entry))
    n0 = max(int(np.ceil(L0 / step)), 1)
    straight = entry + np.outer(np.linspace(0.0, 1.0, n0 + 1), p0 - entry)
    a1, a2 = p1[::-1], p2[::-1]                     # forward order: straight end -> arc 1 -> arc 2 -> tip
    pts = np.vstack([straight, a1[1:], a2[1:]])
    lab = np.r_[np.zeros(len(straight), int), np.ones(len(a1) - 1, int), np.full(len(a2) - 1, 2)]
    return pts, lab


def shape_text(shape):
    """'straight 42 | arc 1 20 mm R 80 | arc 2 15 mm R 45' (arcs shorter than 0.5 mm or straight are left out)."""
    if not shape: return ""
    out = [f"straight {shape['straight_mm']:.0f}"]
    for a in ("arc1", "arc2"):
        L, R = shape.get(f"{a}_mm", 0), shape.get(f"{a}_radius_mm")
        if L >= 0.5 and R is not None and R < 1e4: out.append(f"{a[:3]} {a[3]} {L:.0f} mm R {R:.0f}")
        elif L >= 0.5: out.append(f"{a[:3]} {a[3]} {L:.0f} mm straight")
    return " | ".join(out)
