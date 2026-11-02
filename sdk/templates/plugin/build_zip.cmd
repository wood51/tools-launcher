@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_zip.ps1" -Project "%~dp0"
pause
