@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo Lancez install_dev.cmd d'abord.
  pause
  exit /b 1
)
.venv\Scripts\pythonw.exe main.pyw
