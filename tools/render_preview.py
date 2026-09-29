"""
render_preview.py - PNG preview of a patient package (no headset needed): 6 views of the 3D model.

Row 1: anatomy
  1. whole brain (opaque cortex) + arteries
  2. transparent cortex: ventricles, hippocampus, amygdala, thalamus, basal ganglia, brainstem, arteries
  3. the same from above
Row 2: functional layers (what trajectories must avoid besides vessels)
  4. eloquent cortex on the brain (motor, sensory, visual, auditory, language) - left lateral view
  5. white-matter tracts in a transparent brain - lateral view
  6. white-matter tracts - from above

Usage: python tools/render_preview.py --package results/IXI057/package --out preview.png
"""
import argparse, json, os
import numpy as np
import pyvista as pv
import trimesh

pv.OFF_SCREEN = True

def load(pkg, name):
    p = os.path.join(pkg, "meshes", f"{name}.glb")
    if not os.path.exists(p):
        return None
    m = trimesh.load(p, force="mesh")
    faces = np.hstack([np.full((len(m.faces), 1), 3), m.faces]).ravel()
    return pv.PolyData(np.asarray(m.vertices), faces)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--package", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    man = json.load(open(os.path.join(a.package, "manifest.json")))
    col = {L["name"]: np.array(L["rgba"][:3]) / 255 for L in man["layers"]}
    meshes = {n: load(a.package, n) for n in col}
    deep = ["ventricles", "hippocampus", "amygdala", "thalamus", "basal_ganglia", "brainstem", "vessels"]
    elo = [n for n in col if n.startswith("eloquent_")]
    tracts = [n for n in col if n.split("_")[0] in ("cst", "arcuate", "optic")]
    two_rows = bool(elo or tracts)

    p = pv.Plotter(off_screen=True, shape=(2 if two_rows else 1, 3), window_size=(1800, 1280 if two_rows else 640), border=False)
    p.enable_depth_peeling(10)

    def cortex(op):
        for n, o in (("gray_matter", op), ("cerebellum", max(op, 0.25))):
            if meshes.get(n) is not None:
                p.add_mesh(meshes[n], color=col[n], opacity=o, smooth_shading=True, specular=0.2)

    def add(names):
        for n in names:
            if meshes.get(n) is not None:
                p.add_mesh(meshes[n], color=col[n], smooth_shading=True)

    def cam(view, title, left=False):
        p.add_text(title, font_size=11, color="white")
        getattr(p, f"view_{view}")()
        if view == "yz": p.camera.azimuth = 180          # view from the patient's left side
        p.camera.zoom(1.35)

    for i, (title, op, view, names) in enumerate([
            ("Whole brain (posterior view) + arteries", 1.0, "xz", ["vessels"]),
            ("Transparent cortex: deep structures", 0.12, "yz", deep),
            ("Top view", 0.12, "xy", deep)]):
        p.subplot(0, i); p.set_background("black"); cortex(op); add(names); cam(view, title)

    if two_rows:
        p.subplot(1, 0); p.set_background("black")
        if meshes.get("gray_matter") is not None:
            p.add_mesh(meshes["gray_matter"], color=[0.55, 0.5, 0.5], smooth_shading=True)
        add(elo); cam("yz", "Eloquent cortex (atlas): motor, sensory, visual, auditory, language", left=True)
        p.subplot(1, 1); p.set_background("black"); cortex(0.08); add(tracts + ["ventricles"])
        cam("yz", "White-matter tracts: corticospinal, arcuate, optic radiation", left=True)
        p.subplot(1, 2); p.set_background("black"); cortex(0.08); add(tracts + ["ventricles"])
        cam("xy", "White-matter tracts - top view")
    p.screenshot(a.out)
    print("preview ->", a.out)

if __name__ == "__main__":
    main()
