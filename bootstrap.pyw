###############################
#  Imports
###############################
import subprocess, ctypes, sys
from pathlib import Path

from core.deps import deps_outdated, install_deps, load_failed
from core.splash import run_with_splash

###############################
#  Constantes
###############################
ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PYTHONW = VENV / "Scripts" / "pythonw.exe"
PYTHON = VENV / "Scripts" / "python.exe"
RUNTIME_PYTHON = ROOT / "runtime" / "python.exe"


###############################
#  Functions
###############################
def venv_missing() -> bool:
    return not PYTHONW.exists()


def setup(set_status) -> bool:
    if venv_missing():
        set_status("Création de l'environnement (1/2)…")
        python = RUNTIME_PYTHON if RUNTIME_PYTHON.exists() else Path(sys.executable).with_name("python.exe")
        subprocess.run(
            [str(python), "-m", "venv", str(VENV)],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    if deps_outdated():
        set_status("Installation des dépendances (2/2)…")
        return install_deps(set_status) is not None

    return True


###############################
#  Main
###############################
if venv_missing() or deps_outdated():
    if not run_with_splash("Préparation…", setup):
        ctypes.windll.user32.MessageBoxW(
            0,
            "Échec de l'installation. Vérifie la connexion réseau ou le proxy.",
            "Erreur",
            0x10,
        )
        sys.exit(1)
    if failed := load_failed():  # signalé une fois, à l'installation
        ctypes.windll.user32.MessageBoxW(
            0,
            "Dépendances non installées, extensions ignorées :\n" + "\n".join(sorted(failed)),
            "Avertissement",
            0x30,
        )

# Lancement du lanceur
subprocess.Popen(
    [str(PYTHONW), str(ROOT / "core" / "launcher.pyw")],
    creationflags=subprocess.CREATE_NO_WINDOW,
)
