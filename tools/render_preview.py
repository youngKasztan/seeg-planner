"""
render_preview.py - podglad PNG pakietu pacjenta (bez okularow): 6 widokow modelu 3D.

Rzad 1: anatomia
  1. caly mozg (kora nieprzezroczysta) + tetnice
  2. kora przezroczysta: komory, hipokamp, migdalowate, wzgorze, jadra, pien, tetnice
  3. to samo z gory
Rzad 2: warstwy funkcjonalne (to, czego trajektoria ma unikac poza naczyniami)
  4. kora elokwentna na mozgu (ruch, czucie, wzrok, sluch, mowa) - z boku, lewa polkula
  5. drogi istoty bialej w przezroczystym mozgu - z boku
  6. drogi istoty bialej - z gory

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
        if view == "yz": p.camera.azimuth = 180          # widok od lewej strony pacjenta
        p.camera.zoom(1.35)

    for i, (title, op, view, names) in enumerate([
            ("Caly mozg (z tylu) + tetnice", 1.0, "xz", ["vessels"]),
            ("Kora przezroczysta: struktury glebokie", 0.12, "yz", deep),
            ("Widok z gory", 0.12, "xy", deep)]):
        p.subplot(0, i); p.set_background("black"); cortex(op); add(names); cam(view, title)

    if two_rows:
        p.subplot(1, 0); p.set_background("black")
        if meshes.get("gray_matter") is not None:
            p.add_mesh(meshes["gray_matter"], color=[0.55, 0.5, 0.5], smooth_shading=True)
        add(elo); cam("yz", "Kora elokwentna (atlas): ruch, czucie, wzrok, sluch, mowa", left=True)
        p.subplot(1, 1); p.set_background("black"); cortex(0.08); add(tracts + ["ventricles"])
        cam("yz", "Drogi istoty bialej: korowo-rdzeniowa, lukowata, wzrokowa", left=True)
        p.subplot(1, 2); p.set_background("black"); cortex(0.08); add(tracts + ["ventricles"])
        cam("xy", "Drogi istoty bialej - z gory")
    p.screenshot(a.out)
    print("podglad ->", a.out)

if __name__ == "__main__":
    main()
