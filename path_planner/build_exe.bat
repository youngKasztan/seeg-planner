@echo off
rem Builds dist\ContinuumPathPlanner\ContinuumPathPlanner.exe (Windows). Double click or run from a terminal.
rem Needs Python 3.11 (python.org). First run downloads the libraries (~1 GB) and takes 5-10 minutes.
cd /d %~dp0
if not exist .venv (
  py -3.11 -m venv .venv 2>nul || python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || goto :error
pyinstaller --noconfirm --clean --name ContinuumPathPlanner --windowed ^
  --add-data "robot.toml;." ^
  --collect-submodules skimage.graph --hidden-import scipy.optimize._highs ^
  --collect-data trimesh --collect-submodules pyqtgraph --collect-submodules OpenGL ^
  --exclude-module torch --exclude-module tensorflow --exclude-module SimpleITK --exclude-module cv2 ^
  app.py || goto :error
copy /Y robot.toml dist\ContinuumPathPlanner\robot.toml >nul
echo.
echo Done: dist\ContinuumPathPlanner\ContinuumPathPlanner.exe
echo Edit dist\ContinuumPathPlanner\robot.toml to change the robot constraints.
pause
exit /b 0
:error
echo BUILD FAILED - see the messages above
pause
exit /b 1
