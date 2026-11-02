# L'API d'une extension (`core/api.py`, `core/plugin_api.py`)

## Dans un outil

```python
from core.api import get_api

api = get_api()  # l'extension courante (id : variable TL_EXTENSION_ID, sinon nom du dossier du script)
```

`get_api("mon_id")` force l'id. Module stdlib seulement (importable sans PySide6).

| Appel | Rôle |
|---|---|
| `api.id` | id de l'extension |
| `api.data_dir` | `Path` du dossier `extensions/<id>/data/`, créé si besoin, non versionné, jamais écrasé par une mise à jour |
| `api.load_json(name)` | lit `data/<name>` ; `None` si absent ou illisible (message au journal) ; le résultat peut être de n'importe quel type : valider |
| `api.save_json(name, data)` | écrit `data/<name>` **de façon atomique** (fichier temporaire unique puis `os.replace`), UTF-8, indenté, accents conservés ; `name` qui sort de `data/` (`../x.json`) : `ValueError` (`load_json` renvoie `None` et journalise) |
| `api.load_settings()` | `dict` lu dans `data/settings.json` ; `{}` si absent ou invalide |
| `api.save_settings(dict)` | écrit `data/settings.json` (atomique) |
| `api.log(message)` | console et `core/data/plugins.log` (vidé au-delà de 500 Ko) ; ne lève jamais d'exception ; **le seul moyen de voir un message depuis `pythonw`** |
| `api.apply_theme(app)` | applique le thème choisi dans le lanceur et le suit en direct ; à appeler juste après avoir créé le `QApplication` |
| `api.notify(title, message, level="info")` | notification selon le choix de l'utilisateur (toast du lanceur en bas à droite, notification Windows au nom de l'extension, un seul des deux ; son optionnel) ; `level` : `info`, `warning`, `error` ; renvoie `False` si le lanceur ne tourne pas |
| `api.set_badge(level)` | badge de l'icône du lanceur : `"blue"` (information), `"red"` (notification, prioritaire), `None` (retire) ; renvoie `False` sans lanceur ; lève `ValueError` pour une autre valeur |
| `api.launch_tool(extension_id)` | lance l'outil d'une autre extension d'après son `id` |
| `api.open_path(path)` | ouvre un fichier ou un dossier avec l'association Windows |
| `api.open_file(path)` / `api.open_folder(path)` | ouvre uniquement le type de chemin attendu |
| `api.choose_file(parent, title, filter)` | affiche le sélecteur de fichier et renvoie un `Path` ou `None` |
| `api.choose_folder(parent, title)` | affiche le sélecteur de dossier et renvoie un `Path` ou `None` |
| `api.confirm(parent, title, message)` | demande une confirmation Oui/Non |
| `api.get_app_info()` | renvoie l'identifiant et le mode `launcher` ou `standalone` |

Aussi disponible : `core.api.write_json_atomic(path, data)` pour écrire un JSON de façon atomique ailleurs que dans `data/` (créé le dossier parent).

Un `from core.api import ...` échoue hors du lanceur (voir `standalone.md`).

## Dans un plugin (`register(api)`)

`main.py` définit `register(api)`, appelée une fois au démarrage du lanceur. `api` a **tout ce qui précède**, plus :

| Appel | Rôle |
|---|---|
| `api.add_menu(title, build, icon=None)` | sous-menu du lanceur ; `build(menu: QMenu)` est appelé **à chaque ouverture** (le menu est vidé puis rempli) |
| `api.add_action(text, callback, icon=None)` | entrée simple du menu principal ; `callback()` sans argument |
| `api.on_start(fn)` / `api.on_quit(fn)` | rappels une fois le lanceur affiché / à l'arrêt |
| `api.notify(title, message, level="info", on_click=None)` | comme ci-dessus, avec un rappel au clic (plugin seulement, et seulement pour le toast du lanceur) |
| `api.set_badge(level)` | comme ci-dessus (le badge est partagé par id d'extension) |

Les entrées s'insèrent avant le menu **Launcher**. `icon` : un `QIcon`. Toute exception dans `register` ou un callback est attrapée et journalisée ; le lanceur continue. Pas de rechargement à chaud : relancer le lanceur après une modification. Activer ou désactiver un plugin : Launcher > Paramètres > Plugins (effet au redémarrage du lanceur).

Règles : rien de long dans un callback (lancer un outil ou un `subprocess`) ; un plugin ne touche jamais le code du lanceur ; la logique sans Qt va dans un module séparé, testable seul (voir `extensions/files/files.py` + `main.py`).

## Canal outil → lanceur (pour information)

`notify` et `set_badge` depuis un outil écrivent un message JSON, une ligne, dans le tube nommé `\\.\pipe\tools-launcher` (`core.api.send_message`). Le lanceur valide les champs, limite les textes à 500 caractères, ignore et journalise un message invalide, n'accepte que l'utilisateur courant. Un seul lanceur tourne à la fois (`core/data/launcher.lock`). Un badge posé par un outil reste jusqu'à `set_badge(None)` : le retirer à la fermeture si besoin.
