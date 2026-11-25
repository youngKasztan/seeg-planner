"""
mri_volume.py - the T1 image for the headset's slice mode (MRI slices shown inside the hologram).

Writes into the patient's headset folder:
  mri_volume.bytes   uint8 voxels, x fastest, then y, then z (C order of an array [k][j][i]):
                       i -> Unity +x (patient LEFT), j -> Unity +y (SUPERIOR), k -> Unity +z (POSTERIOR)
                     1 = darkest inside the head ... 255 = brightest; 0 = outside the head (transparent in the headset)
  mri_volume.json    dims [nx, ny, nz], spacing_m, origin_local_m (PatientRoot local position of voxel 0,0,0),
                     intensity window, source file

Coordinates: the headset loads patient_scene.glb with glTFast, which mirrors glTF x into Unity, so a point in RAS mm
has the PatientRoot local position
    x = -(R - cR) / 1000,   y = (S - cS) / 1000,   z = -(A - cA) / 1000      (c = head_centre_ras_mm)
(glTF scene = export.to_scene = R (p - c) / 1000 with RAS -> (x, y, z) = (R, S, -A); Unity local = (-gx, gy, gz)).
"""
import json, os
import numpy as np
import nibabel as nib
from scipy import ndimage


def unity_to_ras(u, centre):
    """PatientRoot local metres (..., 3) -> RAS mm."""
    u = np.asarray(u, float)
    return np.stack([centre[0] - 1000 * u[..., 0], centre[1] - 1000 * u[..., 2], centre[2] + 1000 * u[..., 1]], -1)


def ras_to_unity(p, centre):
    """RAS mm (..., 3) -> PatientRoot local metres."""
    p = np.asarray(p, float)
    return np.stack([-(p[..., 0] - centre[0]), p[..., 2] - centre[2], -(p[..., 1] - centre[1])], -1) / 1000.0


def export(headset_dir, t1, affine, head, centre, spacing_mm=1.0, margin_mm=3.0, log=print):
    """t1: float array (any orientation) with its vox->RAS `affine`; head: bool mask on the same grid (or None).
    Resamples to a `spacing_mm` grid aligned with the headset axes and writes mri_volume.bytes / .json."""
    centre = np.asarray(centre, float)
    mask = head if head is not None else t1 > np.percentile(t1, 60)
    idx = np.argwhere(mask)
    lo, hi = idx.min(0), idx.max(0)
    corners = np.array([[a, b, c] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for c in (lo[2], hi[2])], float)
    u = ras_to_unity(nib.affines.apply_affine(affine, corners), centre)
    m = margin_mm / 1000.0
    umin, umax = u.min(0) - m, u.max(0) + m
    s = spacing_mm / 1000.0
    dims = np.ceil((umax - umin) / s).astype(int) + 1                  # nx, ny, nz

    lo_t1, hi_t1 = np.percentile(t1[mask], [0.5, 99.5])
    inv = np.linalg.inv(affine)
    out = np.zeros((dims[2], dims[1], dims[0]), np.uint8)              # [k][j][i]
    xs = umin[0] + s * np.arange(dims[0]); ys = umin[1] + s * np.arange(dims[1])
    X, Y = np.meshgrid(xs, ys, indexing="xy")                          # [j][i]
    headf = mask.astype(np.float32)
    for k in range(dims[2]):                                           # one slab at a time (memory)
        Z = np.full_like(X, umin[2] + s * k)
        ras = unity_to_ras(np.stack([X, Y, Z], -1), centre)
        vox = nib.affines.apply_affine(inv, ras.reshape(-1, 3)).T
        v = ndimage.map_coordinates(t1, vox, order=1, cval=0.0).reshape(X.shape)
        h = ndimage.map_coordinates(headf, vox, order=1, cval=0.0).reshape(X.shape) > 0.5
        g = np.clip((v - lo_t1) / max(hi_t1 - lo_t1, 1e-6) * 254.0 + 1.0, 1, 255)
        out[k] = np.where(h, g, 0).astype(np.uint8)

    os.makedirs(headset_dir, exist_ok=True)
    out.tofile(os.path.join(headset_dir, "mri_volume.bytes"))
    meta = {"format": "uint8, x fastest; i -> +x (patient left), j -> +y (superior), k -> +z (posterior); 0 = outside the head",
            "dims": [int(d) for d in dims], "spacing_m": s, "origin_local_m": [round(float(v), 6) for v in umin],
            "intensity_window": [float(lo_t1), float(hi_t1)], "head_centre_ras_mm": [float(c) for c in centre]}
    json.dump(meta, open(os.path.join(headset_dir, "mri_volume.json"), "w"), indent=1)
    log(f"  MRI slice volume written: {dims[0]} x {dims[1]} x {dims[2]} voxels of {spacing_mm:g} mm "
        f"({out.nbytes / 1e6:.1f} MB)")
    return meta


if __name__ == "__main__":                                             # python mri_volume.py <patient folder>
    import sys
    folder = sys.argv[1]
    t1img = nib.as_closest_canonical(nib.load(os.path.join(folder, "orig.nii.gz")))
    head_path = os.path.join(folder, "head.nii.gz")
    head = None
    if os.path.exists(head_path):
        from nibabel.processing import resample_from_to
        head = np.asanyarray(resample_from_to(nib.load(head_path), t1img, order=0).dataobj) > 0
        head = ndimage.binary_fill_holes(head)
    man = json.load(open(os.path.join(folder, "headset", "headset_manifest.json")))
    export(os.path.join(folder, "headset"), np.asanyarray(t1img.dataobj, dtype=np.float32), t1img.affine, head,
           man["coordinate_system"]["head_centre_ras_mm"])
