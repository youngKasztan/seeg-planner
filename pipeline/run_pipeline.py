"""
run_pipeline.py - jedno polecenie: surowe badania pacjenta -> gotowy pakiet mozgu do planowania SEEG.

Uzycie:
  python pipeline/run_pipeline.py --t1 T1.nii.gz [--mra MRA.nii.gz] [--truth vessels_expert.nii.gz] \
      --out wyniki/IXI057 --fastsurfer /sciezka/do/FastSurfer [--device cpu|cuda]

Kroki (kazdy pomijany, jesli jego wynik juz istnieje - mozna wznawiac):
  1. segmentacja T1 (FastSurfer)            -> seg/aparc.DKTatlas+aseg.deep.nii.gz, mask.nii.gz, orig.nii.gz
  2. maska glowy                            -> head.nii.gz
  3. tetnice z MRA (jesli podane)           -> vessels_auto.nii.gz (+ raport vs eksperci, jesli --truth)
  4. pakiet warstw (siatki, mapy odleglosci)-> package/
  5. podglad PNG                            -> preview.png
"""
import argparse, os, subprocess, sys
import numpy as np, nibabel as nib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def run(cmd, env=None):
    print("\n$ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)

def mgz_to_nii(src, dst):
    i = nib.load(src); nib.save(nib.Nifti1Image(np.asanyarray(i.dataobj), i.affine), dst)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--t1", required=True); ap.add_argument("--mra"); ap.add_argument("--truth")
    ap.add_argument("--dti_dir", help="folder z wolumenami DTI (*DTI-*.nii.gz)"); ap.add_argument("--bvals"); ap.add_argument("--bvecs")
    ap.add_argument("--t1_gd", help="T1 po kontrascie -> zyly i zatoki"); ap.add_argument("--ct", help="CT -> kosc, skora")
    ap.add_argument("--ct_postimplant", action="store_true", help="CT po implantacji -> kontakty elektrod")
    ap.add_argument("--out", required=True); ap.add_argument("--fastsurfer", required=True)
    ap.add_argument("--device", default="cpu"); ap.add_argument("--threads", default="2")
    a = ap.parse_args()
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    seg = os.path.join(out, "aparc.DKTatlas+aseg.deep.nii.gz")

    # 1. segmentacja
    if not os.path.exists(seg):
        env = dict(os.environ, PYTHONPATH=a.fastsurfer)
        run([sys.executable, os.path.join(a.fastsurfer, "FastSurferCNN", "run_prediction.py"),
             "--t1", os.path.abspath(a.t1), "--sd", out, "--sid", "fastsurfer",
             "--device", a.device, "--viewagg_device", "cpu" if a.device == "cpu" else "auto",
             "--batch_size", "1", "--threads", a.threads], env=env)
        mri = os.path.join(out, "fastsurfer", "mri")
        mgz_to_nii(os.path.join(mri, "aparc.DKTatlas+aseg.deep.mgz"), seg)
        mgz_to_nii(os.path.join(mri, "mask.mgz"), os.path.join(out, "mask.nii.gz"))
        mgz_to_nii(os.path.join(mri, "orig.mgz"), os.path.join(out, "orig.nii.gz"))

    # 2. maska glowy
    head = os.path.join(out, "head.nii.gz")
    if not os.path.exists(head):
        run([sys.executable, os.path.join(HERE, "head_mask.py"), "--t1", os.path.join(out, "orig.nii.gz"), "--out", head])

    # 3. tetnice
    vessels = os.path.join(out, "vessels_auto.nii.gz")
    if a.mra and not os.path.exists(vessels):
        cmd = [sys.executable, os.path.join(HERE, "vessels_mra.py"), "--mra", a.mra, "--t1", os.path.join(out, "orig.nii.gz"),
               "--brainmask", os.path.join(out, "mask.nii.gz"), "--out", vessels, "--report", os.path.join(out, "vessels_report.json")]
        if a.truth: cmd += ["--truth", a.truth]
        run(cmd)

    extra = []
    # 3b. drogi istoty bialej
    if a.dti_dir:
        tdir = os.path.join(out, "tracts")
        if not os.path.exists(os.path.join(tdir, "tracts_report.json")):
            run([sys.executable, os.path.join(HERE, "tracts_dti.py"), "--dti_dir", a.dti_dir, "--bvals", a.bvals,
                 "--bvecs", a.bvecs, "--t1", os.path.join(out, "orig.nii.gz"), "--seg", seg, "--out", tdir])
        for f in sorted(os.listdir(tdir)):
            if f.endswith(".nii.gz") and not f.startswith("fa_"):
                extra += ["--layer", f"{f[:-7]}:{os.path.join(tdir, f)}:critical"]
    # 3c. zyly i zatoki
    if a.t1_gd:
        vdir = os.path.join(out, "veins")
        cmd = [sys.executable, os.path.join(HERE, "veins_ct1.py"), "--pre", os.path.join(out, "orig.nii.gz"),
               "--post", a.t1_gd, "--seg", seg, "--out", vdir]
        if os.path.exists(vessels): cmd += ["--arteries", vessels]
        run(cmd)
        extra += ["--layer", f"veins:{vdir}/veins.nii.gz:critical", "--layer", f"sinuses:{vdir}/sinuses.nii.gz:critical"]
    # 3d. CT
    if a.ct:
        cdir = os.path.join(out, "ct")
        cmd = [sys.executable, os.path.join(HERE, "ct_layers.py"), "--ct", a.ct, "--t1", os.path.join(out, "orig.nii.gz"), "--out", cdir]
        if a.ct_postimplant: cmd.append("--postimplant")
        run(cmd)
        extra += ["--layer", f"skull:{cdir}/skull.nii.gz"]

    # 4. pakiet
    pkg = os.path.join(out, "package")
    cmd = [sys.executable, os.path.join(HERE, "seeg_prep.py"), "--seg", seg, "--head", head,
           "--brainmask", os.path.join(out, "mask.nii.gz"), "--out", pkg]
    if os.path.exists(vessels): cmd += ["--vessels", vessels]
    run(cmd + extra)

    # 5. podglad
    run([sys.executable, os.path.join(ROOT, "tools", "render_preview.py"), "--package", pkg, "--out", os.path.join(out, "preview.png")])
    print("\nGOTOWE ->", out)

if __name__ == "__main__":
    main()
