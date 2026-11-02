import json
import os
import re
from pathlib import Path

from core.paths import ASSETS_DIR, DATA_DIR, EXTENSIONS_DIR
from core.registry import MANIFEST_NAME, discover_extensions

SETTINGS_FILE = DATA_DIR / "settings.json"
THEMES_DIR = ASSETS_DIR / "themes"
QSS_FILE = ASSETS_DIR / "theme.qss"
DEFAULT_THEME = "dark"
SCHEMES = ("dark", "light")
BUILTIN_THEMES = ("dark", "light")  # non supprimables
THEME_ID = re.compile(r"[a-z0-9][a-z0-9_-]*")

# Couleurs du thème par défaut : base de tous les thèmes et utilisées par splash.py
# (tkinter, avant que PySide6 soit installé : ce module doit rester sans dépendance)
DEFAULT_COLORS = json.loads((THEMES_DIR / f"{DEFAULT_THEME}.json").read_text(encoding="utf-8"))["colors"]
BG = DEFAULT_COLORS["BG"]
SURFACE_2 = DEFAULT_COLORS["SURFACE_2"]
TEXT = DEFAULT_COLORS["TEXT"]
MUTED = DEFAULT_COLORS["MUTED"]
ACCENT = DEFAULT_COLORS["ACCENT"]


#### Thèmes : dark et light dans core/assets/themes/, les autres sont des extensions de type theme ####

def load_theme(path: Path) -> dict:
    """Lit un thème. Les couleurs absentes sont complétées par celles du thème par défaut."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"fichier illisible ({e})")
    if not isinstance(data, dict) or "label" not in data:
        raise ValueError("label manquant")
    colors = data.get("colors", {})
    scheme = data.get("scheme", "dark")
    if not isinstance(colors, dict) or scheme not in SCHEMES:
        raise ValueError("colors ou scheme invalide")
    return {"label": data["label"], "scheme": scheme, "colors": {**DEFAULT_COLORS, **colors}}


def theme_sources() -> dict[str, Path]:
    """{identifiant: fichier .json}. Les thèmes du noyau l'emportent sur une extension du même id."""
    sources = {path.stem: path for path in sorted(THEMES_DIR.glob("*.json"))}
    for ext in discover_extensions():
        if "theme" in ext and ext["id"] not in sources:
            sources[ext["id"]] = ext["folder"] / ext["theme"]["file"]
    return sources


def discover_themes() -> dict[str, dict]:
    """Renvoie {identifiant: thème}. L'identifiant est celui de l'extension (ou le nom du fichier pour dark et light)."""
    themes = {}
    for theme_id, path in theme_sources().items():
        try:
            themes[theme_id] = load_theme(path)
        except ValueError as e:
            print(f"thème {path.name} ignoré : {e}")
    return themes


def _resolve(name: str) -> dict:
    themes = discover_themes()
    return themes.get(name) or themes[DEFAULT_THEME]


def theme_qss_path(theme_id: str) -> Path | None:
    """Feuille de surcharge optionnelle (`<fichier du thème>.qss`), ou None si elle n'existe pas."""
    path = theme_sources().get(theme_id)
    qss = path.with_suffix(".qss") if path else None
    return qss if qss and qss.exists() else None


def save_theme(theme_id: str, label: str, scheme: str, colors: dict) -> None:
    """Écrit le thème. Un nouveau thème crée l'extension `extensions/<theme_id>/`."""
    if not THEME_ID.fullmatch(theme_id):
        raise ValueError(f"identifiant de thème invalide : {theme_id!r}")
    if scheme not in SCHEMES:
        raise ValueError(f"scheme invalide : {scheme!r}")
    data = {
        "label": label,
        "scheme": scheme,
        "colors": {key: colors[key] for key in DEFAULT_COLORS if key in colors},
    }
    path = theme_sources().get(theme_id)
    if path is None:
        folder = EXTENSIONS_DIR / theme_id
        if folder.exists():
            raise ValueError(f"le dossier extensions/{theme_id} existe déjà")
        folder.mkdir(parents=True)
        path = folder / f"{theme_id}.json"
        manifest = {
            "id": theme_id,
            "name": label,
            "version": "1.0.0",
            "theme": {"file": path.name},
        }
        (folder / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def theme_files(theme_id: str) -> list[Path]:
    """Fichiers d'un thème : le .json, son .qss de surcharge, et le manifeste si c'est une extension."""
    path = theme_sources().get(theme_id)
    if path is None:
        return []
    files = [path, theme_qss_path(theme_id)]
    if path.parent != THEMES_DIR:
        files.append(path.parent / MANIFEST_NAME)
    return [f for f in files if f and f.exists()]


def delete_theme(theme_id: str) -> None:
    """Supprime un thème-extension (ses fichiers, puis son dossier s'il est vide)."""
    if theme_id in BUILTIN_THEMES:
        raise ValueError("les thèmes fournis ne peuvent pas être supprimés")
    path = theme_sources().get(theme_id)
    if path is None or path.parent == THEMES_DIR:
        raise ValueError(f"thème introuvable : {theme_id}")
    for file in theme_files(theme_id):
        file.unlink()
    try:
        path.parent.rmdir()
    except OSError:
        pass  # le dossier contient autre chose (README, données) : on le garde


#### Réglage du thème ####

def get_theme() -> str:
    try:
        name = json.loads(SETTINGS_FILE.read_text(encoding="utf-8")).get("theme")
    except (OSError, ValueError, AttributeError):
        return DEFAULT_THEME
    return name if name in discover_themes() else DEFAULT_THEME


def set_theme(name: str, app=None) -> None:
    """Enregistre le thème (les outils ouverts le suivent) et l'applique à `app` si fourni."""
    if name not in discover_themes():
        raise ValueError(f"thème inconnu : {name}")
    try:
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            settings = {}
    except (OSError, ValueError):
        settings = {}
    settings["theme"] = name
    SETTINGS_FILE.parent.mkdir(exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    if app is not None:
        apply_theme_now(app, name)


def apply_theme_now(app, name: str) -> None:
    from PySide6.QtCore import Qt

    # aligne la palette système de Qt, pour les widgets que la feuille de style ne couvre pas
    scheme = Qt.ColorScheme.Light if _resolve(name)["scheme"] == "light" else Qt.ColorScheme.Dark
    app.styleHints().setColorScheme(scheme)
    app.setStyleSheet(build_stylesheet(name))


def apply_theme(app) -> None:
    """À appeler dans chaque outil après QApplication : applique le thème et suit ses changements."""
    from PySide6.QtCore import QFileSystemWatcher
    from PySide6 import QtSvg  # noqa: F401  (sans cet import, Qt ne charge pas les icônes SVG)
    from core.i18n import install_french_qt

    install_french_qt(app)

    def reapply() -> None:
        apply_theme_now(app, get_theme())
        if SETTINGS_FILE.exists() and str(SETTINGS_FILE) not in watcher.files():
            watcher.addPath(str(SETTINGS_FILE))

    SETTINGS_FILE.parent.mkdir(exist_ok=True)  # sans dossier, la surveillance échouerait en silence
    watcher = QFileSystemWatcher(app)
    watcher.addPath(str(SETTINGS_FILE.parent))  # capte la création du fichier
    watcher.fileChanged.connect(reapply)
    watcher.directoryChanged.connect(reapply)
    reapply()
    set_tool_identity(app)


def set_tool_identity(app) -> None:
    """Pour un outil lancé par le lanceur (variable TL_EXTENSION_ID) : icône de la fenêtre, groupe
    propre dans la barre des tâches, et plantage visible. Sans effet dans le lanceur lui-même."""
    extension_id = os.environ.get("TL_EXTENSION_ID")
    if not extension_id:
        return
    from PySide6.QtGui import QIcon

    from core.api import install_crash_handler
    from core.paths import CORE_APPS, ICONS_DIR, LAUNCHER_ICON
    from core.registry import discover_tools

    install_crash_handler(extension_id)
    if os.environ.get("TL_MULTIPLE") != "1":
        from core.single import ensure_single_instance

        ensure_single_instance(app, extension_id)  # déjà ouvert : l'autre fenêtre passe devant, ce processus s'arrête
    try:
        import ctypes

        # sans identifiant propre, Windows range la fenêtre sous python et lui donne son icône
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"Wood51.ToolsLauncher.{extension_id}")
    except (AttributeError, OSError):
        pass
    icon_path = LAUNCHER_ICON if extension_id in CORE_APPS else ICONS_DIR / "tool.svg"
    for tool in discover_tools():
        if tool["id"] == extension_id and tool.get("icon") and (tool["folder"] / tool["icon"]).is_file():
            icon_path = tool["folder"] / tool["icon"]
    app.setWindowIcon(QIcon(str(icon_path)))


#### Feuille de style ####

ICONS_CACHE_DIR = DATA_DIR / "theme_icons"
INDICATOR_SVGS = {
    "ICON_CHECK": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18"><path d="M4.5 9.5l3 3 6-7" fill="none" '
    'stroke="{color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "ICON_RADIO": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18"><circle cx="9" cy="9" r="3.6" fill="{color}"/></svg>',
    "ICON_CHEVRON_DOWN": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3.5 6l4.5 4 4.5-4" fill="none" '
    'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "ICON_CHEVRON_UP": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3.5 10l4.5-4 4.5 4" fill="none" '
    'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
}
ICON_COLOR_KEYS = {"ICON_CHECK":"ON_ACCENT","ICON_RADIO":"ON_ACCENT",
                   "ICON_CHEVRON_DOWN":"TEXT","ICON_CHEVRON_UP":"TEXT"}


def indicator_icon(kind: str, color: str) -> str:
    """Chemin (barres obliques) d'une petite image de case à cocher ou de bouton radio, de la couleur du thème.
    Qt ne sait pas recolorer une image : on l'écrit une fois par couleur dans core/data/theme_icons/."""
    path = ICONS_CACHE_DIR / f"{kind.lower()}_{color.lstrip('#')}.svg"
    try:
        if not path.is_file():
            ICONS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(INDICATOR_SVGS[kind].format(color=color), encoding="utf-8")
    except OSError:
        return ""
    return path.as_posix()


def render_stylesheet(colors: dict, extra_qss: str = "") -> str:
    """theme.qss avec les jetons @NOM remplacés par `colors`, suivi de `extra_qss`.
    Les jetons `@ICON_*` donnent le chemin d'une image adaptée au contraste du thème."""
    def token(match) -> str:
        key = match.group(1)
        if key in INDICATOR_SVGS:
            color_key=ICON_COLOR_KEYS[key]
            return indicator_icon(key,colors.get(color_key,DEFAULT_COLORS[color_key]))
        if key not in colors:
            print(f"jeton inconnu dans la feuille de style : @{key}")
            return match.group(0)
        return colors[key]

    text = "\n".join([QSS_FILE.read_text(encoding="utf-8"), extra_qss])
    return re.sub(r"@([A-Z][A-Z0-9_]*)", token, text)


def build_stylesheet(name: str = DEFAULT_THEME) -> str:
    """Feuille de style du thème `name`, avec son <id>.qss de surcharge s'il existe."""
    extra = theme_qss_path(name)
    extra_qss = extra.read_text(encoding="utf-8") if extra else ""
    return render_stylesheet(_resolve(name)["colors"], extra_qss)
