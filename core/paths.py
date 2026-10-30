from pathlib import Path

#### Dossiers ####
ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = Path(__file__).resolve().parent
EXTENSIONS_DIR = ROOT / "extensions"
ASSETS_DIR = CORE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"

#### Données (jamais versionnées, jamais écrasées par une mise à jour) ####
DATA_DIR = CORE_DIR / "data"  # données du noyau


def launcher_version() -> str:
    """Version du lanceur : contenu du fichier VERSION à la racine."""
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8-sig").strip() or "?"
    except OSError:
        return "?"


def extension_data_dir(extension_id: str) -> Path:
    """Dossier `data/` d'une extension."""
    return EXTENSIONS_DIR / extension_id / "data"


#### Python du venv ####
RUNTIME_PYTHON = ROOT / "runtime" / "python.exe"  # Python embarqué (zip autonome), sinon celui du système
WHEELS_DIR = ROOT / "wheels"  # roues hors ligne du zip autonome
VENV = ROOT / ".venv"
PYTHON = VENV / "Scripts" / "python.exe"
PYTHONW = VENV / "Scripts" / "pythonw.exe"

#### Configuration et plugins ####
CONFIG_FILE = DATA_DIR / "config.json"
LEGACY_PLUGINS_FILE = DATA_DIR / "plugins.json"  # ancien emplacement des plugins désactivés
LOG_FILE = DATA_DIR / "plugins.log"
LOG_MAX_BYTES = 500_000

#### Canal outil → lanceur (tube nommé Windows `\\.\pipe\<nom>`) ####
CHANNEL_NAME = "tools-launcher"

#### Fenêtres du noyau (pas des extensions) : nom affiché ; elles portent l'icône du lanceur ####
CORE_APPS = {"catalog": "Catalogue", "settings": "Paramètres"}
LAUNCHER_ICON = ICONS_DIR / "launcher.ico"

#### Icônes de la zone de notification ####
TRAY_ICONS = {
    None: "launcher.ico",
    "blue": "launcher_badge_blue.ico",
    "red": "launcher_badge_red.ico",
}


if __name__ == "__main__":
    print(ROOT)
