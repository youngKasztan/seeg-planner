"""
headset_scene.py - the brain model for the headset, with exactly the layers and groups of the planner app.

Writes into the patient's headset folder:
  patient_scene.glb        one named node per layer (metres, glTF axes), colours and transparency as in the app
  patient_scene_lite.glb   same, fewer triangles (HoloLens 2 / web)
  headset_manifest.json    'layers' replaced by the planner layers (name, group, origin, colour, opacity, visible);
                           landmarks, coordinate system and the rest of the manifest are kept unchanged
The first time, the original files from tools/export_headset.py are kept as *_pipeline.glb / *_pipeline.json.

Coordinates: p_scene = R (p_ras - centre) / 1000, the same transform as paths.glb and tools/export_headset.py.
"""
import json, os, shutil
import numpy as np
import trimesh
from scipy import ndimage
from skimage import measure

import export

GROUPS = {"nogo": "No-go zones", "soft": "Soft zones", "layer": "Anatomy"}
HEAD_LAYERS = ("skull_t1", "scalp")
CATEGORY = {"No-go zones": "critical", "Soft zones": "soft", "Anatomy": "anatomy", "Head": "surface",
            "Target regions": "target"}


def mask_mesh(mask, vox_to_mm, sigma):
    """Smooth surface of a binary mask, vertices in RAS mm."""
    m = ndimage.gaussian_filter(np.pad(mask, 2).astype(np.float32), sigma) if sigma > 0 else np.pad(mask, 2).astype(np.float32)
    if m.max() < 0.5: return None
    v, f, _, _ = measure.marching_cubes(m, 0.5)
    mesh = trimesh.Trimesh(vox_to_mm(v - 2), f, process=True)
    trimesh.smoothing.filter_taubin(mesh, iterations=10)
    return mesh


def opacity(key, ml):
    """Same rule as the 3D view of the app: large layers faint, small ones solid."""
    if key in ("gray_matter", "white_matter", "scalp", "skull_t1"): return 0.15
    if key.startswith("region_"): return 0.35                          # target region: see the path inside it
    return 0.2 if ml > 20 else 1.0


def make_meshes(layers, patient):
    """layers: [(name, group, mask, colour, visible, origin)] -> [(name, group, mesh RAS mm, colour, visible, origin, ml)]."""
    vox_ml = patient.vox.prod() / 1000
    out = []
    for name, group, mask, col, vis, origin in layers:
        ml = float(mask.sum() * vox_ml)
        mesh = mask_mesh(mask, patient.vox_to_mm, 1.0 if ml > 20 else 0.5)   # thin vessels need less smoothing
        if mesh is not None and len(mesh.faces): out.append((name, group, mesh, col, vis, origin, ml))
    return out


def build(meshes, centre, budget):
    """-> (trimesh.Scene in glTF metres, manifest layer list, triangles), decimated to the triangle budget."""
    total = sum(len(m[2].faces) for m in meshes)
    scale = min(1.0, budget / max(total, 1))
    scene, out = trimesh.Scene(), []
    for name, group, mesh, col, vis, origin, ml in meshes:
        m = mesh.copy()
        if scale < 1.0 and len(m.faces) > 2000:
            try: m = m.simplify_quadric_decimation(face_count=max(1000, int(len(m.faces) * scale)))
            except Exception: pass
        m.vertices = export.to_scene(m.vertices, centre)
        op = opacity(name, ml)
        m.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            name=name, baseColorFactor=[*col, op], metallicFactor=0.0, roughnessFactor=0.7,
            alphaMode="BLEND" if op < 1.0 else "OPAQUE", doubleSided=True))
        scene.add_geometry(m, node_name=name, geom_name=name)
        out.append({"name": name, "node": name, "group": group, "category": CATEGORY[group], "visible": vis,
                    "opacity": op, "colour": [round(c, 3) for c in col], "origin": origin, "volume_ml": round(ml, 1)})
    return scene, out, int(sum(len(g.faces) for g in scene.geometry.values()))


def export_scene(headset_dir, patient, layers, log=print, budget=600000, budget_lite=200000):
    """Write patient_scene(.glb/_lite.glb) and update headset_manifest.json; returns the number of layers."""
    man_path = os.path.join(headset_dir, "headset_manifest.json")
    man = json.load(open(man_path))
    for src, dst in (("patient_scene.glb", "patient_scene_pipeline.glb"), ("patient_scene_lite.glb", "patient_scene_lite_pipeline.glb"),
                     ("headset_manifest.json", "headset_manifest_pipeline.json")):
        s, d = os.path.join(headset_dir, src), os.path.join(headset_dir, dst)
        if os.path.exists(s) and not os.path.exists(d): shutil.copy2(s, d)       # keep the original once
    centre = np.array(man["coordinate_system"]["head_centre_ras_mm"], float)
    log(f"  headset model: {len(layers)} layers ...")
    meshes = make_meshes(layers, patient)
    full, out, nf = build(meshes, centre, budget)
    full.export(os.path.join(headset_dir, "patient_scene.glb"))
    lite, _, nl = build(meshes, centre, budget_lite)
    lite.export(os.path.join(headset_dir, "patient_scene_lite.glb"))
    man["layers"] = out
    man["layers_source"] = "path_planner (same layers and groups as the planner app)"
    man["triangles"] = {"full": nf, "lite": nl}
    json.dump(man, open(man_path, "w"), indent=1)
    log(f"  headset model written: {len(out)} layers, {nf} triangles (lite {nl})")
    return len(out)
