"""
regions.py - target regions drawn by the doctor: "the robot has to go into this area".

How a region is made (no 3D drawing needed):
  1. draw its outline with the mouse on a slice of one view (e.g. axial),
  2. draw its outline on a slice of a second view (e.g. coronal), optionally a third (sagittal).
Each outline is extended through the whole volume along the axis of its view (a prism), and the region is the part
where all prisms overlap (a "visual hull"): the axial outline gives left-right and front-back, the coronal one
adds up-down. With only one outline the region is a thin slab around that slice (slab_mm). By default the region
is also clipped to the brain. Drawing again in the same view replaces that view's outline.

Planning (Planner.region_tip): the tip of the robot may end anywhere inside the region - the planner picks the
point that is easiest to reach safely (kept a little inside the edge when possible); other electrode contacts may
lie in the region as well, the app reports how many.

Outlines are stored in RAS mm (regions.json in the patient folder), so they survive a different crop of the scan;
the region masks are also written as regions/<name>.nii.gz for other tools.
"""
import json, os
import numpy as np
from matplotlib.path import Path

UV_DIMS = {2: (0, 1), 1: (0, 2), 0: (1, 2)}                     # view axis -> volume dims shown as (u, v)
COLOURS = [(1.0, 0.85, 0.0), (0.0, 1.0, 0.8), (1.0, 0.4, 0.0), (0.6, 1.0, 0.2), (0.9, 0.5, 1.0)]
VIEW_NAMES = {2: "axial", 1: "coronal", 0: "sagittal"}


def to_ijk(axis, u, v, k):
    ijk = np.zeros((len(u), 3)); du, dv = UV_DIMS[axis]
    ijk[:, du], ijk[:, dv], ijk[:, axis] = u, v, k
    return ijk


def outline_mask(axis, shape, verts):
    """2D mask of a polygon (u, v vertices) on a slice of this view: array indexed [u, v]."""
    du, dv = UV_DIMS[axis]
    uu, vv = np.meshgrid(np.arange(shape[du]), np.arange(shape[dv]), indexing="ij")
    inside = Path(np.asarray(verts, float)).contains_points(np.c_[uu.ravel(), vv.ravel()])
    return inside.reshape(uu.shape)


class Region:
    def __init__(self, name, colour):
        self.name, self.colour = name, colour
        self.outlines = {}                     # view axis -> (slice index k, vertices N x 2 in (u, v) voxel units)
        self.mask = None

    def set_outline(self, axis, k, verts):
        self.outlines[axis] = (int(k), np.asarray(verts, float))

    def views(self):
        return ", ".join(VIEW_NAMES[a] for a in sorted(self.outlines, reverse=True)) or "no outline yet"

    def build(self, shape, vox, clip=None, slab_mm=2.0):
        """Recompute the 3D mask from the outlines (AND of the prisms); clip: optional boolean volume (brain)."""
        if not self.outlines: self.mask = None; return None
        m = np.ones(shape, bool)
        for axis, (k, verts) in self.outlines.items():
            m &= np.expand_dims(outline_mask(axis, shape, verts), axis)
        if len(self.outlines) == 1:                                 # one view only: a slab around the slice
            axis, (k, _) = next(iter(self.outlines.items()))
            half = max(int(round(slab_mm / vox[axis])), 0)
            keep = np.zeros(shape[axis], bool); keep[max(k - half, 0):k + half + 1] = True
            sh = [1, 1, 1]; sh[axis] = shape[axis]
            m &= keep.reshape(sh)
        if clip is not None: m &= clip
        self.mask = m
        return m

    def volume_ml(self, vox):
        return 0.0 if self.mask is None else float(self.mask.sum() * np.prod(vox) / 1000)

    # ------------------------------------------------------------------ save / load (outlines in RAS mm)
    def to_json(self, vox_to_mm):
        out = {"name": self.name, "colour": list(self.colour), "outlines": []}
        for axis, (k, verts) in self.outlines.items():
            mm = vox_to_mm(to_ijk(axis, verts[:, 0], verts[:, 1], k))
            out["outlines"].append({"view": VIEW_NAMES[axis], "vertices_ras_mm": np.round(mm, 2).tolist()})
        return out

    @staticmethod
    def from_json(d, mm_to_vox):
        r = Region(d["name"], tuple(d.get("colour", COLOURS[0])))
        axis_of = {v: a for a, v in VIEW_NAMES.items()}
        for o in d["outlines"]:
            axis = axis_of[o["view"]]
            ijk = mm_to_vox(np.asarray(o["vertices_ras_mm"], float))
            du, dv = UV_DIMS[axis]
            r.set_outline(axis, int(round(float(np.median(ijk[:, axis])))), ijk[:, [du, dv]])
        return r


def save(folder, regions, vox_to_mm, affine=None):
    json.dump([r.to_json(vox_to_mm) for r in regions.values()], open(os.path.join(folder, "regions.json"), "w"), indent=1)
    if affine is not None:
        import nibabel as nib
        os.makedirs(os.path.join(folder, "regions"), exist_ok=True)
        for r in regions.values():
            if r.mask is not None:
                nib.save(nib.Nifti1Image(r.mask.astype(np.uint8), affine), os.path.join(folder, "regions", f"{r.name}.nii.gz"))


def load(folder, mm_to_vox):
    path = os.path.join(folder, "regions.json")
    if not os.path.exists(path): return {}
    return {d["name"]: Region.from_json(d, mm_to_vox) for d in json.load(open(path))}
