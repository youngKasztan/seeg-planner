"""
patient.py - load a patient folder (output of pipeline/run_pipeline.py) and build the planning fields.

Expected files (paths relative to the patient folder; missing optional files are skipped with a warning):
  orig.nii.gz                         T1 (shown in the slice views, defines the planning grid)
  aparc.DKTatlas+aseg.deep.nii.gz     segmentation (or labels.nii.gz)
  head.nii.gz, mask.nii.gz            head and brain masks
  files named in robot.toml           vessels, tracts, priors ...
  headset/headset_manifest.json       landmarks (entry zone) and headset coordinates (export)

Everything is resampled to the T1 grid, reoriented to RAS (array axes = x right, y anterior, z superior).
"""
import json, os
import numpy as np
import nibabel as nib
from scipy import ndimage

def find(folder, *names):
    for n in names:
        p = os.path.join(folder, n)
        if os.path.exists(p): return p
    return None

class Field:
    """A 3D array on the planning grid, sampled at points in scanner RAS mm (trilinear)."""
    def __init__(self, data, affine, outside):
        self.data, self.affine, self.inv, self.outside = data, affine, np.linalg.inv(affine), outside
    def __call__(self, pts):
        pts = np.asarray(pts, float)
        ijk = nib.affines.apply_affine(self.inv, pts.reshape(-1, 3)).T
        return ndimage.map_coordinates(self.data, ijk, order=1, mode="constant", cval=self.outside).reshape(pts.shape[:-1])

def head_frame(seg, aff):
    """Anatomical axes from the segmentation: lr (left->right), ap (back->front), si (up). Returns centre, F."""
    def cen(labels): return nib.affines.apply_affine(aff, np.argwhere(np.isin(seg, labels))).mean(0)
    left, right = cen([2] + list(range(1000, 1036))), cen([41] + list(range(2000, 2036)))
    frontal = cen([1003, 1012, 1014, 1018, 1019, 1020, 1027, 1028, 2003, 2012, 2014, 2018, 2019, 2020, 2027, 2028])
    occipital = cen([1005, 1011, 1013, 1021, 2005, 2011, 2013, 2021])
    lr = right - left; lr /= np.linalg.norm(lr)
    ap = frontal - occipital; ap -= ap.dot(lr) * lr; ap /= np.linalg.norm(ap)
    return cen(list(range(1000, 1036)) + list(range(2000, 2036))), np.stack([lr, ap, np.cross(lr, ap)])

class Patient:
    def __init__(self, folder, cfg, log=print):
        self.folder, self.cfg, self.log, self.warnings = folder, cfg, log, []
        t1_path = find(folder, "orig.nii.gz", "t1.nii.gz", "T1.nii.gz")
        seg_path = find(folder, "aparc.DKTatlas+aseg.deep.nii.gz", "labels.nii.gz", "package/labels.nii.gz")
        head_path, brain_path = find(folder, "head.nii.gz"), find(folder, "mask.nii.gz")
        if not (t1_path and seg_path and head_path):
            raise FileNotFoundError("patient folder needs orig.nii.gz, aparc.DKTatlas+aseg.deep.nii.gz and head.nii.gz")
        t1 = nib.as_closest_canonical(nib.load(t1_path))
        head_full = self._resample(nib.load(head_path), t1, order=0, full=True) > 0
        # crop to the head (+5 voxels) to save memory and time
        nz = np.argwhere(head_full); lo = np.maximum(nz.min(0) - 5, 0); hi = np.minimum(nz.max(0) + 6, head_full.shape)
        self.crop = (lo, hi)
        A = t1.affine.copy(); A[:3, 3] = nib.affines.apply_affine(t1.affine, lo)
        self.affine, self.vox = A, np.array(t1.header.get_zooms()[:3], float)
        self._t1 = t1
        sl = tuple(slice(a, b) for a, b in zip(lo, hi))
        self.t1 = np.asanyarray(t1.dataobj, dtype=np.float32)[sl]
        self.head = ndimage.binary_fill_holes(head_full[sl])
        self.labels = self._resample(nib.load(seg_path), t1, order=0).astype(np.int32)
        self.brain = (self._resample(nib.load(brain_path), t1, order=0) > 0) if brain_path else self.labels > 0
        self.shape = self.t1.shape
        man = find(folder, "headset/headset_manifest.json", "headset_manifest.json")
        self.headset_manifest = json.load(open(man)) if man else None
        self.headset_dir = os.path.dirname(man) if man else os.path.join(folder, "headset")
        self.frame = head_frame(self.labels, self.affine)
        self.build_fields()

    # ------------------------------------------------------------------ resampling helpers
    def _resample(self, img, ref, order, full=False):
        """Resample img onto the (cropped) reference grid."""
        shape = ref.shape[:3]
        if full: lo, hi, A = np.zeros(3, int), np.array(shape), ref.affine
        else: lo, hi = self.crop; A = ref.affine.copy(); A[:3, 3] = nib.affines.apply_affine(ref.affine, lo)
        M = np.linalg.inv(img.affine) @ A
        data = np.asanyarray(img.dataobj)
        if np.allclose(M, np.eye(4), atol=1e-4) and data.shape[:3] == tuple(shape) and full: return data
        out_shape = tuple(hi - lo)
        if order == 0:
            return ndimage.affine_transform(data, M[:3, :3], M[:3, 3], output_shape=out_shape, order=0, mode="constant")
        f = ndimage.affine_transform(data.astype(np.float32), M[:3, :3], M[:3, 3], output_shape=out_shape, order=1, mode="constant")
        return f

    LEFT = [2, 4, 5, 7, 8, 10, 11, 12, 13, 17, 18, 26, 28, 30, 31] + list(range(1000, 1036))
    RIGHT = [41, 43, 44, 46, 47, 49, 50, 51, 52, 53, 54, 58, 60, 62, 63] + list(range(2000, 2036))

    def midline(self):
        """Surface between the hemispheres (falx, interhemispheric fissure, midline of the corpus callosum and
        3rd ventricle): voxels about equally far from left- and right-hemisphere labels, inside the head.
        A robot never crosses it - each path stays in the hemisphere it enters."""
        if getattr(self, "_midline", None) is None:
            dl = ndimage.distance_transform_edt(~np.isin(self.labels, self.LEFT), sampling=self.vox)
            dr = ndimage.distance_transform_edt(~np.isin(self.labels, self.RIGHT), sampling=self.vox)
            self._midline = (np.abs(dl - dr) <= self.vox.max()) & (np.minimum(dl, dr) < 15.0) & self.head
        return self._midline

    def _mask_from(self, spec, name):
        """Binary mask for a zone spec: labels, mask files, a computed surface, or outside_of a mask."""
        m = np.zeros(self.shape, bool); ok = False
        if "labels" in spec: m |= np.isin(self.labels, spec["labels"]); ok = True
        if spec.get("computed") == "midline": m |= self.midline(); ok = True
        for f in spec.get("mask", []):
            p = os.path.join(self.folder, f)
            if not os.path.exists(p): self.warnings.append(f"{name}: {f} not found - zone skipped"); continue
            img = nib.load(p)
            m |= self._resample(img, self._t1, order=1) > 0.25; ok = True      # keeps thin vessels on a coarser grid
        if "outside_of" in spec:
            p = os.path.join(self.folder, spec["outside_of"])
            inside = (self._resample(nib.load(p), self._t1, order=0) > 0) if os.path.exists(p) else self.brain
            m |= ~inside; ok = True
        return m if ok else None

    # ------------------------------------------------------------------ planning fields
    def build_fields(self):
        cfg, r = self.cfg, self.cfg["robot"]["diameter_mm"] / 2
        self.zone_dist, self.zone_masks = {}, {}
        strict = np.full(self.shape, 1e3, np.float32); ign = strict.copy(); outside = strict.copy()
        for name, z in cfg.get("no_go", {}).items():
            m = self._mask_from(z, name)
            if m is None or not m.any(): continue
            self.log(f"  no-go zone {name}: {m.sum() * self.vox.prod() / 1000:.1f} ml")
            d = ndimage.distance_transform_edt(~m, sampling=self.vox).astype(np.float32)
            self.zone_dist[name] = Field(d, self.affine, 0.0); self.zone_masks[name] = m
            c = d - z["margin_mm"] - r
            if "outside_of" in z: outside = np.minimum(outside, c)
            elif z.get("ignore_near_targets", False): ign = np.minimum(ign, c)
            else: strict = np.minimum(strict, c)
        soft = np.zeros(self.shape, np.float32); self.soft_masks = {}
        for name, z in cfg.get("avoid", {}).items():
            m = self._mask_from(z, name)
            if m is None or not m.any(): continue
            self.log(f"  soft zone {name}: {m.sum() * self.vox.prod() / 1000:.1f} ml")
            d = ndimage.distance_transform_edt(~m, sampling=self.vox).astype(np.float32)
            self.zone_dist[name] = Field(d, self.affine, 50.0); self.soft_masks[name] = m
            soft += z["weight"] * np.exp(-d / z["scale_mm"])
        self.C_strict = Field(strict, self.affine, -10.0)
        self.C_ignorable = Field(ign, self.affine, 1e3)
        self.C_outside = Field(outside, self.affine, -10.0)
        self.soft = Field(soft, self.affine, 0.0)
        self.nogo_union = np.zeros(self.shape, bool)
        for n, m in self.zone_masks.items():
            if "outside_of" not in cfg["no_go"][n]: self.nogo_union |= m
        self.soft_union = np.zeros(self.shape, bool)
        for m in self.soft_masks.values(): self.soft_union |= m

    def sample(self, pts):
        """C_strict, C_ignorable, C_outside and soft at pts (N x 3, RAS mm) with one coordinate transform
        (all four fields share the planning grid). Same values as calling the fields one by one."""
        ijk = nib.affines.apply_affine(self.C_strict.inv, np.asarray(pts, float)).T
        return [ndimage.map_coordinates(f.data, ijk, order=1, mode="constant", cval=f.outside)
                for f in (self.C_strict, self.C_ignorable, self.C_outside, self.soft)]

    def display_mask(self, key, src):
        """Mask of a display layer (cached); None if its file is missing."""
        if not hasattr(self, "_display"): self._display = {}
        if key not in self._display:
            if key == "scalp": self._display[key] = self.head & ~ndimage.binary_erosion(self.head, iterations=2)
            else: self._display[key] = self._mask_from(src, key)
        return self._display[key]

    # ------------------------------------------------------------------ coordinates
    def vox_to_mm(self, ijk): return nib.affines.apply_affine(self.affine, np.asarray(ijk, float))
    def mm_to_vox(self, p): return nib.affines.apply_affine(np.linalg.inv(self.affine), np.asarray(p, float))

    def label_at(self, p):
        i = np.round(self.mm_to_vox(p)).astype(int)
        return int(self.labels[tuple(i)]) if np.all(i >= 0) and np.all(i < self.shape) else 0

    def landmarks_q(self):
        """Headset landmarks in the anatomical frame (for the entry zone)."""
        if not self.headset_manifest: return {}
        c, F = self.frame
        return {k: (np.array(v["ras_mm"]) - c) @ F.T for k, v in self.headset_manifest["landmarks"].items()}
