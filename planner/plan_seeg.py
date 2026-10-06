"""
plan_seeg.py - plan SEEG electrodes for a list of targets and write plan.json for the headset app.

Usage:
  python planner/plan_seeg.py --package results/P/package --head results/P/head.nii.gz \
      --headset results/P/headset --targets planner/targets_example.json [--png plan.png]

Targets file (JSON list), each entry one of:
  {"name": "L amygdala", "region": 18}                                  FreeSurfer/DKT label -> centre of the region
  {"name": "L hippocampus head", "region": 17, "part": "anterior"}      anterior / middle / posterior third
  {"name": "my point", "ras": [x, y, z]}                                any point in scanner RAS mm

Output: <headset>/plan.json (RAS mm + headset scene metres), shown by unity/Assets/SeegPlanner/PlanViewer.cs.
"""
import argparse, json, os, sys, time
import numpy as np, nibabel as nib, trimesh
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import trajectory_planner as tp
from export_headset import mask_mesh, head_frame, to_scene

def resolve_targets(spec, seg, aff, F):
    out, regions = {}, {}
    for t in spec:
        if "ras" in t: out[t["name"]] = np.asarray(t["ras"], float); regions[t["name"]] = None; continue
        ijk = np.argwhere(seg == t["region"])
        if not len(ijk): print(f"  [!] {t['name']}: label {t['region']} not found, skipped"); continue
        xyz = nib.affines.apply_affine(aff, ijk)
        part = t.get("part")
        if part:
            ap = xyz @ F[1]; lo, hi = np.percentile(ap, [33.3, 66.7])
            xyz = xyz[{"anterior": ap >= hi, "middle": (ap > lo) & (ap < hi), "posterior": ap <= lo}[part]]
        c = xyz.mean(0)
        out[t["name"]] = xyz[np.argmin(np.linalg.norm(xyz - c, axis=1))]   # nearest point inside the region
        regions[t["name"]] = xyz
    return out, regions

def entry_zone(q, lm_q):
    """Allowed entry points (in the anatomical frame q = lr, ap, si): skull vault and temporal squama,
    not the face, ears or neck."""
    ok = np.ones(len(q), bool)
    if "nasion" in lm_q:
        n = lm_q["nasion"]; ok &= ~((q[:, 1] > n[1] - 35) & (q[:, 2] < n[2] + 15))       # face
        ok &= ~((np.abs(q[:, 0] - n[0]) < 25) & (q[:, 2] < n[2] + 40) & (q[:, 1] > n[1] - 40))  # frontal sinus
        ok &= np.abs(q[:, 0] - n[0]) > 15                                                 # midline: sagittal sinus
    trag = [lm_q[k] for k in ("left_tragus", "right_tragus") if k in lm_q]
    if trag:
        # the floor of the middle cranial fossa is just above the ear canal: entries below it would pass
        # through the skull base or the neck, so they must be at least 5 mm above the tragus
        zmin = max(t[2] for t in trag) + 5; ok &= q[:, 2] > zmin
        for t in trag: ok &= np.linalg.norm(q - t, axis=1) > 30                        # ear
    else:
        ok &= q[:, 2] > q[:, 2].min() + 40
    return ok

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True); ap.add_argument("--head", required=True)
    ap.add_argument("--headset", required=True, help="folder with headset_manifest.json; plan.json is written here")
    ap.add_argument("--targets", required=True); ap.add_argument("--png")
    a = ap.parse_args(); t0 = time.time(); s = tp.Settings()

    man = json.load(open(os.path.join(a.package, "manifest.json")))
    hman = json.load(open(os.path.join(a.headset, "headset_manifest.json")))
    centre = np.array(hman["coordinate_system"]["head_centre_ras_mm"])
    seg_img = nib.load(os.path.join(a.package, "labels.nii.gz")); seg = np.asanyarray(seg_img.dataobj).astype(int)
    head_img = nib.load(a.head); head = ndimage.binary_fill_holes(np.asanyarray(head_img.dataobj) > 0)
    c, F = head_frame(seg, seg_img.affine)

    def lookup(mask, aff):
        inv = np.linalg.inv(aff)
        def f(p):
            i = np.round(nib.affines.apply_affine(inv, p)).astype(int)
            return bool(np.all(i >= 0) and np.all(i < mask.shape) and mask[tuple(i)])
        return f
    head_fn, brain_fn = lookup(head, head_img.affine), lookup(seg > 0, seg_img.affine)

    scalp = mask_mesh(head, head_img.affine)
    v, nrm = scalp.vertices, scalp.vertex_normals
    if np.mean(np.einsum("ij,ij->i", v - v.mean(0), nrm)) < 0: nrm = -nrm          # outward normals
    keep = np.unique(np.floor(v / s.entry_spacing_mm).astype(int), axis=0, return_index=True)[1]
    v, nrm = v[keep], nrm[keep]
    q = (v - c) @ F.T
    lm_q = {k: (np.array(p["ras_mm"]) - c) @ F.T for k, p in hman["landmarks"].items()}
    allowed = entry_zone(q, lm_q)

    targets, regions = resolve_targets(json.load(open(a.targets)), seg, seg_img.affine, F)
    maps = tp.DistanceMaps.from_package(a.package, man)
    shifts = {}
    for k in targets:
        targets[k], shifts[k] = tp.adjust_target(targets[k], regions[k], maps, s)
        if shifts[k] > 0: print(f"  {k}: moved {shifts[k]:.1f} mm inside the region (too close to a critical structure)")
    print(f"{len(targets)} targets, {allowed.sum()} candidate entry points, {len(maps.maps)} distance maps")
    chosen, uncovered, cands = tp.plan(targets, maps, v, nrm, allowed, head_fn, brain_fn, s)

    sc = lambda p: np.round(to_scene(np.asarray(p), centre), 5).tolist()
    out = {"coordinate_system": "entry/tip/contacts in scanner RAS mm (_ras) and headset scene metres (_scene_m)",
           "settings": s.__dict__ | {"electrode_models": list(s.electrode_models)},
           "rules": {k: dict(zip(["hard_min_mm", "soft_scale_mm", "weight", "ignore_near_tip_mm"], r)) for k, r in tp.RULES.items()},
           "targets": {k: {"ras": np.round(p, 2).tolist(), "scene_m": sc(p), "shift_mm": round(shifts[k], 1)} for k, p in targets.items()},
           "uncovered_targets": uncovered,
           "electrodes": []}
    for i, t in enumerate(sorted(chosen, key=lambda t: t.risk)):
        out["electrodes"].append({
            "id": f"E{i + 1}", "targets": t.targets, "electrode": t.electrode,
            "entry_ras": np.round(t.entry, 2).tolist(), "tip_ras": np.round(t.tip, 2).tolist(),
            "entry_scene_m": sc(t.entry), "tip_scene_m": sc(t.tip),
            "contacts_ras": t.contacts, "contacts_scene_m": [sc(p) for p in t.contacts],
            "length_mm": round(t.length_mm, 1), "angle_deg": round(t.angle_deg, 1), "risk": round(t.risk, 3),
            "min_distance_mm": t.min_dist, "warnings": t.warnings,
            "status": "warning" if t.warnings else "ok"})
    out["note"] = "Research prototype - automatic proposal, must be reviewed by the surgical team."
    path = os.path.join(a.headset, "plan.json"); json.dump(out, open(path, "w"), indent=1)

    print(f"{len(chosen)} electrodes for {len(targets)} targets ({len(cands)} candidates), {time.time() - t0:.0f} s -> {path}")
    for e in out["electrodes"]:
        md = e["min_distance_mm"]
        print(f"  {e['id']}: {' + '.join(e['targets'])} | {e['length_mm']} mm, angle {e['angle_deg']} deg, "
              f"vessels {md.get('vessels')} mm, risk {e['risk']} {'| ' + '; '.join(e['warnings']) if e['warnings'] else ''}")
    if uncovered: print("  NOT COVERED (no safe line found):", ", ".join(uncovered))
    if a.png: render(a.package, out, a.png)

def render(package, plan, png):
    import pyvista as pv
    pv.OFF_SCREEN = True
    def mesh(n):
        m = trimesh.load(os.path.join(package, "meshes", f"{n}.glb"), force="mesh")
        return pv.PolyData(np.asarray(m.vertices), np.hstack([np.full((len(m.faces), 1), 3), m.faces]).ravel())
    p = pv.Plotter(off_screen=True, shape=(1, 2), window_size=(1800, 800), border=False)
    for i, view in enumerate(("yz", "xy")):
        p.subplot(0, i); p.set_background("black")
        p.add_mesh(mesh("gray_matter"), color=[0.8, 0.6, 0.6], opacity=0.08)
        for n, col in (("vessels", "red"), ("ventricles", [0.3, 0.55, 1]), ("hippocampus", "gold"), ("amygdala", "orange")):
            if os.path.exists(os.path.join(package, "meshes", f"{n}.glb")): p.add_mesh(mesh(n), color=col, opacity=0.9)
        for e in plan["electrodes"]:
            a_, b_ = np.array(e["entry_ras"]), np.array(e["tip_ras"])
            col = "lime" if e["status"] == "ok" else "yellow"
            p.add_mesh(pv.Tube(pointa=a_, pointb=b_, radius=0.6), color=col)
            for cpt in e["contacts_ras"]: p.add_mesh(pv.Sphere(radius=1.0, center=cpt), color="white")
            p.add_point_labels([a_], [e["id"]], font_size=14, text_color="white", shape_opacity=0.3)
        for k, t in plan["targets"].items(): p.add_mesh(pv.Sphere(radius=2.0, center=t["ras"]), color="magenta")
        getattr(p, f"view_{view}")()
        if view == "yz": p.camera.azimuth = 180
        p.camera.zoom(1.3)
        p.add_text(("Left lateral view" if view == "yz" else "Top view") + " - green: ok, yellow: warning, magenta: targets",
                   font_size=10, color="white")
    p.screenshot(png); print("preview ->", png)

if __name__ == "__main__":
    main()
