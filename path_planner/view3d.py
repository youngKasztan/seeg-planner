"""
view3d.py - 3D view of the app (brain, zones, targets, paths) drawn with pyqtgraph + OpenGL.

pyqtgraph and PyOpenGL are pure Python; they draw through the system OpenGL driver and Qt (PySide6).
The earlier view used VTK (pyvista), whose unsigned DLLs are blocked by Windows Smart App Control.

Mouse: left drag = rotate, right drag or wheel = zoom, middle drag (or Ctrl + left drag) = move.
Slice planes: the axial, coronal and sagittal slices shown in the other three views are drawn as almost transparent
coloured planes with a thin frame (button "Slices" switches them off); they move with the cursor and the sliders.
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
        self.btn_planes = QtWidgets.QToolButton(); self.btn_planes.setText("Slices"); self.btn_planes.setCheckable(True)
        self.btn_planes.setChecked(True); self.btn_planes.setToolTip("Show where the three slices of the other views are")
        self.btn_planes.toggled.connect(self._planes_toggled); bar.addWidget(self.btn_planes)
        for text, view in (("Front", "front"), ("Left", "left"), ("Right", "right"), ("Top", "top")):
            b = QtWidgets.QToolButton(); b.setText(text); b.clicked.connect(lambda _=False, v=view: self.set_view(v)); bar.addWidget(b)
        lay = QtWidgets.QVBoxLayout(self); lay.setContentsMargins(2, 2, 2, 2); lay.setSpacing(2)
        lay.addLayout(bar); lay.addWidget(self.gl, 1)
        self.centre, self.size = np.zeros(3), 200.0
        self._planes = []                                          # last [(name, corners 4 x 3 mm, colour)]

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

    # ------------------------------------------------------------------ slice planes
    PLANE_FILL, PLANE_FRAME = 0.07, 0.6                           # opacity of the plane and of its frame

    def set_slice_planes(self, planes):
        """planes: [(name, corners (4 x 3, mm, in order around the plane), colour)]. Updated in place (cheap),
        so it can be called on every cursor move."""
        self._planes = planes
        if not self.btn_planes.isChecked(): return
        for name, corners, col in planes:
            c = np.asarray(corners, np.float32)
            fill, frame = self.items.get("PLANE_" + name), self.items.get("PLANEF_" + name)
            faces = np.array([[0, 1, 2], [0, 2, 3]], np.uint32)
            loop = np.vstack([c, c[:1]])
            if fill is None:
                fill = gl.GLMeshItem(meshdata=gl.MeshData(vertexes=c, faces=faces), smooth=False, shader=None,
                                     color=(*col, self.PLANE_FILL), drawEdges=False)
                fill.setGLOptions(SEE_THROUGH); fill.setDepthValue(15)
                self._put("PLANE_" + name, fill)
                frame = gl.GLLinePlotItem(pos=loop, color=(*col, self.PLANE_FRAME), width=1.5, antialias=True,
                                          mode="line_strip")
                frame.setGLOptions(SEE_THROUGH); frame.setDepthValue(16)
                self._put("PLANEF_" + name, frame)
            else:
                fill.setMeshData(vertexes=c, faces=faces)
                frame.setData(pos=loop)

    def _planes_toggled(self, on):
        if on: self.set_slice_planes(self._planes)
        else:
            for name in [n for n in self.items if n.startswith(("PLANE_", "PLANEF_"))]: self.remove(name)

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
    import surface
    m = ndimage.zoom(mask.astype(np.float32), 1 / step, order=1) if step > 1 else mask.astype(np.float32)
    if m.max() < 0.5: return None
    vv, ff = surface.marching_cubes(np.pad(m, 1), 0.5)
    return affine_fn((vv - 1) * step), ff
