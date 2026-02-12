@echo off
set "PYTHON_EXE=C:\Users\CMAT-CNC-PC\AppData\Local\Programs\Python\Python313\python.exe"

echo Used Python: "%PYTHON_EXE%"
echo.
echo Installing/Updating PyInstaller...
"%PYTHON_EXE%" -m pip install pyinstaller
echo.
echo Building Executable...
"%PYTHON_EXE%" -m PyInstaller --noconfirm --onefile --windowed --name "ROKU_G66_Editor_v2" --hidden-import "matplotlib.backends.backend_qtagg" --clean main.py
echo.
echo Build Done! Executable is in the 'dist' folder.
pause
