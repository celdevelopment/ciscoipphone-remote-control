@echo off
setlocal
cd /d "%~dp0"
"%~dp0runtime\python.exe" -I -B "%~dp0install_windows.py"
if errorlevel 1 echo Installation did not complete. Read the error above.
pause
