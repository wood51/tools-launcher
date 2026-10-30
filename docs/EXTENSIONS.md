# Squelettes : outil, plugin, thème

Tout se déclare par une **extension** : un dossier `extensions/<id>/` avec un `extension.json`. Le contenu du manifeste choisit ce que l'extension est ; une même extension peut cumuler plusieurs blocs (exemple : `files` est un plugin et un outil). Copier le squelette, renommer, remplir. Vérifier ensuite avec `.venv\Scripts\python.exe scripts\check.py`.

| | Outil (`tool`) | Plugin (`plugin`) | Thème (`theme`) |
|---|---|---|---|
| Rôle | Programme avec sa propre fenêtre | Ajoute au menu du lanceur, réagit à ses événements | Palette de couleurs |
| Processus | Séparé (`pythonw.exe`) | **Celui du lanceur** | Aucun (fichier lu) |
| Plantage | Sans effet sur le lanceur | Message console et `core/data/plugins.log`, plugin ignoré | Thème ignoré avec message |
| Activer, retirer | Immédiat | Au prochain démarrage | Immédiat |

Noms de dossiers, fichiers et variables en anglais ; textes affichés en français.

## Le manifeste `extension.json`

```json
{
  "id": "mon_outil",
  "name": "Mon outil",
  "version": "1.0.0",
  "tooltip": "Ce que fait l'extension",
  "tool": { "entry": "main.pyw", "icon": "icon.svg" }
}
```

- **Optionnels** : `tooltip`, `author` (mention affichée sur la carte du Catalogue).
- **Obligatoires** : `id` (égal au nom du dossier ; minuscules, chiffres, `_`, `-`), `name`, `version` (`1.2.3`), et au moins un bloc `tool`, `plugin` ou `theme`.
- **Blocs** : `tool` : `entry` obligatoire, `name` (libellé du menu Outils, sinon le `name` de l'extension), `icon` et `multiple` (`true` si l'outil doit pouvoir s'ouvrir plusieurs fois ; par défaut, relancer un outil déjà ouvert ramène sa fenêtre au premier plan) optionnels. `plugin` : `entry`. `theme` : `file`.
- Les chemins (`entry`, `file`, `icon`) sont relatifs au dossier de l'extension et ne peuvent pas en sortir. `entry` et `file` doivent exister.
- Un manifeste invalide est ignoré avec un message ; il n'empêche jamais le lanceur de démarrer.
- Chaque extension a un `README.md` (ce qu'elle fait, ses données) et, si elle écrit des données, un dossier `data/` (non versionné, jamais écrasé par une mise à jour).

---

## Squelette d'outil

```
extensions/mon_outil/
├─ extension.json
├─ README.md
├─ main.pyw
└─ icon.svg          optionnel
```

`main.pyw` : son propre `QApplication`, le thème appliqué après sa création, un widget central nommé `root`.

```python
import sys

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from core.theme import apply_theme

app = QApplication(sys.argv)
apply_theme(app)

window = QWidget()
window.setObjectName("root")  # reçoit le fond du thème
window.setWindowTitle("Mon outil")
layout = QVBoxLayout(window)
layout.addWidget(QLabel("Bonjour"))
window.resize(400, 300)
window.show()

sys.exit(app.exec())
```

API de l'outil (`core/api.py`, stdlib seulement) :

```python
from core.api import get_api

api = get_api()  # l'extension courante
api.apply_theme(app)  # remplace apply_theme(app) ci-dessus
settings = api.load_settings()
api.save_settings(settings)  # écriture atomique dans data/settings.json
api.log("message")  # console + core/data/plugins.log
api.notify("Titre", "Message", "info")  # toast du lanceur ; False si le lanceur ne tourne pas
api.set_badge("blue")  # badge de l'icône ; None le retire
```

Aussi `api.data_dir`, `api.load_json(nom)` / `api.save_json(nom, data)` et `api.launch_tool(id)`. Les plugins ont les mêmes appels, plus ceux du tableau ci-dessous.

Un outil qui dépend du lanceur (il importe `core`) doit le dire quand on le lance seul, au lieu de planter sans bruit (`pythonw` n'affiche aucune erreur) :

```python
try:
    from core.api import get_api
except ImportError:  # lancé hors du lanceur
    import ctypes

    ctypes.windll.user32.MessageBoxW(0, "Cet outil se lance depuis le lanceur Tools Launcher (menu Outils).", "Mon outil", 0x10)
    raise SystemExit(1)
```

Pièges : sans `setObjectName("root")` le fond reste celui du système (texte illisible en thème clair) ; `read_text()` toujours avec `encoding="utf-8"` ; un `subprocess` lancé depuis l'outil prend `creationflags=subprocess.CREATE_NO_WINDOW`. Pour déboguer, lancer `main.pyw` avec `python.exe` dans un terminal (`pythonw.exe` cache les erreurs). Une erreur non attrapée ou un plantage au démarrage ne sont plus silencieux : le lanceur envoie la sortie d'erreur de l'outil dans `core/data/plugins.log`, notifie si l'outil s'arrête aussitôt, et `get_api()` / `apply_theme` affichent une boîte d'erreur (une fois) pour une exception en cours d'exécution. L'icône de la fenêtre est celle du manifeste (`tool.icon`, sinon l'icône générique) et chaque outil a son propre groupe dans la barre des tâches (rien à faire dans le code de l'outil). Le processus de l'outil a `PYTHONPATH` = racine du projet : `from core.theme import ...` fonctionne, et aussi `from extensions.autre.module import ...` pour partager du code avec une autre extension.

---

## Squelette de plugin

```
extensions/mon_plugin/
├─ extension.json
├─ README.md
├─ main.py           doit définir register(api)
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

`main.py` : une fonction `register(api)`, appelée une fois au démarrage du lanceur. On y **s'abonne** à ce que l'on veut.

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

API disponible (`core/plugin_api.py`) :

| Appel | Rôle |
|---|---|
| `api.add_menu(title, build, icon=None)` | Sous-menu ; `build(menu)` le remplit à chaque ouverture |
| `api.add_action(text, callback, icon=None)` | Entrée simple du menu principal |
| `api.on_start(fn)` / `api.on_quit(fn)` | Rappels au démarrage et à l'arrêt |
| `api.launch_tool(extension_id)` | Lance l'outil d'une extension d'après son `id` |
| `api.notify(title, message, level="info", on_click=None)` | Notification du lanceur (toast en bas à droite, pas celle de Windows) ; `level` : `info`, `warning`, `error` |
| `api.log(message)` | Écrit dans la console et `core/data/plugins.log` (`pythonw` cache la console) |
| `api.set_badge("blue" / "red" / None)` | Badge de l'icône (le rouge l'emporte) |
| `api.data_dir` | Dossier `data/` de l'extension (`extensions/<id>/data/`), créé si besoin, non versionné |
| `api.load_settings()` / `api.save_settings(dict)` | Réglages de l'extension, dans `data/settings.json` |

Règles :
- Un plugin ne modifie jamais `core/launcher.pyw` : tout passe par `api`.
- Une exception dans `register` ou dans un callback est attrapée et journalisée ; le lanceur continue.
- Ne pas bloquer : pas de traitement long dans un callback (lancer un outil ou un `subprocess` à la place).
- Activer ou désactiver : **Launcher > Paramètres… > Plugins** (mémorisé dans `core/data/config.json`), effet au redémarrage du lanceur (le bouton « Redémarrer le lanceur » est dans la fenêtre).
- Un plugin est chargé comme un paquet : `from .autre import ...` fonctionne, `import autre` non.

---

## Squelette de thème

```
extensions/mon_theme/
├─ extension.json
├─ README.md
├─ mon_theme.json     les couleurs
└─ mon_theme.qss      optionnel : surcharge pour ce qui n'est pas une couleur
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

- L'identifiant du thème est l'`id` de l'extension. Le thème apparaît au prochain menu Thème, sans redémarrer. `dark` et `light` sont fournis par le noyau (`core/assets/themes/`) et ne sont pas supprimables.
- `label` : nom affiché ; `scheme` : `dark` ou `light` (règle les parties que la palette ne couvre pas).
- Les couleurs omises viennent de `dark.json`. Liste complète des jetons : voir `core/assets/themes/light.json` (16 jetons : `BG`, `SURFACE`, `SURFACE_2`, `BORDER`, `TEXT`, `MUTED`, `ACCENT`, `ACCENT_HOVER`, `ALT_ROW`, `HOVER_ROW`, `SELECTION`, `SELECTION_STRONG`, `WARN`, `WARN_BG`, `DROP_HOVER`, `ON_ACCENT`).
- Le `.qss` optionnel porte le même nom que le `.json` et peut utiliser les jetons (`@ACCENT`).
- Le plus simple pour en créer un : l'extension **Éditeur de thèmes** (aperçu en direct, rapports de contraste) ; elle crée le dossier et le manifeste.
