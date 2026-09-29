"""Test ct_layers.py na syntetycznym fantomie CT (bez danych pacjenta):
glowa = kula HU 40, czaszka = skorupa HU 1000 (grubosc 6 mm), 2 elektrody = 8 kontaktow HU 3000."""
import os, sys, json, subprocess, tempfile
import numpy as np, nibabel as nib
HERE = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
n, vox = 160, 1.0
g = np.mgrid[:n, :n, :n].astype(np.float32) - n / 2
r = np.sqrt((g ** 2).sum(0))
hu = np.full((n, n, n), -1000, np.float32)
hu[r < 75] = 40; hu[(r >= 66) & (r < 72)] = 1000
for k in range(8):                      # elektroda wzdluz osi x, kontakty co 5 mm
    hu[40 + 5 * k:42 + 5 * k, 79:81, 79:81] = 3000
aff = np.diag([vox, vox, vox, 1]); aff[:3, 3] = -n / 2
nib.save(nib.Nifti1Image(hu, aff), f"{tmp}/ct.nii.gz")
subprocess.run([sys.executable, os.path.join(HERE, "..", "pipeline", "ct_layers.py"), "--ct", f"{tmp}/ct.nii.gz",
                "--t1", f"{tmp}/ct.nii.gz", "--out", f"{tmp}/out", "--no_register", "--postimplant"], check=True)
rep = json.load(open(f"{tmp}/out/ct_report.json"))
contacts = json.load(open(f"{tmp}/out/contacts.json"))
p50 = rep["skull_thickness_mm_p50_p95"][0]
print("grubosc kosci p50:", p50, "mm (oczekiwane ~3-6)  kontakty:", len(contacts), "(oczekiwane 8)")
assert 2 <= p50 <= 7 and len(contacts) == 8
print("OK")
