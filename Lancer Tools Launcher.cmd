@echo off
rem Lance Tools Launcher sans dependre de l'association des fichiers .pyw.
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "bootstrap.pyw"
) else if exist "runtime\pythonw.exe" (
    start "" "runtime\pythonw.exe" "bootstrap.pyw"
) else (
    where pyw >nul 2>&1 && (start "" pyw "bootstrap.pyw") || (
        echo Python 3.12 ou plus recent est introuvable.
        echo Installez-le, ou utilisez la version autonome du lanceur.
        pause
    )
)
