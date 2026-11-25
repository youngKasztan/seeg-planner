"""
surface.py - triangle surface of a 3D mask (for the 3D view and the headset model).

Uses skimage.measure.marching_cubes when it can be loaded. Windows Smart App Control can block scikit-image's compiled
modules; then a pure-NumPy fallback is used: the faces between inside and outside voxels (a blocky surface that the
callers smooth anyway). Vertices are in voxel index coordinates, like marching_cubes.
"""
import numpy as np

try:
    from skimage import measure as _measure
    BACKEND = "marching_cubes"
except ImportError:
    _measure = None
    BACKEND = "voxel_faces"


def marching_cubes(volume, level=0.5):
    """(vertices N x 3 in voxel coordinates, faces M x 3) of the iso-surface volume == level."""
    if _measure is not None:
        v, f, _, _ = _measure.marching_cubes(volume, level)
        return v, f
    return voxel_faces(np.asarray(volume) > level)


def voxel_faces(mask):
    """Surface made of the square faces between inside and outside voxels (2 triangles each), outward normals."""
    m = np.pad(np.asarray(mask, bool), 1)
    quads = []                                                   # 4 corner points (x2, integers) per face
    for ax in range(3):
        a, b = [slice(None)] * 3, [slice(None)] * 3
        a[ax], b[ax] = slice(0, -1), slice(1, None)
        ma, mb = m[tuple(a)], m[tuple(b)]
        u, w = [d for d in range(3) if d != ax]
        for sign, sel in ((+1, ma & ~mb), (-1, ~ma & mb)):       # +1: inside -> outside along +ax
            idx = np.argwhere(sel)
            if not len(idx): continue
            c = 2 * idx + 1; c[:, ax] += 1                         # face centre between voxel i and i+1, doubled
            corners = []
            for du, dw in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = c.copy(); p[:, u] += du; p[:, w] += dw; corners.append(p)
            if (sign > 0) == (ax == 1):                            # winding so that the normal points outwards
                corners = corners[::-1]
            quads.append(np.stack(corners, 1))
    if not quads: return np.zeros((0, 3)), np.zeros((0, 3), int)
    q = np.concatenate(quads)                                    # (F, 4, 3)
    verts, inv = np.unique(q.reshape(-1, 3), axis=0, return_inverse=True)
    inv = inv.reshape(-1, 4)
    faces = np.concatenate([inv[:, [0, 1, 2]], inv[:, [0, 2, 3]]])
    return verts / 2.0 - 1.5, faces                              # undo doubling and padding; voxel i spans i +/- 0.5
