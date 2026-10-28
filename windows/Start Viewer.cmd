@echo off
setlocal
cd /d "%~dp0"
"%~dp0runtime\python.exe" -I -B "%~dp0remote_viewer.py" %*
pause
