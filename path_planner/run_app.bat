@echo off
rem Starts the planner without building an exe.
rem Python used: path_planner\.venv (made by build_exe.bat), else the repo .venv, else python on PATH.
rem Installs the 3D view libraries (pyqtgraph, PyOpenGL - pure Python, allowed by Smart App Control) if they are missing.
cd /d %~dp0
set PY=python
if exist ..\.venv\Scripts\python.exe set PY=..\.venv\Scripts\python.exe
if exist .venv\Scripts\python.exe set PY=.venv\Scripts\python.exe
echo Using %PY%
%PY% -c "import pyqtgraph, OpenGL" 2>nul || %PY% -m pip install pyqtgraph PyOpenGL
%PY% app.py %*
