"""
export_headset.py - turn a patient package into files for the headset app (Quest 3 now, optical see-through later).

Output (folder --out):
  patient_scene.glb        one glTF 2.0 scene, one named node per layer, colours + transparency,
                           metres, glTF axes (Y up). Loads in Unity (glTFast), three.js, Blender, Windows 3D viewer.
  patient_scene_lite.glb   same scene with a lower triangle budget (for HoloLens 2 / web)
  headset_manifest.json    layers (category, origin: patient / prior / estimate, default visibility),
                           MRI-mm <-> scene transform, alignment landmarks, atlas region centroids
  head_phantom.stl         scalp surface in mm for 3D printing a test phantom (1:1 scale)

Coordinate convention
  MRI: scanner RAS, millimetres (x = right, y = anterior, z = superior)
  scene: glTF (x = right, y = up, z = toward the viewer = posterior), metres, centred on the head
         p_scene = R @ (p_ras - centre) / 1000,   R = [[1,0,0],[0,0,1],[0,-1,0]]  (rotation, det = +1)
  Unity's glTF importer converts to Unity's left-handed axes automatically.

Usage:
  python tools/export_headset.py --package package/ --head head.nii.gz --out headset/
"""
import argparse, json, os
import numpy as np, nibabel as nib, trimesh
from scipy import ndimage
from skimage import measure
from skimage.morphology import ball

R = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)

CATEGORY = {  # layer name prefix -> (category, default visible, default opacity)
    "scalp": ("surface", True, 0.15), "skull": ("surface", False, 0.35), "gray_matter": ("anatomy", True, 0.25),
    "white_matter": ("anatomy", False, 0.3), "cerebellum": ("anatomy", True, 0.35), "csf": ("anatomy", False, 0.2),
    "sulci": ("critical", False, 0.4), "ventricles": ("critical", True, 0.85), "brainstem": ("critical", True, 0.8),
    "vessels": ("critical", True, 1.0), "veins": ("critical", True, 1.0), "sinus": ("critical", True, 1.0),
    "hippocampus": ("target", True, 1.0), "amygdala": ("target", True, 1.0), "thalamus": ("anatomy", False, 0.9),
    "basal_ganglia": ("anatomy", False, 0.9), "eloquent": ("function", False, 0.9),
    "cst": ("tract", False, 0.9), "arcuate": ("tract", False, 0.9), "optic": ("tract", False, 0.9),
    "uncinate": ("tract", False, 0.9), "ifof": ("tract", False, 0.9),
}
ORIGIN = {"veins_prior": "prior: VENAT population atlas registered to patient (not patient-specific)",
          "sinus_sss_prior": "prior: superior sagittal sinus from anatomical rules (not imaged)",
          "skull_t1": "estimate: skull from T1 intensity (no CT)",
          "sulci": "patient (derived from segmentation)",
          "eloquent": "patient anatomy + atlas-based function (no fMRI)"}

# Landmarks chosen to be easy to find again on the real patient (no hair, clear skin features).
TOUCH_ORDER = ["nose_tip", "nasion", "right_inner_eye_corner", "right_outer_eye_corner", "right_tragus",
               "left_inner_eye_corner", "left_outer_eye_corner", "left_tragus"]
HINT = {"nose_tip": "tip of the nose",
        "nasion": "deepest point of the nose bridge, between the eyes",
        "right_inner_eye_corner": "right eye: inner corner (next to the nose), eye closed",
        "right_outer_eye_corner": "right eye: outer corner, eye closed",
        "left_inner_eye_corner": "left eye: inner corner (next to the nose), eye closed",
        "left_outer_eye_corner": "left eye: outer corner, eye closed",
        "right_tragus": "right ear: the small flap in front of the ear canal",
        "left_tragus": "left ear: the small flap in front of the ear canal"}

def meta(name):
    for k, v in CATEGORY.items():
        if name.startswith(k): return v
    return ("other", False, 0.8)

def to_scene(v, centre):
    return ((np.asarray(v) - centre) @ R.T) / 1000.0

def mask_mesh(mask, aff, smooth=10):
    m = ndimage.gaussian_filter(np.pad(mask, 2).astype(np.float32), 1.0)
    v, f, _, _ = measure.marching_cubes(m, 0.5); v -= 2
    mesh = trimesh.Trimesh(nib.affines.apply_affine(aff, v), f, process=True)
    trimesh.smoothing.filter_taubin(mesh, iterations=smooth)
    return mesh

def head_frame(seg, aff):
    """Anatomical axes from the segmentation (robust to head tilt in the scanner):
    lr = left->right hemisphere, ap = occipital->frontal lobe, si = up. Returns centre, (lr, ap, si)."""
    def cen(labels): return nib.affines.apply_affine(aff, np.argwhere(np.isin(seg, labels))).mean(0)
    left, right = cen([2] + list(range(1000, 1036))), cen([41] + list(range(2000, 2036)))
    frontal = cen([1003, 1012, 1014, 1018, 1019, 1020, 1027, 1028, 2003, 2012, 2014, 2018, 2019, 2020, 2027, 2028])
    occipital = cen([1005, 1011, 1013, 1021, 2005, 2011, 2013, 2021])
    lr = right - left; lr /= np.linalg.norm(lr)
    ap = frontal - occipital; ap -= ap.dot(lr) * lr; ap /= np.linalg.norm(ap)
    si = np.cross(lr, ap)
    return cen(list(range(1000, 1036)) + list(range(2000, 2036))), np.stack([lr, ap, si])

def eye_centres(t1_img, head, head_aff, c, F, qa):
    """Eyeball centres (anatomical frame) from T1: the vitreous is a dark-grey ball (darker than tissue,
    brighter than air in the sinuses) surrounded by bright orbital fat."""
    T = np.asanyarray(t1_img.dataobj).astype(np.float32)
    ijk = np.argwhere(head)
    q = (nib.affines.apply_affine(t1_img.affine, ijk) - c) @ F.T
    reg = (np.abs(q[:, 0]) > 18) & (np.abs(q[:, 0]) < 55) & (q[:, 1] < qa[1] - 8) & (q[:, 1] > qa[1] - 55) & \
          (q[:, 2] > qa[2] - 20) & (q[:, 2] < qa[2] + 30)
    sel, qs = ijk[reg], q[reg]
    wm = np.median(T[head & (T > np.percentile(T[head], 60))])          # bright tissue reference
    val = T[tuple(sel.T)]
    m = np.zeros(T.shape, bool); m[tuple(sel[(val > 0.11 * wm) & (val < 0.40 * wm)].T)] = True
    d = ndimage.distance_transform_edt(m, sampling=t1_img.header.get_zooms()[:3]); lab, _ = ndimage.label(m)
    eyes = {}
    for side, sg in (("right", 1), ("left", -1)):
        ss = sel[sg * qs[:, 0] > 0]
        if not len(ss): continue
        i = ss[np.argmax(d[tuple(ss.T)])]
        if d[tuple(i)] < 4: continue                                    # no ball found
        comp = (nib.affines.apply_affine(t1_img.affine, np.argwhere(lab == lab[tuple(i)])) - c) @ F.T
        p0 = (nib.affines.apply_affine(t1_img.affine, i) - c) @ F.T
        eyes[side] = comp[np.linalg.norm(comp - p0, axis=1) < 13].mean(0)
    return eyes

def landmarks(scalp, seg, aff, head=None, head_aff=None, head_vox=(1, 1, 1), t1_img=None):
    """Auto-estimated fiducials on the scalp (RAS mm), found in the head's own anatomical frame.
    Must be verified by the user in the app."""
    c, F = head_frame(seg, aff)
    v = scalp.vertices; q = (v - c) @ F.T                 # columns: lr, ap, si (mm from brain centre)
    pick = lambda m, key: v[m][key(q[m])] if m.any() else None
    # Facial midline profile. The nose is found as the part of the profile that sticks out of the face
    # (vs. the cheeks / orbits 18-24 mm to the side), not as the most anterior point: with the chin
    # tucked in the scanner the forehead can be as far forward as the nose tip.
    zs = np.arange(q[:, 2].min() + 6, q[:, 2].max(), 1.0)  # skip the bottom of the field of view
    prof, prot = np.full(len(zs), np.nan), np.full(len(zs), np.nan)
    for i, z in enumerate(zs):
        Q = q[(q[:, 1] > 0) & (np.abs(q[:, 2] - z) < 0.75)]
        cen, side = Q[np.abs(Q[:, 0]) < 12], Q[(np.abs(Q[:, 0]) > 18) & (np.abs(Q[:, 0]) < 24)]
        if len(cen) and len(side): prof[i] = cen[:, 1].max(); prot[i] = prof[i] - side[:, 1].max()
    face = np.nan_to_num(prot) > 6
    i_tip = int(np.argmax(np.where(face, prof, -np.inf)))
    win = (zs > zs[i_tip] + 10) & (zs < zs[i_tip] + 60) & ~np.isnan(prof)
    i_nas = int(np.argmin(np.where(win, prof, np.inf)))   # deepest point between nose and forehead
    at = lambda i: pick((np.abs(q[:, 0]) < 12) & (np.abs(q[:, 2] - zs[i]) < 0.75), lambda Q: np.argmax(Q[:, 1]))
    nose, nasion = at(i_tip), at(i_nas)
    qa = (nasion - c) @ F.T
    eyes = eye_centres(t1_img, head, head_aff, c, F, qa) if (t1_img is not None and head is not None) else {}
    if len(eyes) == 2:
        # with the eyes known, the nasion is the deepest midline point from eye level to 20 mm above it
        ez = np.mean([e[2] for e in eyes.values()])
        win = (zs > ez - 2) & (zs < ez + 20) & ~np.isnan(prof)
        if win.any(): nasion = at(int(np.argmin(np.where(win, prof, np.inf)))); qa = (nasion - c) @ F.T
    def skin(lr, si):                                     # skin point at a given (left-right, height)
        m = (np.abs(q[:, 0] - lr) < 1.5) & (np.abs(q[:, 2] - si) < 1.5) & (q[:, 1] > 0)
        return v[m][np.argmax(q[m, 1])] if m.any() else None
    corners = {}
    for side, sg in (("right", 1), ("left", -1)):
        if side in eyes:                                  # typical eye: inner corner 16 mm, outer 13 mm from the centre
            e = eyes[side]
            corners[f"{side}_inner_eye_corner"] = skin(e[0] - sg * 16, e[2])
            corners[f"{side}_outer_eye_corner"] = skin(e[0] + sg * 13, e[2] + 2)
    # ears: the pinna is thin, so it disappears when the head mask is opened with a 5 mm ball;
    # the tragus is estimated at the front edge of the pinna, at its mid-height, snapped to the skin
    lpa = rpa = None
    if head is not None:
        thin = head & ~ndimage.binary_opening(head, structure=ball(max(1, int(round(5 / np.mean(head_vox))))))
        thin = ndimage.binary_opening(thin, iterations=1)
        e = (nib.affines.apply_affine(head_aff, np.argwhere(thin)) - c) @ F.T
        region = (np.abs(e[:, 0]) > 50) & (e[:, 1] < qa[1] - 60) & (e[:, 1] > qa[1] - 140) & \
                 (e[:, 2] > qa[2] - 50) & (e[:, 2] < qa[2] + 60)
        def tragus(sign):
            E = e[region & (sign * e[:, 0] > 0)]
            if len(E) < 30: return None
            t = np.array([np.median(E[:, 0]), np.percentile(E[:, 1], 95), np.median(E[:, 2])])
            side = sign * q[:, 0] > 0
            return v[side][np.argmin(np.linalg.norm(q[side] - t, axis=1))]
        lpa, rpa = tragus(-1), tragus(+1)
    out = {"nose_tip": nose, "nasion": nasion, "right_tragus": rpa, "left_tragus": lpa, **corners}
    return {k: out[k] for k in TOUCH_ORDER if out.get(k) is not None}

def build_scene(layers, centre, budget):
    total = sum(len(m.faces) for _, m, _ in layers)
    scale = min(1.0, budget / max(total, 1))
    scene = trimesh.Scene()
    for name, mesh, (cat, vis, op) in layers:
        m = mesh.copy()
        if scale < 1.0 and len(m.faces) > 2000:
            try: m = m.simplify_quadric_decimation(face_count=max(1000, int(len(m.faces) * scale)))
            except Exception: pass
        m.vertices = to_scene(m.vertices, centre)
        rgba = list(mesh.visual.face_colors[0]) if hasattr(mesh.visual, "face_colors") else [200, 200, 200, 255]
        rgba[3] = int(255 * op)
        m.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            name=name, baseColorFactor=[c / 255 for c in rgba], metallicFactor=0.0, roughnessFactor=0.7,
            alphaMode="BLEND" if op < 1.0 else "OPAQUE", doubleSided=True))
        scene.add_geometry(m, node_name=name, geom_name=name)
    return scene, int(sum(len(g.faces) for g in scene.geometry.values()))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True); ap.add_argument("--head", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--t1", help="T1 (e.g. orig.nii.gz) - used to find the eyes for the eye-corner landmarks")
    ap.add_argument("--budget", type=int, default=600000, help="triangle budget, full scene")
    ap.add_argument("--budget_lite", type=int, default=200000, help="triangle budget, lite scene")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    man = json.load(open(os.path.join(a.package, "manifest.json")))
    layers = []
    for L in man["layers"]:
        mesh = trimesh.load(os.path.join(a.package, L["file"]), force="mesh")
        mesh.visual.face_colors = L["rgba"]
        layers.append((L["name"], mesh, meta(L["name"])))

    head_img = nib.load(a.head); head = ndimage.binary_fill_holes(np.asanyarray(head_img.dataobj) > 0)
    scalp = mask_mesh(head, head_img.affine)
    centre = scalp.vertices.mean(0)
    seg_img = nib.load(os.path.join(a.package, "labels.nii.gz"))
    lm = landmarks(scalp, np.asanyarray(seg_img.dataobj).astype(int), seg_img.affine,
                   head, head_img.affine, head_img.header.get_zooms()[:3], nib.load(a.t1) if a.t1 else None)

    full, nf = build_scene(layers, centre, a.budget); full.export(os.path.join(a.out, "patient_scene.glb"))
    lite, nl = build_scene(layers, centre, a.budget_lite); lite.export(os.path.join(a.out, "patient_scene_lite.glb"))
    phantom = scalp.copy()
    if len(phantom.faces) > 200000:                       # keep the print file small (~10 MB)
        phantom = phantom.simplify_quadric_decimation(face_count=200000)
    phantom.fill_holes()
    phantom.export(os.path.join(a.out, "head_phantom.stl"))

    T = np.eye(4); T[:3, :3] = R / 1000.0; T[:3, 3] = -(R @ centre) / 1000.0
    out = {
        "coordinate_system": {"mri": "scanner RAS, mm", "scene": "glTF right-handed, Y up, metres",
                              "ras_mm_to_scene_m": T.round(8).tolist(), "head_centre_ras_mm": centre.round(3).tolist()},
        "layers": [{"name": n, "node": n, "category": c, "visible": v, "opacity": o,
                    "origin": next((t for k, t in ORIGIN.items() if n.startswith(k)), "patient"),
                    "volume_ml": next(L["volume_ml"] for L in man["layers"] if L["name"] == n)}
                   for n, _, (c, v, o) in layers],
        "landmarks": {k: {"ras_mm": np.round(p, 2).tolist(), "scene_m": np.round(to_scene(p, centre), 5).tolist(),
                          "status": "auto-estimated - verify on the model before registration",
                          "touch_hint": HINT[k]} for k, p in lm.items() if p is not None},
        "touch_order": list(lm),
        "region_centroids_scene_m": {k: np.round(to_scene(v, centre), 5).tolist() for k, v in man["region_centroids_mm"].items()},
        "distance_maps": man["critical"],
        "triangles": {"full": nf, "lite": nl},
        "warnings": man.get("warnings", []) + ["Research prototype - not for clinical use."],
    }
    json.dump(out, open(os.path.join(a.out, "headset_manifest.json"), "w"), indent=1)
    print(f"scene: {len(layers)} layers, {nf} triangles (lite {nl}); phantom {len(phantom.faces)} faces, "
          f"watertight={phantom.is_watertight}; landmarks: {', '.join(lm)}")

if __name__ == "__main__":
    main()
