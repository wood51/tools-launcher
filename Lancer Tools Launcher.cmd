@echo off
rem Lance Tools Launcher avec le Python du systeme (bootstrap.pyw prepare ou repare l'environnement).
cd /d "%~dp0"
if exist "runtime\pythonw.exe" (
    start "" "runtime\pythonw.exe" "bootstrap.pyw"
    exit /b
)
where pyw >nul 2>&1 && (
    start "" pyw "bootstrap.pyw"
    exit /b
)
where pythonw >nul 2>&1 && (
    start "" pythonw "bootstrap.pyw"
    exit /b
)
where python >nul 2>&1 && (
    start "" python "bootstrap.pyw"
    exit /b
)
echo Python 3.12 ou plus recent est introuvable.
echo Installez-le depuis le Microsoft Store (Python Install Manager), puis relancez ce fichier.
pause
