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
import config, labels
from patient import Patient
from planner import Planner
import export

from PySide6 import QtCore, QtGui, QtWidgets
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

APP_NAME = "Continuum Path Planner"
PATH_COLOURS = export.COLOURS

# ---------------------------------------------------------------------------------------------- workers
class Worker(QtCore.QThread):
    """Runs a function in the background; reports log lines and progress."""
    log = QtCore.Signal(str)
    progress = QtCore.Signal(float, str)
    done = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, fn):
        super().__init__(); self.fn = fn

    def run(self):
        try: self.done.emit(self.fn(self.log.emit, lambda f, m="": self.progress.emit(f, m)))
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
        self.img = self.ov_nogo = self.ov_soft = None
        self.artists = []

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
        if ev.inaxes is None or ev.xdata is None: return
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
            self.ov_nogo = self.ax.imshow(np.zeros(sl.shape + (4,)), origin="lower", interpolation="nearest")
            self.ov_soft = self.ax.imshow(np.zeros(sl.shape + (4,)), origin="lower", interpolation="nearest")
            h, w = sl.shape
            for txt, x in (("R", w - 12), ("L", 4)) if self.axis != 0 else (("A", w - 12), ("P", 4)):
                self.ax.text(x, h - 14, txt, color="#8cf", fontsize=11, weight="bold")
        self.img.set_data(sl)
        def rgba(mask, col, alpha):
            m = self.take(mask, k); o = np.zeros(m.shape + (4,), np.float32); o[m] = (*col, alpha); return o
        self.ov_nogo.set_data(rgba(p.nogo_union, (1, 0.15, 0.15), 0.45) if a.chk_nogo.isChecked() else np.zeros(sl.shape + (4,)))
        self.ov_soft.set_data(rgba(p.soft_union, (1, 0.85, 0.1), 0.25) if a.chk_soft.isChecked() else np.zeros(sl.shape + (4,)))
        for art in self.artists: art.remove()
        self.artists = []
        u, v, _ = self.uv(a.cursor)
        self.artists += [self.ax.axvline(u[0], color="#2a6", lw=0.6, alpha=0.6), self.ax.axhline(v[0], color="#2a6", lw=0.6, alpha=0.6)]
        if a.chk_paths.isChecked():
            for i, r in enumerate(a.paths):
                ijk = p.mm_to_vox(r.points); pu, pv, d = self.uv(ijk); col = PATH_COLOURS[i % len(PATH_COLOURS)]
                self.artists += self.ax.plot(pu, pv, color=col, lw=1, alpha=0.35)
                near = np.abs(d - k) <= 2.0
                if near.any():
                    self.artists += self.ax.plot(np.where(near, pu, np.nan), np.where(near, pv, np.nan), color=col, lw=3)
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
        self.worker = None
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
            from pyvistaqt import QtInteractor
            self.view3d = QtInteractor(central); self.view3d.set_background("black")
            grid.addWidget(self.view3d.interactor, 1, 1)
        except Exception as ex:
            lab = QtWidgets.QLabel(f"3D view not available:\n{ex}"); lab.setAlignment(QtCore.Qt.AlignCenter); grid.addWidget(lab, 1, 1)
        self.setCentralWidget(central)

        side = QtWidgets.QWidget(); sl = QtWidgets.QVBoxLayout(side); side.setMinimumWidth(380)
        sl.addWidget(QtWidgets.QLabel("<b>Targets</b>  (left click on a slice to add; double click a name to rename)"))
        self.tlist = QtWidgets.QListWidget(); self.tlist.itemDoubleClicked.connect(self.rename_target)
        self.tlist.currentRowChanged.connect(self.goto_target); sl.addWidget(self.tlist, 2)
        row = QtWidgets.QHBoxLayout()
        for text, fn in (("Delete", self.delete_target), ("Snap to safe point", self.snap_target), ("Clear all", self.clear_targets)):
            b = QtWidgets.QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        sl.addLayout(row)
        row = QtWidgets.QHBoxLayout()
        self.chk_nogo = QtWidgets.QCheckBox("No-go zones"); self.chk_nogo.setChecked(True)
        self.chk_soft = QtWidgets.QCheckBox("Soft zones"); self.chk_paths = QtWidgets.QCheckBox("Paths"); self.chk_paths.setChecked(True)
        for c in (self.chk_nogo, self.chk_soft, self.chk_paths): c.toggled.connect(self.redraw); row.addWidget(c)
        sl.addLayout(row)
        self.btn_plan = QtWidgets.QPushButton("Plan paths"); self.btn_plan.setStyleSheet("font-weight: bold; padding: 8px")
        self.btn_plan.clicked.connect(self.plan); sl.addWidget(self.btn_plan)
        self.bar = QtWidgets.QProgressBar(); self.bar.setRange(0, 1000); sl.addWidget(self.bar)
        sl.addWidget(QtWidgets.QLabel("<b>Paths</b>"))
        self.rlist = QtWidgets.QTreeWidget(); self.rlist.setHeaderLabels(["Path", "Length", "Min radius", "Closest no-go"])
        self.rlist.setRootIsDecorated(False); sl.addWidget(self.rlist, 2)
        self.btn_export = QtWidgets.QPushButton("Export to headset"); self.btn_export.clicked.connect(self.export); sl.addWidget(self.btn_export)
        sl.addWidget(QtWidgets.QLabel("<b>Log</b>"))
        self.logbox = QtWidgets.QPlainTextEdit(); self.logbox.setReadOnly(True); sl.addWidget(self.logbox, 3)
        dock = QtWidgets.QDockWidget("Planner", self); dock.setWidget(side); dock.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        self.status = self.statusBar()

    def _log(self, msg):
        self.logbox.appendPlainText(str(msg)); self.logbox.verticalScrollBar().setValue(self.logbox.verticalScrollBar().maximum())

    def _busy(self, on):
        for w in (self.btn_plan, self.btn_export): w.setEnabled(not on)

    def _run(self, fn, done):
        if self.worker and self.worker.isRunning():
            self._log("busy - wait for the current task"); return
        self._busy(True)
        self.worker = Worker(fn)
        self.worker.log.connect(self._log)
        self.worker.progress.connect(lambda f, m: (self.bar.setValue(int(f * 1000)), self.status.showMessage(m)))
        self.worker.done.connect(lambda r: (self._busy(False), done(r)))
        self.worker.failed.connect(lambda tb: (self._busy(False), self._log("ERROR:\n" + tb),
                                               QtWidgets.QMessageBox.critical(self, APP_NAME, tb.splitlines()[-1])))
        self.worker.start()

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
        self._build_3d(); self.redraw()

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
        self.targets.clear(); self.paths = []; self._refresh_targets(); self._refresh_paths(); self.redraw()

    def snap_target(self):
        n = self.current_target()
        if not (n and self.planner): return
        s = self.planner.safe_nearby(self.targets[n])
        if s is None: self._log(f"{n}: no safe point within 5 mm"); return
        self._log(f"{n}: moved {np.linalg.norm(s - self.targets[n]):.1f} mm to a safe point")
        self.targets[n] = s; self._refresh_targets(select=n); self.goto_target(0)

    def save_targets(self):
        if self.patient is None: return
        path = os.path.join(self.patient.folder, "targets.json")
        json.dump([{"name": n, "ras_mm": np.round(v, 2).tolist()} for n, v in self.targets.items()], open(path, "w"), indent=1)
        self._log(f"targets saved to {path}")

    def load_targets(self, path=None):
        if self.patient is None: return
        path = path or QtWidgets.QFileDialog.getOpenFileName(self, "Targets", self.patient.folder, "JSON (*.json)")[0]
        if not path: return
        self.targets = {t["name"]: np.array(t["ras_mm"], float) for t in json.load(open(path))}
        self._refresh_targets(); self._log(f"{len(self.targets)} targets loaded from {path}"); self.redraw()

    # ------------------------------------------------------------------ planning
    def plan(self):
        if not (self.planner and self.targets): self._log("open a patient and add targets first"); return
        targets, pl = dict(self.targets), self.planner
        pl.robot, pl.pl = self.cfg["robot"], self.cfg["planning"]; pl.cfg = self.cfg
        self._log(f"Planning {len(targets)} target(s) ...")
        def job(log, progress):
            pl.log, pl.progress = log, progress
            return pl.plan_all(targets)
        self._run(job, self._planned)

    def _planned(self, res):
        self.paths, self.uncovered, _ = res
        self._log(f"{len(self.paths)} path(s) for {len(self.targets)} target(s)")
        for n in self.uncovered:
            self._log(f"NOT REACHED: {n} - {self.planner.target_problems.get(n, 'no path satisfies all constraints')}")
        self._refresh_paths(); self._update_3d_paths(); self.redraw()

    def _refresh_paths(self):
        self.rlist.clear()
        nogo = [z for z in self.cfg.get("no_go", {}) if "outside_of" not in self.cfg["no_go"][z]]
        for i, r in enumerate(self.paths):
            close = min(((r.min_clearance_mm.get(z, 99), z) for z in nogo), default=(None, ""))
            it = QtWidgets.QTreeWidgetItem([f"{i + 1}: {' -> '.join(r.targets)}", f"{r.length_mm:.0f} mm",
                                            f"{r.min_radius_mm:.0f} mm", f"{close[1]} {close[0]} mm"])
            it.setForeground(0, QtGui.QColor.fromRgbF(*PATH_COLOURS[i % len(PATH_COLOURS)]))
            self.rlist.addTopLevelItem(it)
        for c in range(4): self.rlist.resizeColumnToContents(c)

    def export(self):
        if not self.paths: self._log("nothing to export - plan first"); return
        man = self.patient.headset_manifest
        if not man:
            QtWidgets.QMessageBox.warning(self, APP_NAME, "No headset/headset_manifest.json in the patient folder.\n"
                                          "Run tools/export_headset.py first."); return
        centre = np.array(man["coordinate_system"]["head_centre_ras_mm"])
        path = export.export(self.patient.headset_dir, self.paths, self.targets, self.cfg, centre,
                             self.uncovered, getattr(self.planner, "target_problems", {}))
        self.save_targets()
        self._log(f"Exported {len(self.paths)} path(s): {path} and paths.glb - copy the headset folder to the glasses")

    # ------------------------------------------------------------------ drawing
    def set_cursor(self, c):
        self.cursor = np.clip(np.asarray(c, int), 0, np.array(self.patient.shape) - 1) if self.patient else c; self.redraw()

    def redraw(self):
        for v in self.views: v.redraw()

    def _build_3d(self):
        if self.view3d is None: return
        import pyvista as pv
        from skimage import measure
        from scipy import ndimage
        p = self.patient; v3 = self.view3d; v3.clear()
        def mesh(mask, step=2):
            m = ndimage.zoom(mask.astype(np.float32), 1 / step, order=1)
            if m.max() < 0.5: return None
            vv, ff, _, _ = measure.marching_cubes(m, 0.5)
            pts = p.vox_to_mm(vv * step)
            return pv.PolyData(pts, np.hstack([np.full((len(ff), 1), 3), ff]).ravel())
        b = mesh(p.brain)
        if b is not None: v3.add_mesh(b, color=[0.85, 0.7, 0.7], opacity=0.12, name="brain")
        if "arteries" in p.zone_masks:
            a = mesh(p.zone_masks["arteries"], 1)
            if a is not None: v3.add_mesh(a, color="red", opacity=0.6, name="arteries")
        if "ventricles" in p.zone_masks:
            a = mesh(p.zone_masks["ventricles"], 1)
            if a is not None: v3.add_mesh(a, color=[0.3, 0.55, 1], opacity=0.5, name="ventricles")
        v3.view_xz(); v3.reset_camera(); self._update_3d_targets()

    def _update_3d_targets(self):
        if self.view3d is None or self.patient is None: return
        import pyvista as pv
        self.view3d.remove_actor("targets")
        if self.targets:
            self.view3d.add_mesh(pv.PolyData(np.array(list(self.targets.values()))), color="magenta", point_size=14,
                                 render_points_as_spheres=True, name="targets")

    def _update_3d_paths(self):
        if self.view3d is None: return
        import pyvista as pv
        for i in range(20): self.view3d.remove_actor(f"path{i}")
        for i, r in enumerate(self.paths):
            line = pv.Spline(r.points, len(r.points)).tube(radius=self.cfg["robot"]["diameter_mm"] / 2)
            self.view3d.add_mesh(line, color=PATH_COLOURS[i % len(PATH_COLOURS)], name=f"path{i}")

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
