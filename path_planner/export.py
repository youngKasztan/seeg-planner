"""
export.py - write the planned paths for the headset app.

  <headset>/plan.json   targets and paths (RAS mm and headset scene metres), robot settings, checks
  <headset>/paths.glb   tubes along the paths (robot diameter) + target spheres, in the same coordinates as
                        patient_scene.glb, so the headset shows them inside the brain (PatientLoader loads it)
"""
import json, os
import numpy as np
import trimesh

R = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)          # RAS -> glTF (Y up), as in tools/export_headset.py
COLOURS = [(0.1, 0.8, 1.0), (1.0, 0.55, 0.1), (0.7, 0.3, 1.0), (0.2, 1.0, 0.4), (1.0, 0.3, 0.6)]

def to_scene(p, centre): return ((np.asarray(p) - centre) @ R.T) / 1000.0

def tube(points, radius, sides=12):
    """Triangle mesh of a tube along a polyline (parallel-transport frames, no twisting)."""
    P = np.asarray(points, float)
    T = np.gradient(P, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True)
    n = np.cross(T[0], [0, 0, 1.0]); n = n if np.linalg.norm(n) > 1e-3 else np.cross(T[0], [0, 1.0, 0])
    n /= np.linalg.norm(n); frames = []
    for t in T:
        n = n - (n @ t) * t; n /= np.linalg.norm(n); frames.append((n, np.cross(t, n)))
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    V = np.array([p + radius * (np.cos(a) * f[0] + np.sin(a) * f[1]) for p, f in zip(P, frames) for a in ang])
    F = []
    for i in range(len(P) - 1):
        for j in range(sides):
            a, b = i * sides + j, i * sides + (j + 1) % sides
            F += [[a, b + sides, b], [a, a + sides, b + sides]]
    m = trimesh.Trimesh(V, F, process=False)
    cap = trimesh.creation.icosphere(2, radius); cap.apply_translation(P[-1])          # rounded tip
    return trimesh.util.concatenate([m, cap])

def export(headset_dir, paths, targets, cfg, centre, uncovered=(), target_problems=None):
    os.makedirs(headset_dir, exist_ok=True)
    sc = lambda p: np.round(to_scene(p, centre), 5).tolist()
    rad = cfg["robot"]["diameter_mm"] / 2
    scene = trimesh.Scene()
    out = {"note": "Research prototype - automatic proposal, must be reviewed by the surgical team.",
           "robot": cfg["robot"], "targets": {}, "paths": [], "not_reached": list(uncovered),
           "target_problems": target_problems or {}}
    for name, p in targets.items():
        out["targets"][name] = {"ras_mm": np.round(p, 2).tolist(), "scene_m": sc(p)}
        s = trimesh.creation.icosphere(2, 2.0 / 1000); s.apply_translation(to_scene(p, centre))
        s.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            name="target", baseColorFactor=[1.0, 0.1, 0.9, 1.0], metallicFactor=0.0, roughnessFactor=0.5))
        scene.add_geometry(s, node_name=f"target_{name}", geom_name=f"target_{name}")
    for i, r in enumerate(paths):
        col = COLOURS[i % len(COLOURS)]
        m = tube(to_scene(r.points, centre), rad / 1000)
        m.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            name=f"path_{i + 1}", baseColorFactor=[*col, 1.0], metallicFactor=0.1, roughnessFactor=0.4))
        scene.add_geometry(m, node_name=f"path_{i + 1}", geom_name=f"path_{i + 1}")
        out["paths"].append({
            "id": f"path_{i + 1}", "targets": r.targets, "colour": col,
            "entry_ras_mm": np.round(r.entry, 2).tolist(), "entry_scene_m": sc(r.entry),
            "points_ras_mm": np.round(r.points, 2).tolist(), "points_scene_m": sc(r.points),
            "length_mm": round(r.length_mm, 1), "min_bend_radius_mm": round(r.min_radius_mm, 1),
            "entry_angle_deg": round(r.entry_angle_deg, 1), "total_turn_deg": round(r.total_turn_deg, 1),
            "min_clearance_mm": r.min_clearance_mm, "feasible": r.feasible, "problems": r.problems})
    json.dump(out, open(os.path.join(headset_dir, "plan.json"), "w"), indent=1)
    if len(scene.geometry): scene.export(os.path.join(headset_dir, "paths.glb"))
    return os.path.join(headset_dir, "plan.json")
