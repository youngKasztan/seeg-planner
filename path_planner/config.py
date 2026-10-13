"""config.py - read robot.toml (robot constraints, no-go and soft zones, planner settings)."""
import os, sys, tomllib

def default_path():
    base = getattr(sys, "_MEIPASS", None)                  # inside the PyInstaller exe
    exe_dir = os.path.dirname(sys.executable) if base else os.path.dirname(os.path.abspath(__file__))
    for d in (exe_dir, base or exe_dir):                   # a robot.toml next to the exe wins (easy to edit)
        p = os.path.join(d, "robot.toml")
        if os.path.exists(p): return p
    raise FileNotFoundError("robot.toml not found")

def load(path=None):
    path = path or default_path()
    with open(path, "rb") as f: cfg = tomllib.load(f)
    for sec in ("robot", "planning"):
        if sec not in cfg: raise ValueError(f"robot.toml: missing [{sec}]")
    cfg["_path"] = path
    return cfg
