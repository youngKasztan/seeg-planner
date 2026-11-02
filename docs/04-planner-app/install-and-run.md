<!-- nav:crumb -->
[Docs home](../README.md) › [Planner app (desktop)](README.md) › **Install and run**
<!-- /nav:crumb -->

# Install and run

## Requirements

Python 3.11 (python.org), Windows (also runs on Linux / macOS). Libraries (`path_planner/requirements.txt`): numpy, scipy, nibabel, scikit-image, trimesh, fast_simplification, matplotlib, PySide6, pyqtgraph, PyOpenGL, pyinstaller.

## Three ways to start

| Way | Command | When |
|---|---|---|
| from the repo's virtual environment | `cd C:\Users\MSI\Desktop\seeg-planner` then `.\.venv\Scripts\python.exe path_planner\app.py C:\Users\MSI\Desktop\dataMedical\IXI057` | development; the patient folder argument opens it at start |
| `run_app.bat` | double click in `path_planner/` | uses `path_planner\.venv`, else the repo `.venv`, else `python` on PATH; installs pyqtgraph / PyOpenGL if missing |
| Windows exe | `build_exe.bat` -> `dist\ContinuumPathPlanner\ContinuumPathPlanner.exe` | for users without Python; first build downloads ~1 GB and takes 5-10 min |

The exe build (PyInstaller) bundles `robot.toml` and copies it next to the exe, where it can be edited.

**Windows Smart App Control** may block an unsigned exe; then use `run_app.bat`. The 3D view uses pyqtgraph + PyOpenGL (pure Python) because the earlier VTK / pyvista view was blocked by Smart App Control (unsigned DLLs).

## Self-test without a window

```
python path_planner/app.py --selftest C:\Users\MSI\Desktop\dataMedical\IXI057
```

Loads the patient, puts a target in the centre of the left hippocampus (snapped to a safe point if needed), plans it and prints `SELFTEST OK` with the path length and smallest radius.

<!-- nav:bar -->
---
← [Planner app (desktop)](README.md) | [↑ Planner app (desktop)](README.md) | [The main window](main-window.md) →
<!-- /nav:bar -->
