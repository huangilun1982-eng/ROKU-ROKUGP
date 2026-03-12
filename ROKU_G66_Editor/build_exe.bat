@echo off
set "PYTHON_EXE=C:\Users\CMAT-CNC-PC\AppData\Local\Programs\Python\Python313\python.exe"

echo Used Python: "%PYTHON_EXE%"
echo.
echo Cleaning old build artifacts...
if exist dist del /q /s dist\*
echo.
echo Building Executable using Spec file...
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean ROKU_G66_Editor_v2.spec
echo.
echo Build Done! Executable is in the 'dist' folder.
pause
