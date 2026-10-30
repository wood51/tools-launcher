# Squelettes : outil, plugin, thème

Copier, renommer, remplir. Dossier : `extensions/<id>/` ; `id` = nom du dossier.

## Outil

```
extensions/mon_outil/
├─ extension.json
├─ README.md
├─ main.pyw
└─ icon.svg          optionnel
```

```json
{
  "id": "mon_outil",
  "name": "Mon outil",
  "version": "1.0.0",
  "tooltip": "Ce que fait l'outil",
  "tool": { "entry": "main.pyw", "icon": "icon.svg" }
}
```

`main.pyw` (version lanceur) :

```python
import sys

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from core.api import get_api

api = get_api()
app = QApplication(sys.argv)
api.apply_theme(app)

window = QWidget()
window.setObjectName("root")  # reçoit le fond du thème
window.setWindowTitle("Mon outil")
layout = QVBoxLayout(window)
layout.addWidget(QLabel("Bonjour"))
window.resize(400, 300)
window.show()

sys.exit(app.exec())
```

Un outil **réservé au lanceur** (version lanceur seulement) qui dépend du lanceur (il importe `core`) doit le dire quand on le lance seul, au lieu de planter sans bruit (`pythonw` n'affiche aucune erreur) :

```python
try:
    from core.api import get_api
except ImportError:  # lancé hors du lanceur
    import ctypes

    ctypes.windll.user32.MessageBoxW(0, "Cet outil se lance depuis le lanceur Tools Launcher (menu Outils).", "Mon outil", 0x10)
    raise SystemExit(1)
```

Pour une version qui marche **aussi hors du lanceur**, remplacer l'import par le motif de `standalone.md`.

Structure conseillée pour un outil non trivial : la logique sans Qt dans un module séparé (`logic.py`, testable seule, sans import PySide6), la fenêtre dans `main.pyw`. Les erreurs attendues (fichier absent, entrée invalide) sont attrapées là où elles se produisent et montrées à l'utilisateur dans l'interface (message dans la fenêtre ou `QMessageBox`), pas seulement affichées sur la console, que `pythonw` cache.

## Plugin

```
extensions/mon_plugin/
├─ extension.json
├─ README.md
├─ main.py           définit register(api)
└─ autre.py          optionnel : `from .autre import ...` dans main.py
```

```json
{
  "id": "mon_plugin",
  "name": "Mon plugin",
  "version": "1.0.0",
  "tooltip": "Ce que fait le plugin",
  "plugin": { "entry": "main.py" }
}
```

```python
from PySide6.QtWidgets import QMenu


def build_menu(menu: QMenu) -> None:
    """Appelée à chaque ouverture du sous-menu : le menu est vidé puis rempli de nouveau."""
    action = menu.addAction("Faire quelque chose")
    action.triggered.connect(lambda checked=False: do_something())


def do_something() -> None:
    print("fait")


def register(api) -> None:
    api.add_menu("Mon menu", build_menu)           # sous-menu rempli à chaque ouverture
    api.add_action("Entrée simple", do_something)  # entrée directe du menu principal
    api.on_start(lambda: print("lanceur démarré"))
    api.on_quit(lambda: print("lanceur arrêté"))
```

Plugin minimal (exemple `hello`) :

```python
def register(api) -> None:
    api.add_action("Bonjour", lambda: api.notify("Bonjour", "Le plugin fonctionne."))
```

## Extension à deux blocs (plugin + outil)

```json
{
  "id": "files",
  "name": "Fichier",
  "version": "1.0.0",
  "tooltip": "Ouvre les fichiers configurés avec l'application choisie",
  "plugin": { "entry": "main.py" },
  "tool": { "name": "Éditeur de fichiers", "entry": "editor.pyw" }
}
```

Le plugin ouvre l'outil avec `api.launch_tool("files")`. Le code partagé (sans Qt) vit dans un module de l'extension ; l'outil l'importe par `from extensions.files.files import ...` (le `PYTHONPATH` est la racine du projet), le plugin par `from .files import ...`.

## Thème

```
extensions/mon_theme/
├─ extension.json
├─ README.md
├─ mon_theme.json     les couleurs
└─ mon_theme.qss      optionnel
```

```json
{
  "id": "mon_theme",
  "name": "Mon thème",
  "version": "1.0.0",
  "theme": { "file": "mon_theme.json" }
}
```

`mon_theme.json` :

```json
{
  "label": "Mon thème",
  "scheme": "dark",
  "colors": {
    "BG": "#14171f",
    "SURFACE": "#1c2029",
    "SURFACE_2": "#242a36",
    "BORDER": "#323a4a",
    "TEXT": "#e6e9f0",
    "MUTED": "#9aa3b8",
    "ACCENT": "#4d85f2",
    "ACCENT_HOVER": "#6a9af5",
    "ON_ACCENT": "#ffffff"
  }
}
```

L'id du thème est l'`id` de l'extension. `label` : nom affiché ; `scheme` : `dark` ou `light`. Les couleurs omises viennent du thème sombre. Liste complète des jetons et règles de contraste : `theming.md`. Le `.qss` optionnel porte le même nom que le `.json` et peut utiliser les jetons (`@ACCENT`).
