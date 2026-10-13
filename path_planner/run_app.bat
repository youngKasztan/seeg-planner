@echo off
rem Starts the planner without building an exe (uses the .venv created by build_exe.bat or pip install -r requirements.txt).
cd /d %~dp0
if exist .venv\Scripts\python.exe ( .venv\Scripts\python.exe app.py %* ) else ( python app.py %* )
