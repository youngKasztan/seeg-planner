"""
app.py - Continuum robot path planner (desktop app, Windows/Linux/macOS).

  1. Open patient folder   (output of pipeline/run_pipeline.py, e.g. dataMedical/IXI057/results)
  2. Scroll through the slices (mouse wheel), LEFT click = add a target, RIGHT click = move the cursor
  3. Plan paths            (robot constraints and no-go zones: robot.toml next to the program)
  4. Export to headset     (plan.json + paths.glb into the patient's headset folder)

Run:  python path_planner/app.py [patient_folder]
Self-test without a window:  python path_planner/app.py --selftest patient_folder
"""
import json, os, sys, traceback
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config, labels, layers
from patient import Patient
from planner import Planner, Cancelled
import export, electrode, regions

from PySide6 import QtCore, QtGui, QtWidgets
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.widgets import LassoSelector

APP_NAME = "Continuum Path Planner"
PATH_COLOURS = export.COLOURS

# ---------------------------------------------------------------------------------------------- workers
class Worker(QtCore.QThread):
    """Runs a function in the background; reports log lines and progress.
    The function never touches widgets: it only emits signals, which Qt delivers to the main thread."""
    log = QtCore.Signal(str)
    progress = QtCore.Signal(float, str)
    done = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    cancelled = QtCore.Signal()

    def __init__(self, fn):
        super().__init__(); self.fn = fn; self.stop_requested = False

    def stop(self): self.stop_requested = True

    def run(self):
        try: self.done.emit(self.fn(self.log.emit, lambda f, m="": self.progress.emit(float(f), str(m))))
        except Cancelled: self.cancelled.emit()
        except Exception: self.failed.emit(traceback.format_exc())

# ---------------------------------------------------------------------------------------------- slice view
class SliceView(QtWidgets.QWidget):
    """One slice orientation. axis 2 = axial, 1 = coronal, 0 = sagittal (array is RAS)."""
    clicked = QtCore.Signal(int, object, bool)        # axis, voxel index (3,), add_target?
    TITLES = {2: "Axial", 1: "Coronal", 0: "Sagittal"}

    def __init__(self, axis, parent=None):
        super().__init__(parent)
        self.axis, self.app = axis, parent
        self.fig = Figure(figsize=(4, 4), facecolor="black"); self.canvas = FigureCanvasQTAgg(self.fig)
        self.ax = self.fig.add_axes([0, 0, 1, 1]); self.ax.set_facecolor("black"); self.ax.axis("off")
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.label = QtWidgets.QLabel(self.TITLES[axis]); self.label.setStyleSheet("color: white; font-weight: bold")
        lay = QtWidgets.QVBoxLayout(self); lay.setContentsMargins(2, 2, 2, 2); lay.setSpacing(2)
        top = QtWidgets.QHBoxLayout(); top.addWidget(self.label); top.addWidget(self.slider, 1); lay.addLayout(top)
        lay.addWidget(self.canvas, 1)
        self.slider.valueChanged.connect(self._slider)
        self.canvas.mpl_connect("scroll_event", self._scroll)
        self.canvas.mpl_connect("button_press_event", self._press)
        self.img = self.ov = None
        self.artists = []
        # outline drawing for target regions (active only while 'Draw outline' is on)
        self.lasso = LassoSelector(self.ax, self._lasso_done, useblit=False, button=1,
                                   props=dict(color="yellow", linewidth=1.5))
        self.lasso.set_active(False)

    def _lasso_done(self, verts):
        if len(verts) >= 3: self.app.region_outline(self.axis, self.slider.value(), np.asarray(verts, float))

    def setup(self, shape):
        self.slider.blockSignals(True); self.slider.setRange(0, shape[self.axis] - 1); self.slider.blockSignals(False)

    def take(self, vol, k):
        if self.axis == 2: return vol[:, :, k].T
        if self.axis == 1: return vol[:, k, :].T
        return vol[k, :, :].T

    def uv(self, ijk):
        """2D display coordinates of voxel indices (N x 3) and their depth along this axis."""
        ijk = np.atleast_2d(ijk)
        if self.axis == 2: return ijk[:, 0], ijk[:, 1], ijk[:, 2]
        if self.axis == 1: return ijk[:, 0], ijk[:, 2], ijk[:, 1]
        return ijk[:, 1], ijk[:, 2], ijk[:, 0]

    def to_ijk(self, u, v, k):
        if self.axis == 2: return np.array([u, v, k])
        if self.axis == 1: return np.array([u, k, v])
        return np.array([k, u, v])

    def _slider(self, k):
        c = self.app.cursor.copy(); c[self.axis] = k; self.app.set_cursor(c)

    def _scroll(self, ev):
        step = 5 if (ev.key == "shift") else 1
        self.slider.setValue(self.slider.value() + (step if ev.button == "up" else -step))

    def _press(self, ev):
        if ev.inaxes is None or ev.xdata is None or self.app.drawing(): return
        ijk = self.to_ijk(ev.xdata, ev.ydata, self.slider.value())
        self.clicked.emit(self.axis, ijk, ev.button == 1)

    def redraw(self):
        a = self.app; p = a.patient
        if p is None: return
        k = int(a.cursor[self.axis]); self.slider.blockSignals(True); self.slider.setValue(k); self.slider.blockSignals(False)
        self.label.setText(f"{self.TITLES[self.axis]}  {k + 1}/{p.shape[self.axis]}")
        sl = self.take(a.t1n, k)
        if self.img is None:
            self.ax.clear(); self.ax.axis("off")
            self.img = self.ax.imshow(sl, cmap="gray", origin="lower", vmin=0, vmax=1, interpolation="bilinear")
            self.ov = self.ax.imshow(np.zeros(sl.shape + (4,)), origin="lower", interpolation="nearest")
            h, w = sl.shape
            for txt, x in (("R", w - 12), ("L", 4)) if self.axis != 0 else (("A", w - 12), ("P", 4)):
                self.ax.text(x, h - 14, txt, color="#8cf", fontsize=11, weight="bold")
        self.img.set_data(sl)
        o = np.zeros(sl.shape + (4,), np.float32)                  # all ticked layers, in list order
        for key, mask, col, alpha in a.visible_layers():
            m = self.take(mask, k); o[m] = (*col, alpha)
        for r in a.regions.values():                                # target regions on top of the layers
            if r.mask is not None: o[self.take(r.mask, k)] = (*r.colour, 0.45)
        self.ov.set_data(o)
        for art in self.artists: art.remove()
        self.artists = []
        for r in a.regions.values():                                # the outline drawn on this slice
            if self.axis in r.outlines and r.outlines[self.axis][0] == k:
                vt = r.outlines[self.axis][1]
                self.artists += self.ax.plot(np.r_[vt[:, 0], vt[:1, 0]], np.r_[vt[:, 1], vt[:1, 1]], color=r.colour, lw=1.5)
        u, v, _ = self.uv(a.cursor)
        self.artists += [self.ax.axvline(u[0], color="#2a6", lw=0.6, alpha=0.6), self.ax.axhline(v[0], color="#2a6", lw=0.6, alpha=0.6)]
        if a.chk_paths.isChecked():
            for i, r in enumerate(a.paths):
                ijk = p.mm_to_vox(r.points); pu, pv, d = self.uv(ijk); col = PATH_COLOURS[i % len(PATH_COLOURS)]
                self.artists += self.ax.plot(pu, pv, color=col, lw=1, alpha=0.35)
                near = np.abs(d - k) <= 2.0
                if near.any():
                    self.artists += self.ax.plot(np.where(near, pu, np.nan), np.where(near, pv, np.nan), color=col, lw=3)
                if a.chk_contacts.isChecked():                     # electrode contacts on this slice
                    c = electrode.for_path(r, a.cfg, a.plan_targets())
                    if len(c.centres):
                        cu, cv, cd = self.uv(p.mm_to_vox(c.centres))
                        on = np.abs(cd - k) <= 2.0
                        hit = np.isin(np.arange(len(cu)), list(c.hits))
                        sets = ((~on & ~hit, dict(s=8, marker="o", facecolors="white", edgecolors="none", alpha=0.45, zorder=3)),
                                (on & ~hit, dict(s=26, marker="s", facecolors=col, edgecolors="white", linewidths=0.8, zorder=4)),
                                (~on & hit, dict(s=40, marker="o", facecolors="none", edgecolors="#3f3", linewidths=1.0, alpha=0.6, zorder=6)),
                                (on & hit, dict(s=90, marker="o", facecolors="none", edgecolors="#3f3", linewidths=2.0, zorder=7)))
                        for m, style in sets:                      # faint = contact on another slice, bold = on this slice
                            if m.any(): self.artists.append(self.ax.scatter(cu[m], cv[m], **style))
        for n, t in a.region_tips.items():                          # tip chosen inside a region (after planning)
            tu, tv, td = self.uv(p.mm_to_vox(t)); inside = abs(td[0] - k) <= 2
            col = a.regions[n].colour if n in a.regions else (1, 1, 0)
            self.artists.append(self.ax.scatter(tu, tv, s=110 if inside else 30, marker="*", facecolors=col if inside else "none",
                                                edgecolors=col, linewidths=1.2, zorder=5))
            if inside: self.artists.append(self.ax.text(tu[0] + 4, tv[0] + 4, n, color=col, fontsize=8, zorder=6))
        for n, t in a.targets.items():
            tu, tv, td = self.uv(p.mm_to_vox(t)); inside = abs(td[0] - k) <= 2
            sel = a.current_target() == n
            self.artists.append(self.ax.scatter(tu, tv, s=90 if inside else 25, facecolors="magenta" if inside else "none",
                                                edgecolors="yellow" if sel else "magenta", linewidths=1.5, zorder=5))
            if inside: self.artists.append(self.ax.text(tu[0] + 4, tv[0] + 4, n, color="magenta", fontsize=8, zorder=6))
        self.canvas.draw_idle()

# ---------------------------------------------------------------------------------------------- main window
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, folder=None):
        super().__init__()
        self.setWindowTitle(APP_NAME); self.resize(1500, 950)
        self.cfg = config.load(); self.patient = self.planner = None
        self.targets, self.paths, self.uncovered, self.cursor = {}, [], [], np.zeros(3, int)
        self.regions, self.region_tips = {}, {}                    # name -> regions.Region; name -> tip chosen by the planner
        self.layer_items, self.layer_meshes = {}, {}               # key -> (tree item, mask getter, colour, alpha)
        self.worker = None
        self._pending_layers = set()
        self._layer_timer = QtCore.QTimer(self); self._layer_timer.setSingleShot(True); self._layer_timer.setInterval(0)
        self._layer_timer.timeout.connect(self._apply_layer_changes)
        self._build_ui()
        self._log(f"Robot config: {self.cfg['_path']}")
        if folder: QtCore.QTimer.singleShot(100, lambda: self.open_folder(folder))

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        tb = self.addToolBar("main"); tb.setMovable(False)
        def act(text, fn, tip=""):
            a = QtGui.QAction(text, self); a.triggered.connect(fn); a.setToolTip(tip); tb.addAction(a); return a
        act("Open patient folder", lambda: self.open_folder(), "Folder with orig.nii.gz, segmentation, masks")
        act("Load targets", self.load_targets); act("Save targets", self.save_targets)
        tb.addSeparator()
        act("Edit robot.toml", self.edit_config, "Robot constraints and no-go zones")
        act("Reload robot.toml", self.reload_config)

        central = QtWidgets.QWidget(); grid = QtWidgets.QGridLayout(central); grid.setSpacing(4)
        self.views = [SliceView(2, self), SliceView(1, self), SliceView(0, self)]
        for v in self.views: v.clicked.connect(self.on_click)
        grid.addWidget(self.views[0], 0, 0); grid.addWidget(self.views[1], 0, 1); grid.addWidget(self.views[2], 1, 0)
        self.view3d = None
        try:
            from view3d import View3D                               # pyqtgraph + OpenGL (pure Python, no VTK)
            self.view3d = View3D(central); grid.addWidget(self.view3d, 1, 1)
        except Exception as ex:
            lab = QtWidgets.QLabel(f"3D view not available:\n{ex}\n\nInstall it with:  pip install pyqtgraph PyOpenGL")
            lab.setAlignment(QtCore.Qt.AlignCenter); lab.setWordWrap(True); grid.addWidget(lab, 1, 1)
        self.setCentralWidget(central)

        side = QtWidgets.QWidget(); sl = QtWidgets.QVBoxLayout(side); side.setMinimumWidth(430)
        sl.addWidget(QtWidgets.QLabel("<b>Targets</b>  (left click on a slice to add; double click a name to rename)"))
        self.tlist = QtWidgets.QListWidget(); self.tlist.itemDoubleClicked.connect(self.rename_target)
        self.tlist.currentRowChanged.connect(self.goto_target); sl.addWidget(self.tlist, 1)
        row = QtWidgets.QHBoxLayout()
        for text, fn in (("Delete", self.delete_target), ("Snap to safe point", self.snap_target), ("Clear all", self.clear_targets)):
            b = QtWidgets.QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        sl.addLayout(row)
        sl.addWidget(QtWidgets.QLabel("<b>Target regions</b>  (the robot tip goes anywhere inside; double click to rename)"))
        self.reglist = QtWidgets.QListWidget(); self.reglist.setMaximumHeight(80)
        self.reglist.itemDoubleClicked.connect(self.rename_region)
        self.reglist.currentRowChanged.connect(self.goto_region); sl.addWidget(self.reglist)
        row = QtWidgets.QHBoxLayout()
        self.btn_draw = QtWidgets.QPushButton("Draw outline"); self.btn_draw.setCheckable(True)
        self.btn_draw.setToolTip("Hold the left mouse button and draw around the area on a slice.\n"
                                 "Then draw it on a slice of a second view (e.g. axial, then coronal):\n"
                                 "the region is where the outlines overlap. Drawing again in a view replaces it.")
        self.btn_draw.toggled.connect(self.toggle_draw); row.addWidget(self.btn_draw)
        for text, fn in (("New region", self.new_region), ("Delete region", self.delete_region)):
            b = QtWidgets.QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        sl.addLayout(row)
        self.chk_clip = QtWidgets.QCheckBox("Region only inside the brain"); self.chk_clip.setChecked(True)
        self.chk_clip.toggled.connect(self._rebuild_regions); sl.addWidget(self.chk_clip)
        sl.addWidget(QtWidgets.QLabel("<b>Layers</b>  (tick to show on the slices and in 3D)"))
        self.ltree = QtWidgets.QTreeWidget(); self.ltree.setHeaderHidden(True)
        self.ltree.itemChanged.connect(self._layer_toggled); sl.addWidget(self.ltree, 5)
        self.chk_paths = QtWidgets.QCheckBox("Show paths"); self.chk_paths.setChecked(True)
        self.chk_paths.toggled.connect(self.redraw); sl.addWidget(self.chk_paths)
        self.chk_contacts = QtWidgets.QCheckBox("Show electrode contacts"); self.chk_contacts.setChecked(True)
        self.chk_contacts.setToolTip("Recording contacts of the electrode ([electrode] in robot.toml, default every 5 mm).\n"
                                     "Squares = contacts on this slice, faint dots = contacts on other slices,\n"
                                     "green ring = a contact that lies on a target.")
        self.chk_contacts.toggled.connect(self._contacts_toggled); sl.addWidget(self.chk_contacts)
        self.btn_plan = QtWidgets.QPushButton("Plan paths"); self.btn_plan.setStyleSheet("font-weight: bold; padding: 8px")
        self.btn_plan.clicked.connect(self.plan)
        self.btn_stop = QtWidgets.QPushButton("Stop"); self.btn_stop.setEnabled(False)
        self.btn_stop.setToolTip("Stop planning (paths already found for groups of targets are kept)")
        self.btn_stop.clicked.connect(self.stop_task)
        row = QtWidgets.QHBoxLayout(); row.addWidget(self.btn_plan, 1); row.addWidget(self.btn_stop); sl.addLayout(row)
        self.bar = QtWidgets.QProgressBar(); self.bar.setRange(0, 1000); sl.addWidget(self.bar)
        sl.addWidget(QtWidgets.QLabel("<b>Paths</b>"))
        self.rlist = QtWidgets.QTreeWidget(); self.rlist.setHeaderLabels(["Path", "Length", "Min radius", "Closest no-go", "Electrode contacts on targets"])
        self.rlist.setRootIsDecorated(False); sl.addWidget(self.rlist, 1)
        self.btn_export = QtWidgets.QPushButton("Export to headset"); self.btn_export.clicked.connect(self.export); sl.addWidget(self.btn_export)
        sl.addWidget(QtWidgets.QLabel("<b>Log</b>"))
        self.logbox = QtWidgets.QPlainTextEdit(); self.logbox.setReadOnly(True); sl.addWidget(self.logbox, 2)
        dock = QtWidgets.QDockWidget("Planner", self); dock.setWidget(side); dock.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        self.status = self.statusBar()

    def _log(self, msg):
        self.logbox.appendPlainText(str(msg)); self.logbox.verticalScrollBar().setValue(self.logbox.verticalScrollBar().maximum())

    def _busy(self, on):
        for w in (self.btn_plan, self.btn_export): w.setEnabled(not on)
        self.btn_stop.setEnabled(on)

    def busy(self):
        return self.worker is not None and self.worker.isRunning()

    def _run(self, fn, done):
        if self.busy():
            self._log("busy - wait for the current task or press Stop"); return False
        self._busy(True)
        self._done_cb = done
        self.worker = Worker(fn)
        # connected to methods of this window (lives in the main thread) -> always run in the main thread
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.start()
        return True

    def _on_progress(self, f, msg):
        self.bar.setValue(int(f * 1000)); self.status.showMessage(msg)

    def _on_done(self, res):
        self._busy(False); self._done_cb(res)

    def _on_failed(self, tb):
        self._busy(False); self._log("ERROR:\n" + tb)
        QtWidgets.QMessageBox.critical(self, APP_NAME, tb.strip().splitlines()[-1])

    def _on_cancelled(self):
        self._busy(False); self.bar.setValue(0); self.status.showMessage("stopped"); self._log("Stopped.")

    def stop_task(self):
        if self.busy():
            self.worker.stop(); self.btn_stop.setEnabled(False)
            self._log("Stopping ... (finishing the current step)")

    def closeEvent(self, ev):
        if self.busy():                                          # never destroy a running thread
            self.worker.stop(); self.status.showMessage("stopping the planner before closing ...")
            self.worker.wait(30000)
        super().closeEvent(ev)

    # ------------------------------------------------------------------ patient
    def open_folder(self, folder=None):
        folder = folder or QtWidgets.QFileDialog.getExistingDirectory(self, "Patient folder (output of the pipeline)")
        if not folder: return
        self._log(f"Loading {folder} ... (about 30 s)")
        cfg = self.cfg
        def job(log, progress):
            progress(0.1, "loading scans and building safety maps")
            pt = Patient(folder, cfg, log=log)
            progress(0.8, "preparing the route search")
            return pt, Planner(pt, cfg, log=log)
        self._run(job, self._loaded)

    def _loaded(self, res):
        self.patient, self.planner = res
        p = self.patient
        lo, hi = np.percentile(p.t1[p.head], [1, 99.5])
        self.t1n = np.clip((p.t1 - lo) / (hi - lo), 0, 1).astype(np.float32)
        self.cursor = np.array(p.shape) // 2
        for v in self.views: v.img = None; v.setup(p.shape)
        for w in p.warnings: self._log("WARNING: " + w)
        self._log(f"Patient loaded: {os.path.basename(p.folder.rstrip('/'))}; no-go zones: {', '.join(p.zone_masks)}")
        self.bar.setValue(1000); self.status.showMessage("Left click on a slice to add a target")
        tf = os.path.join(p.folder, "targets.json")
        if os.path.exists(tf): self.load_targets(tf)
        self._load_regions()
        self._build_layer_tree(); self._build_3d(); self.redraw()

    # ------------------------------------------------------------------ layers
    def _build_layer_tree(self):
        """No-go and soft zones from robot.toml (used by the planner) + all display layers of the headset model."""
        p, cfg = self.patient, self.cfg
        self.ltree.blockSignals(True); self.ltree.clear(); self.layer_items = {}
        def swatch(col):
            pm = QtGui.QPixmap(12, 12); pm.fill(QtGui.QColor.fromRgbF(*col)); return QtGui.QIcon(pm)
        groups = []
        def group(title, tip):
            # one tick per group (shows / hides all its layers); expand the group to tick single layers
            g = QtWidgets.QTreeWidgetItem(self.ltree, [title]); g.setToolTip(0, tip + "\nTick = show all; expand to choose single layers")
            g.setFlags(g.flags() | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsAutoTristate)
            f = g.font(0); f.setBold(True); g.setFont(0, f); groups.append((g, title)); return g
        def add(parent, key, text, getter, col, alpha, checked, tip=""):
            it = QtWidgets.QTreeWidgetItem(parent, [text]); it.setIcon(0, swatch(col)); it.setToolTip(0, tip)
            it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
            it.setCheckState(0, QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
            self.layer_items[key] = (it, getter, col, alpha)
        tag = lambda n: " [PRIOR]" if "prior" in n else " [atlas function]" if "eloquent" in n else ""
        g = group("No-go zones (hard limit, robot must stay out)", "From robot.toml [no_go]; robot radius is added to each margin")
        for n, z in cfg.get("no_go", {}).items():
            if n not in p.zone_masks: continue
            out = "outside_of" in z
            text = (f"{n}  (whole head outside the brain, margin {z['margin_mm']} mm)" if out else
                    f"{n}  (margin {z['margin_mm']} mm{', ignored near targets' if z.get('ignore_near_targets') else ''}){tag(n)}")
            add(g, "nogo:" + n, text, (lambda n=n: p.zone_masks[n]), layers.zone_colour(n), 0.25 if out else 0.5,
                not out)                                            # all no-go zones on at start (outside_brain would cover the head)
        g = group("Soft zones (allowed, planner keeps away)", "From robot.toml [avoid]: cost = weight * exp(-distance / scale)")
        for n, z in cfg.get("avoid", {}).items():
            if n not in p.soft_masks: continue
            add(g, "soft:" + n, f"{n}  (weight {z['weight']}, {z['scale_mm']} mm){tag(n)}", (lambda n=n: p.soft_masks[n]),
                layers.zone_colour(n, (1.0, 0.85, 0.1)), 0.35, False)
        for grp in layers.GROUPS:
            items = [L for L in layers.CATALOG if L[1] == grp]
            g = group(grp + "  (display only)", "Display only; they do not change the plan")
            for key, _, src, col, origin in items:
                if "mask" in src and not all(os.path.exists(os.path.join(p.folder, f)) for f in src["mask"]): continue
                o = "" if origin == "patient" else f" [{origin}]"
                add(g, "layer:" + key, key + o, (lambda src=src, key=key: p.display_mask(key, src)), col, 0.4, False,
                    f"source: {', '.join(src['mask']) if 'mask' in src else 'segmentation labels'}")
        for g, title in groups:                                     # collapsed, with the number of layers in the title
            if g.childCount() == 0: self.ltree.invisibleRootItem().removeChild(g); continue
            g.setText(0, f"{title}  [{g.childCount()}]"); g.setExpanded(False)
        self.ltree.blockSignals(False)

    def visible_layers(self):
        out = []
        for key, (it, getter, col, alpha) in self.layer_items.items():
            if it.checkState(0) == QtCore.Qt.Checked:
                m = getter()
                if m is not None: out.append((key, m, col, alpha))
        return out

    def _layer_toggled(self, item, col):
        """A group tick changes all its layers at once: collect them and redraw once."""
        key = next((k for k, v in self.layer_items.items() if v[0] is item), None)
        if key is None: return                                      # a group row: its layers report themselves
        self._pending_layers.add(key); self._layer_timer.start()

    def _apply_layer_changes(self):
        keys, self._pending_layers = self._pending_layers, set()
        self.redraw()
        for key in keys: self._update_3d_layer(key)

    def reload_config(self):
        try: self.cfg = config.load(self.cfg["_path"])
        except Exception as ex: QtWidgets.QMessageBox.critical(self, APP_NAME, f"robot.toml: {ex}"); return
        self._log("robot.toml reloaded")
        if self.patient: self.open_folder(self.patient.folder)

    def edit_config(self):
        path = self.cfg["_path"]
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
        self._log(f"Opened {path} - save it, then press 'Reload robot.toml'")

    # ------------------------------------------------------------------ targets
    def current_target(self):
        it = self.tlist.currentItem(); return it.data(QtCore.Qt.UserRole) if it else None

    def on_click(self, axis, ijk, add):
        if self.patient is None: return
        ijk = np.clip(np.round(ijk).astype(int), 0, np.array(self.patient.shape) - 1)
        self.cursor = ijk
        if add:
            mm = self.patient.vox_to_mm(ijk); n = 1
            while f"T{n}" in self.targets: n += 1
            self.targets[f"T{n}"] = mm; self._refresh_targets(select=f"T{n}")
            msg = self._target_text(f"T{n}", mm); self._log("added " + msg)
        self.redraw()

    def _target_text(self, name, mm):
        region = labels.name(self.patient.label_at(mm))
        warn = ""
        if self.planner:
            bad = self.planner.check_target(mm)
            if bad: warn = "  !! too close to " + ", ".join(f"{z} ({d} mm)" for z, d in bad)
        return f"{name}: {region}  ({mm[0]:.1f}, {mm[1]:.1f}, {mm[2]:.1f}){warn}"

    def _refresh_targets(self, select=None):
        self.tlist.blockSignals(True); self.tlist.clear()
        for n, mm in self.targets.items():
            it = QtWidgets.QListWidgetItem(self._target_text(n, mm)); it.setData(QtCore.Qt.UserRole, n)
            if "!!" in it.text(): it.setForeground(QtGui.QColor("#e55"))
            self.tlist.addItem(it)
            if n == select: self.tlist.setCurrentItem(it)
        self.tlist.blockSignals(False); self._update_3d_targets()

    def goto_target(self, row):
        n = self.current_target()
        if n and self.patient is not None:
            self.cursor = np.clip(np.round(self.patient.mm_to_vox(self.targets[n])).astype(int), 0, np.array(self.patient.shape) - 1)
            self.redraw()

    def rename_target(self, item):
        old = item.data(QtCore.Qt.UserRole)
        new, ok = QtWidgets.QInputDialog.getText(self, "Rename target", "Name:", text=old)
        if ok and new and new not in self.targets:
            self.targets = {(new if k == old else k): v for k, v in self.targets.items()}; self._refresh_targets(select=new); self.redraw()

    def delete_target(self):
        n = self.current_target()
        if n: self.targets.pop(n); self._refresh_targets(); self.redraw()

    def clear_targets(self):
        self.targets.clear(); self.paths = []; self.region_tips = {}
        self._refresh_targets(); self._refresh_paths(); self._refresh_regions(); self._update_3d_paths(); self.redraw()

    def snap_target(self):
        n = self.current_target()
        if not (n and self.planner): return
        s = self.planner.safe_nearby(self.targets[n])
        if s is None: self._log(f"{n}: no safe point within 5 mm"); return
        self._log(f"{n}: moved {np.linalg.norm(s - self.targets[n]):.1f} mm to a safe point")
        self.targets[n] = s; self._refresh_targets(select=n); self.goto_target(0)

    # ------------------------------------------------------------------ target regions
    def drawing(self):
        return self.btn_draw.isChecked()

    def plan_targets(self):
        """Point targets + the tips the planner chose inside the target regions."""
        return {**self.targets, **self.region_tips}

    def current_region(self):
        it = self.reglist.currentItem(); return it.data(QtCore.Qt.UserRole) if it else None

    def _unique(self, base):
        n = 1
        while f"{base}{n}" in self.regions or f"{base}{n}" in self.targets: n += 1
        return f"{base}{n}"

    def new_region(self):
        if self.patient is None: return None
        name = self._unique("R")
        self.regions[name] = regions.Region(name, regions.COLOURS[(len(self.regions)) % len(regions.COLOURS)])
        self._refresh_regions(select=name)
        if not self.btn_draw.isChecked(): self.btn_draw.setChecked(True)
        self._log(f"{name}: draw its outline on a slice, then on a slice of another view")
        return name

    def toggle_draw(self, on):
        for v in self.views: v.lasso.set_active(on)
        self.status.showMessage("Draw the region outline with the left mouse button (then in a second view)" if on
                                else "Left click on a slice to add a target")

    def region_outline(self, axis, k, verts):
        if self.patient is None: return
        name = self.current_region() or self.new_region()
        r = self.regions[name]
        r.set_outline(axis, k, verts)
        self._build_region(r)
        self.region_tips.pop(name, None)
        hint = "" if len(r.outlines) > 1 else " - now draw it in a second view to set its depth"
        if r.mask is not None and r.mask.any():                    # other views jump to the region
            c = np.round(np.argwhere(r.mask).mean(0)).astype(int); c[axis] = k; self.cursor = c
        self._log(f"{name}: outline in the {regions.VIEW_NAMES[axis]} view, {r.volume_ml(self.patient.vox):.1f} ml{hint}")
        self._refresh_regions(select=name); self._update_3d_regions(); self._save_regions(); self.redraw()

    def _build_region(self, r):
        p = self.patient
        r.build(p.shape, p.vox, clip=p.brain if self.chk_clip.isChecked() else None)

    def _rebuild_regions(self):
        if self.patient is None: return
        for r in self.regions.values(): self._build_region(r)
        self.region_tips = {}
        self._refresh_regions(select=self.current_region()); self._update_3d_regions(); self.redraw()

    def _refresh_regions(self, select=None):
        self.reglist.blockSignals(True); self.reglist.clear()
        for n, r in self.regions.items():
            tip = "  tip chosen" if n in self.region_tips else ""
            it = QtWidgets.QListWidgetItem(f"{n}: {r.volume_ml(self.patient.vox):.1f} ml  ({r.views()}){tip}")
            it.setData(QtCore.Qt.UserRole, n); it.setForeground(QtGui.QColor.fromRgbF(*r.colour))
            self.reglist.addItem(it)
            if n == select: self.reglist.setCurrentItem(it)
        self.reglist.blockSignals(False)

    def goto_region(self, row):
        """Show the selected region: cursor to the slice of its outline (or its centre)."""
        n = self.current_region()
        if not (n and self.patient is not None): return
        r = self.regions[n]
        if r.mask is not None and r.mask.any():
            self.cursor = np.round(np.argwhere(r.mask).mean(0)).astype(int)
        elif r.outlines:
            axis, (k, vt) = next(iter(r.outlines.items()))
            self.cursor = np.round(regions.to_ijk(axis, vt[:1, 0], vt[:1, 1], k)[0]).astype(int)
        self.redraw()

    def rename_region(self, item):
        old = item.data(QtCore.Qt.UserRole)
        new, ok = QtWidgets.QInputDialog.getText(self, "Rename region", "Name:", text=old)
        if ok and new and new not in self.regions and new not in self.targets:
            self.regions = {(new if k == old else k): v for k, v in self.regions.items()}; self.regions[new].name = new
            if old in self.region_tips: self.region_tips[new] = self.region_tips.pop(old)
            self._refresh_regions(select=new); self._update_3d_regions(); self._save_regions(); self.redraw()

    def delete_region(self):
        n = self.current_region()
        if not n: return
        self.regions.pop(n); self.region_tips.pop(n, None)
        self._refresh_regions(); self._update_3d_regions(); self._save_regions(); self.redraw()

    def _save_regions(self, masks=False):
        if self.patient is None: return
        p = self.patient
        regions.save(p.folder, self.regions, p.vox_to_mm, p.affine if masks else None)

    def _load_regions(self):
        p = self.patient
        self.regions, self.region_tips = regions.load(p.folder, p.mm_to_vox), {}
        for r in self.regions.values(): self._build_region(r)
        if self.regions: self._log(f"{len(self.regions)} target region(s) loaded from regions.json")
        self._refresh_regions()

    def _update_3d_regions(self):
        if self.view3d is None or self.patient is None: return
        for name in [n for n in self.view3d.items if n.startswith("REG_")]: self.view3d.remove(name)
        for n, r in self.regions.items():
            if r.mask is None or not r.mask.any(): continue
            mesh = self._mesh(r.mask, 1)
            if mesh is not None: self.view3d.add_mesh("REG_" + n, *mesh, r.colour, 0.45)

    def region_contacts(self, path, c):
        """{region name: number of electrode contacts inside it} for the regions this path is planned for."""
        out = {}
        for n in path.targets:
            r = self.regions.get(n)
            if r is None or r.mask is None or not len(c.centres): continue
            ijk = np.round(self.patient.mm_to_vox(c.centres)).astype(int)
            ok = np.all((ijk >= 0) & (ijk < np.array(r.mask.shape)), axis=1)
            out[n] = int(r.mask[tuple(ijk[ok].T)].sum())
        return out

    def contact_text(self, path):
        c = electrode.for_path(path, self.cfg, self.plan_targets())
        txt = electrode.summary(c, self.cfg)
        for n, k in self.region_contacts(path, c).items(): txt += f" | region {n}: {k} contact(s) inside"
        return c, txt

    def save_targets(self):
        if self.patient is None: return
        path = os.path.join(self.patient.folder, "targets.json")
        json.dump([{"name": n, "ras_mm": np.round(v, 2).tolist()} for n, v in self.targets.items()], open(path, "w"), indent=1)
        self._save_regions(masks=True)
        self._log(f"targets saved to {path}" + (f"; {len(self.regions)} region(s) to regions.json and regions/" if self.regions else ""))

    def load_targets(self, path=None):
        if self.patient is None: return
        path = path or QtWidgets.QFileDialog.getOpenFileName(self, "Targets", self.patient.folder, "JSON (*.json)")[0]
        if not path: return
        self.targets = {t["name"]: np.array(t["ras_mm"], float) for t in json.load(open(path))}
        self._refresh_targets(); self._log(f"{len(self.targets)} targets loaded from {path}"); self.redraw()

    # ------------------------------------------------------------------ planning
    def plan(self):
        regs = {n: r.mask for n, r in self.regions.items() if r.mask is not None and r.mask.any()}
        if not (self.planner and (self.targets or regs)): self._log("open a patient and add targets or regions first"); return
        if self.busy(): self._log("busy - wait for the current task or press Stop"); return
        targets, pl = {k: np.array(v, float) for k, v in self.targets.items()}, self.planner
        pl.robot, pl.pl = self.cfg["robot"], self.cfg["planning"]; pl.cfg = self.cfg
        n = len(targets) + len(regs)
        self._log(f"Planning {n} target(s) ... (each target alone, then groups of targets on one path; "
                  f"time limit {self.cfg['planning'].get('time_limit_s', 120)} s, Stop keeps what was found)")
        def job(log, progress):
            pl.log, pl.progress = log, progress
            pl.should_stop = lambda: self.worker.stop_requested
            try:
                tips = {}
                for rn, mask in regs.items():                        # 1. a tip anywhere inside every region
                    progress(0.0, f"choosing the best point in region {rn}")
                    tip, msg = pl.region_tip(rn, mask)
                    log(f"  region {rn}: {msg}")
                    if tip is not None: tips[rn] = tip
                return pl.plan_all({**targets, **tips}), tips       # 2. then planned like point targets
            finally: pl.should_stop = lambda: False
        self._run(job, self._planned)

    def _planned(self, res):
        (self.paths, self.uncovered, _), self.region_tips = res
        self._log(f"{len(self.paths)} path(s) for {len(self.targets) + len(self.region_tips)} target(s)")
        self._refresh_regions(select=self.current_region()); self._update_3d_targets()
        for n in self.uncovered:
            self._log(f"NOT REACHED: {n} - {self.planner.target_problems.get(n, 'no path satisfies all constraints')}")
        for i, r in enumerate(self.paths):
            self._log(f"  path {i + 1} electrode: {self.contact_text(r)[1]}")
        self._refresh_paths(); self._update_3d_paths(); self.redraw()

    def _contacts_toggled(self):
        self._update_3d_paths(); self.redraw()

    def _refresh_paths(self):
        self.rlist.clear()
        nogo = [z for z in self.cfg.get("no_go", {}) if "outside_of" not in self.cfg["no_go"][z]]
        for i, r in enumerate(self.paths):
            close = min(((r.min_clearance_mm.get(z, 99), z) for z in nogo), default=(None, ""))
            c, ctext = self.contact_text(r)
            it = QtWidgets.QTreeWidgetItem([f"{i + 1}: {' -> '.join(r.targets)}", f"{r.length_mm:.0f} mm",
                                            f"{r.min_radius_mm:.0f} mm", f"{close[1]} {close[0]} mm", ctext])
            it.setForeground(0, QtGui.QColor.fromRgbF(*PATH_COLOURS[i % len(PATH_COLOURS)]))
            if len(c.hits) < len(c.on_target): it.setForeground(4, QtGui.QColor("#f66"))
            it.setToolTip(4, "#n = contact number from the tip (1 = deepest), then the distance from the target to its centre")
            self.rlist.addTopLevelItem(it)
        for c in range(5): self.rlist.resizeColumnToContents(c)

    def headset_layers(self):
        """The app's layers for the headset model, in the order and groups of the layer list:
        [(name, group, mask, colour, visible at start, origin)]. outside_brain is left out (it is the whole head)."""
        import headset_scene
        p = self.patient
        out = [("brain", "Anatomy", p.brain, (0.85, 0.7, 0.7), True, "patient")]
        for key, (it, getter, col, alpha) in self.layer_items.items():
            kind, name = key.split(":", 1)
            if key.startswith("nogo:outside"): continue
            m = getter()
            if m is None or not m.any(): continue
            group = "Head" if name in headset_scene.HEAD_LAYERS else headset_scene.GROUPS[kind]
            spec = (self.cfg.get("no_go", {}).get(name) or self.cfg.get("avoid", {}).get(name) or {}) if kind != "layer" else {}
            files = " ".join(spec.get("mask", []))
            origin = ("prior" if ("prior" in name or "prior" in files) else "atlas function" if "eloquent" in name
                      else "estimate" if name == "skull_t1" else "patient")
            out.append((name, group, m, tuple(col), kind == "nogo", origin))
        for n, r in self.regions.items():                           # target regions drawn by the doctor
            if r.mask is not None and r.mask.any():
                out.append((f"region_{n}", "Target regions", r.mask, tuple(r.colour), True, "drawn by the doctor"))
        return out

    def export(self):
        if not self.paths: self._log("nothing to export - plan first"); return
        man = self.patient.headset_manifest
        if not man:
            QtWidgets.QMessageBox.warning(self, APP_NAME, "No headset/headset_manifest.json in the patient folder.\n"
                                          "Run tools/export_headset.py first."); return
        centre = np.array(man["coordinate_system"]["head_centre_ras_mm"])
        p, paths, targets, cfg = self.patient, list(self.paths), dict(self.plan_targets()), self.cfg
        uncovered, problems = list(self.uncovered), dict(getattr(self.planner, "target_problems", {}))
        layers = self.headset_layers()
        self.save_targets()
        self._log(f"Exporting {len(paths)} path(s) and the brain model with {len(layers)} layers ... (about 1 min)")
        def job(log, progress):
            import headset_scene
            progress(0.1, "writing plan.json and paths.glb")
            path = export.export(p.headset_dir, paths, targets, cfg, centre, uncovered, problems)
            progress(0.3, "building the brain model for the headset")
            headset_scene.export_scene(p.headset_dir, p, layers, log=log)
            progress(1.0, "export done")
            return path
        self._run(job, lambda path: self._log(f"Exported to {os.path.dirname(path)}: plan.json, paths.glb, "
                                              f"patient_scene.glb (same layers as here) - press Play in Unity"))

    # ------------------------------------------------------------------ drawing
    def set_cursor(self, c):
        self.cursor = np.clip(np.asarray(c, int), 0, np.array(self.patient.shape) - 1) if self.patient else c; self.redraw()

    def redraw(self):
        for v in self.views: v.redraw()

    def _mesh(self, mask, step):
        from view3d import mesh_from_mask
        return mesh_from_mask(mask, self.patient.vox_to_mm, step)

    def _build_3d(self):
        if self.view3d is None: return
        p = self.patient; v3 = self.view3d; v3.clear(); self.layer_meshes = {}
        b = self._mesh(p.brain, 2)
        if b is not None:
            v3.add_mesh("brain", *b, (0.85, 0.7, 0.7), 0.12); v3.fit(b[0])
        for key in self.layer_items: self._update_3d_layer(key)
        self._update_3d_targets(); self._update_3d_paths(); self._update_3d_regions()

    def _update_3d_layer(self, key):
        if self.view3d is None or self.patient is None: return
        it, getter, col, alpha = self.layer_items[key]
        name = "L_" + key
        if it.checkState(0) != QtCore.Qt.Checked or key.startswith("nogo:outside"):
            self.view3d.remove(name); return
        if key not in self.layer_meshes:
            m = getter()
            if m is None: return
            big = m.sum() * self.patient.vox.prod() / 1000 > 100            # > 100 ml: coarser mesh
            self.layer_meshes[key] = self._mesh(m, 2 if big else 1)
        mesh = self.layer_meshes[key]
        if mesh is not None:
            ml = getter().sum() * self.patient.vox.prod() / 1000
            # large layers faint (they would hide the rest), small ones (vessels, sinus, plexus) solid
            op = 0.15 if key.endswith(("gray_matter", "white_matter", "scalp", "skull_t1")) else 0.2 if ml > 20 else 1.0
            self.view3d.add_mesh(name, *mesh, col, op)

    def _update_3d_targets(self):
        if self.view3d is None or self.patient is None: return
        self.view3d.remove("targets")
        if self.plan_targets():
            self.view3d.add_points("targets", np.array(list(self.plan_targets().values())), (1.0, 0.0, 1.0), 14)

    def _update_3d_paths(self):
        if self.view3d is None: return
        for name in [n for n in self.view3d.items if n.startswith("path")]: self.view3d.remove(name)
        for i, r in enumerate(self.paths):
            self.view3d.add_line(f"path{i}", r.points, PATH_COLOURS[i % len(PATH_COLOURS)], width=4)
            if self.chk_contacts.isChecked():
                c = electrode.for_path(r, self.cfg, self.plan_targets())
                rest = [j for j in range(len(c.centres)) if j not in c.hits]
                if rest: self.view3d.add_points(f"path{i}_contacts", c.centres[rest], (1.0, 1.0, 1.0), 7)
                if c.hits: self.view3d.add_points(f"path{i}_hits", c.centres[sorted(c.hits)], (0.2, 1.0, 0.2), 13)

# ---------------------------------------------------------------------------------------------- entry
def selftest(folder):
    """Load a patient and plan one target in the middle of the left hippocampus - no window."""
    cfg = config.load(); pt = Patient(folder, cfg); pl = Planner(pt, cfg)
    ijk = np.argwhere(pt.labels == 17); xyz = pt.vox_to_mm(ijk); c = xyz[np.argmin(np.linalg.norm(xyz - xyz.mean(0), axis=1))]
    s = pl.safe_nearby(c) if pl.check_target(c) else c
    ch, unc, _ = pl.plan_all({"L hippocampus": s})
    print("SELFTEST", "OK" if ch and ch[0].feasible else "FAILED", [(r.targets, round(r.length_mm), round(r.min_radius_mm)) for r in ch], unc)
    return 0 if ch else 1

def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--selftest": sys.exit(selftest(sys.argv[2]))
    app = QtWidgets.QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setStyle("Fusion")
    pal = QtGui.QPalette()
    for role, col in ((QtGui.QPalette.Window, "#2b2b2b"), (QtGui.QPalette.WindowText, "#ddd"), (QtGui.QPalette.Base, "#1e1e1e"),
                      (QtGui.QPalette.Text, "#ddd"), (QtGui.QPalette.Button, "#3a3a3a"), (QtGui.QPalette.ButtonText, "#ddd"),
                      (QtGui.QPalette.Highlight, "#2a7"), (QtGui.QPalette.HighlightedText, "#000")):
        pal.setColor(role, QtGui.QColor(col))
    app.setPalette(pal)
    w = MainWindow(sys.argv[1] if len(sys.argv) > 1 else None); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
