"""
view3d.py - 3D view of the app (brain, zones, targets, paths) drawn with pyqtgraph + OpenGL.

pyqtgraph and PyOpenGL are pure Python; they draw through the system OpenGL driver and Qt (PySide6).
The earlier view used VTK (pyvista), whose unsigned DLLs are blocked by Windows Smart App Control.

Mouse: left drag = rotate, right drag or wheel = zoom, middle drag (or Ctrl + left drag) = move.
"""
import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from PySide6 import QtCore, QtWidgets


from OpenGL import GL
SEE_THROUGH = {GL.GL_DEPTH_TEST: True, GL.GL_BLEND: True, GL.GL_ALPHA_TEST: False, GL.GL_CULL_FACE: False,
               "glBlendFunc": (GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA), "glDepthMask": (GL.GL_FALSE,)}
OPAQUE = {GL.GL_DEPTH_TEST: True, GL.GL_BLEND: False, GL.GL_ALPHA_TEST: False, GL.GL_CULL_FACE: False,
          "glDepthMask": (GL.GL_TRUE,)}


class _GLView(gl.GLViewWidget):
    def paintGL(self, *a, **k):
        GL.glDepthMask(GL.GL_TRUE)          # see-through items switch depth writes off; without this the depth
        super().paintGL(*a, **k)            # buffer is not cleared for the next frame and meshes turn black


class View3D(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gl = _GLView()
        self.gl.setBackgroundColor((0, 0, 0, 255))
        self.items = {}                                             # name -> GL item
        bar = QtWidgets.QHBoxLayout(); bar.setContentsMargins(2, 2, 2, 0)
        lab = QtWidgets.QLabel("3D"); lab.setStyleSheet("color: white; font-weight: bold"); bar.addWidget(lab)
        bar.addStretch(1)
        for text, view in (("Front", "front"), ("Left", "left"), ("Right", "right"), ("Top", "top")):
            b = QtWidgets.QToolButton(); b.setText(text); b.clicked.connect(lambda _=False, v=view: self.set_view(v)); bar.addWidget(b)
        lay = QtWidgets.QVBoxLayout(self); lay.setContentsMargins(2, 2, 2, 2); lay.setSpacing(2)
        lay.addLayout(bar); lay.addWidget(self.gl, 1)
        self.centre, self.size = np.zeros(3), 200.0

    # ------------------------------------------------------------------ items
    def _put(self, name, item):
        self.remove(name)
        self.items[name] = item; self.gl.addItem(item)

    def remove(self, name):
        it = self.items.pop(name, None)
        if it is not None: self.gl.removeItem(it)

    def clear(self):
        for name in list(self.items): self.remove(name)

    def add_mesh(self, name, verts, faces, colour, opacity):
        """Triangle mesh (verts N x 3 in mm, faces M x 3). Opaque meshes are lit; see-through ones are drawn after them."""
        md = gl.MeshData(vertexes=np.asarray(verts, np.float32), faces=np.asarray(faces, np.uint32))
        see_through = opacity < 0.99
        item = gl.GLMeshItem(meshdata=md, smooth=True, shader="shaded", color=(*colour, opacity))
        # see-through meshes: blended, drawn after the opaque ones and NOT writing depth,
        # so they never hide what lies inside them (e.g. the brain surface over the ventricles)
        item.setGLOptions(SEE_THROUGH if see_through else OPAQUE)
        item.setDepthValue(10 if see_through else 0)
        self._put(name, item)

    def add_points(self, name, pts, colour, size=14):
        pts = np.atleast_2d(np.asarray(pts, np.float32))
        item = gl.GLScatterPlotItem(pos=pts, color=(*colour, 1.0), size=size, pxMode=True)
        item.setGLOptions(OPAQUE); item.setDepthValue(20)
        self._put(name, item)

    def add_line(self, name, pts, colour, width=4):
        item = gl.GLLinePlotItem(pos=np.asarray(pts, np.float32), color=(*colour, 1.0), width=width, antialias=True, mode="line_strip")
        item.setGLOptions(OPAQUE); item.setDepthValue(5)
        self._put(name, item)

    # ------------------------------------------------------------------ camera
    def fit(self, pts):
        """Centre the camera on these points (N x 3 mm)."""
        pts = np.asarray(pts, float)
        lo, hi = pts.min(0), pts.max(0)
        self.centre, self.size = (lo + hi) / 2, float(np.linalg.norm(hi - lo))
        self.set_view("front")

    def set_view(self, view):
        az, el = {"front": (90, 0), "left": (180, 0), "right": (0, 0), "top": (90, 90)}[view]
        self.gl.opts["center"] = pg.Vector(*self.centre)
        self.gl.setCameraPosition(distance=self.size * 1.3, elevation=el, azimuth=az)


def mesh_from_mask(mask, affine_fn, step=1):
    """Marching cubes of a binary mask; step > 1 makes a coarser (lighter) mesh. Returns (verts mm, faces) or None."""
    from scipy import ndimage
    from skimage import measure
    m = ndimage.zoom(mask.astype(np.float32), 1 / step, order=1) if step > 1 else mask.astype(np.float32)
    if m.max() < 0.5: return None
    vv, ff, _, _ = measure.marching_cubes(np.pad(m, 1), 0.5)
    return affine_fn((vv - 1) * step), ff
