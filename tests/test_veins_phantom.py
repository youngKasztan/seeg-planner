"""Test veins_ct1.py on a phantom: T1 before/after contrast. After contrast a 'sinus'
(8 mm tube on the midline) and a 'vein' (2 mm tube) enhance. Check they land in the right layers."""
import os, sys, json, subprocess, tempfile
import numpy as np, nibabel as nib
HERE = os.path.dirname(os.path.abspath(__file__)); tmp = tempfile.mkdtemp()
n = 128; g = np.mgrid[:n, :n, :n].astype(np.float32) - n / 2; r = np.sqrt((g ** 2).sum(0))
rng = np.random.default_rng(0)
seg = np.zeros((n, n, n), np.int16); seg[r < 45] = 2
pre = np.where(r < 50, 1.0, 0.05).astype(np.float32) + rng.normal(0, 0.02, (n, n, n)).astype(np.float32)
post = pre.copy()
sinus = (np.sqrt(g[0] ** 2 + (g[2] - 47) ** 2) < 4) & (np.abs(g[1]) < 40)      # along the y axis, above the brain
vein = (np.sqrt((g[0] - 20) ** 2 + (g[2] - 10) ** 2) < 1) & (np.abs(g[1]) < 30)
post[sinus] += 1.5; post[vein] += 1.0
aff = np.eye(4); aff[:3, 3] = -n / 2
for a, nm in ((pre, "pre"), (post, "post"), (seg, "seg")): nib.save(nib.Nifti1Image(a, aff), f"{tmp}/{nm}.nii.gz")
subprocess.run([sys.executable, os.path.join(HERE, "..", "pipeline", "veins_ct1.py"), "--pre", f"{tmp}/pre.nii.gz",
                "--post", f"{tmp}/post.nii.gz", "--seg", f"{tmp}/seg.nii.gz", "--out", f"{tmp}/o"], check=True)
S = np.asanyarray(nib.load(f"{tmp}/o/sinuses.nii.gz").dataobj) > 0
V = np.asanyarray(nib.load(f"{tmp}/o/veins.nii.gz").dataobj) > 0
hs = (S & sinus).sum() / sinus.sum(); hv = (V & vein).sum() / vein.sum()
print(f"sinus detected {hs:.0%}, vein detected {hv:.0%}, false sinus voxels outside the tube: {(S & ~sinus).sum()}")
assert hs > 0.5 and hv > 0.3
print("OK")
