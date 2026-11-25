"""Tests for path_planner/mri_volume.py (MRI slice volume for the headset)."""
import json, os, sys, tempfile
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "path_planner"))
import mri_volume  # noqa: E402


def test_round_trip_and_axes():
    c = np.array([0.6, 13.0, -27.5])
    ras = np.array([[10.0, 20.0, 30.0], [-5.0, 0.0, 100.0]])
    u = mri_volume.ras_to_unity(ras, c)
    assert np.allclose(mri_volume.unity_to_ras(u, c), ras)
    # +x = patient left (R decreases), +y = superior, +z = posterior (A decreases)
    d = mri_volume.ras_to_unity(c + np.array([-1.0, 0, 0]), c)
    assert np.allclose(d, [0.001, 0, 0])
    assert np.allclose(mri_volume.ras_to_unity(c + np.array([0, 0, 1.0]), c), [0, 0.001, 0])
    assert np.allclose(mri_volume.ras_to_unity(c + np.array([0, -1.0, 0]), c), [0, 0, 0.001])


def test_export_bright_cube_lands_in_the_right_place():
    # 2 mm voxels, RAS-aligned; a bright cube centred at RAS (20, -10, 30)
    t1 = np.full((60, 60, 60), 50.0, np.float32)
    aff = np.diag([2.0, 2.0, 2.0, 1.0]); aff[:3, 3] = [-60, -60, -60]
    centre_vox = ((np.array([20.0, -10.0, 30.0]) - aff[:3, 3]) / 2).astype(int)
    t1[tuple(slice(v - 2, v + 3) for v in centre_vox)] = 200.0
    head = np.ones_like(t1, bool)
    with tempfile.TemporaryDirectory() as d:
        meta = mri_volume.export(d, t1, aff, head, [0.0, 0.0, 0.0], log=lambda *a: None)
        vol = np.fromfile(os.path.join(d, "mri_volume.bytes"), np.uint8).reshape(meta["dims"][::-1])
        kji = np.argwhere(vol > 200).mean(0)                             # centre of the bright cube
        local = np.array(meta["origin_local_m"]) + meta["spacing_m"] * kji[::-1]
        ras = mri_volume.unity_to_ras(local, np.zeros(3))
        assert np.linalg.norm(ras - [20.0, -10.0, 30.0]) < 1.5          # within 1.5 mm of the true centre
        assert json.load(open(os.path.join(d, "mri_volume.json")))["dims"] == meta["dims"]
