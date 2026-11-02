# Mon plugin

Le launcher charge `main.py` et appelle `register(api)`.

Utiliser `sdk/API.md` pour `add_action`, `add_menu`, `on_start`, `on_quit`, les notifications et les badges.

`build_zip.cmd` crée `outputs/<id>-<version>.zip`. Installer ce ZIP dans le Catalogue d’une copie de test du Launcher, puis redémarrer le Launcher pour charger le plugin. Le plugin n’a pas de lancement autonome.
