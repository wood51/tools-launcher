# Version autonome (hors du lanceur) d'un outil

Un outil peut tourner **seul** (`python main.pyw`) **et** être déposé tel quel dans `extensions/<id>/` d'un lanceur Tools Launcher. Même dossier, même code.

## Principe

- `main.pyw` essaie l'API du noyau, et se rabat sur `tl_shim.py` (à côté de lui, copié depuis `references/tl_shim.py`) si `core` est absent :

```python
try:
    from core.api import get_api
except ImportError:
    from tl_shim import get_api

api = get_api()
```

- Le reste du code n'utilise que `api` : `data_dir`, `load_json`/`save_json`, `load_settings`/`save_settings`, `log`, `apply_theme`, `notify`, `set_badge`. Surtout pas d'autre import de `core` ni de `extensions.*`.
- Quand `main.pyw` est lancé par le lanceur, son dossier est `sys.path[0]` : `from tl_shim import get_api` marche aussi, mais n'est jamais atteint puisque `core` existe.
- Hors du lanceur : les données sont dans `<dossier>/data/`, le journal dans `data/app.log`, le thème est le sombre embarqué (le thème du lanceur n'est pas suivi), `notify` écrit au journal et renvoie `False`, `set_badge` renvoie `False`, `launch_tool` écrit au journal. Le code ne doit pas dépendre du succès de `notify` ou `set_badge`.

## Contenu du dossier

```
mon_outil/
├─ extension.json    toujours (id = nom du dossier)
├─ README.md
├─ main.pyw
├─ tl_shim.py       copie exacte de references/tl_shim.py
├─ requirements.txt  PySide6_Essentials==6.12.0 (+ autres, versions fixées)
└─ logic.py          optionnel : logique sans Qt
```

Lancer hors lanceur : `pip install -r requirements.txt` (de préférence dans un venv) puis `python main.pyw` (`pythonw main.pyw` sans console). Déposé dans un lanceur : copier le dossier dans `extensions/`, le bootstrap installe les dépendances ; `tl_shim.py` y est inerte.

## Dans une discussion sans accès au dépôt ni au lanceur

Livrer les fichiers complets (manifeste, README, code, shim, requirements) ; dire que la version lanceur n'a pas été testée dans un vrai lanceur, et que le comportement visuel n'a pas été vérifié à l'écran si c'est le cas. Pour tester sans lanceur : `python main.pyw` avec PySide6 installé ; pour tester sans écran : `QT_QPA_PLATFORM=offscreen`.

## Limites

- Un **plugin** (menu du lanceur) n'a pas de version autonome : il modifie le menu du lanceur. On peut en revanche isoler sa logique sans Qt dans un module et en faire un outil autonome.
- Hors du lanceur, pas de thème partagé ni de notifications du lanceur : le shim donne un repli simple.
