@echo off
setlocal
cd /d "%~dp0"
"%~dp0runtime\python.exe" -I -B -m unittest discover -s "%~dp0tests" -v
if errorlevel 1 echo Self-test failed. Please share the test output for troubleshooting.
pause
