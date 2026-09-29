"""
render_preview.py - podglad PNG pakietu pacjenta (bez okularow): 3 widoki modelu 3D.

  1. caly mozg (kora nieprzezroczysta) + tetnice
  2. kora przezroczysta: widac komory, hipokamp, migdalowate, wzgorze, jadra, pien i tetnice w srodku
  3. to samo z gory

Uzycie: python tools/render_preview.py --package wyniki/IXI057/package --out preview.png
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
    p = pv.Plotter(off_screen=True, shape=(1, 3), window_size=(1800, 640), border=False)
    p.enable_depth_peeling(10)
    views = [("Caly mozg (z tylu) + tetnice", 1.0, "xz", True),
             ("Kora przezroczysta: struktury glebokie", 0.12, "yz", False),
             ("Widok z gory", 0.12, "xy", False)]
    for i, (title, cortex_op, view, only_vessels) in enumerate(views):
        p.subplot(0, i); p.set_background("black")
        for n, op in (("gray_matter", cortex_op), ("cerebellum", max(cortex_op, 0.25))):
            if meshes.get(n) is not None:
                p.add_mesh(meshes[n], color=col[n], opacity=op, smooth_shading=True, specular=0.2)
        for n in deep:
            if meshes.get(n) is None or (only_vessels and n != "vessels"):
                continue
            p.add_mesh(meshes[n], color=col[n], smooth_shading=True)
        p.add_text(title, font_size=11, color="white")
        getattr(p, f"view_{view}")()
        if view == "yz": p.camera.azimuth = 180
        p.camera.zoom(1.35)
    p.screenshot(a.out)
    print("podglad ->", a.out)

if __name__ == "__main__":
    main()
