# Tools Launcher SDK

Le SDK fournit une base commune pour créer des outils Python/PySide6 conformes au standard UI. La référence courte est [UI_STANDARD.md](UI_STANDARD.md) et le contrat des fonctions est [API.md](API.md).

## Démarrer un outil

1. Copier `templates/basic_app` pour un outil, ou `templates/plugin` pour un plugin.
2. Modifier `extension.json` (identifiant égal au nom du dossier) et l’entrée `main.pyw` ou `main.py`.
3. Pour un outil autonome : exécuter `install_dev.cmd` une fois, puis `run_dev.cmd`.
4. Exécuter `build_zip.cmd` pour obtenir `outputs/<id>-<version>.zip`, local et non signé. Le script fourni fonctionne aussi depuis une copie du modèle située ailleurs sur le PC.

Pour un plugin, installer le ZIP dans une copie de test du Launcher et vérifier le menu. Un plugin dépend du Launcher ; il ne se lance pas seul. Pour intégrer un outil, conserver `extension.json` et installer son ZIP dans le Catalogue.

Le code de l'outil reste lisible : `main.pyw` contient la fenêtre et `logic.py` peut contenir la logique métier.

## Règle simple

Utiliser les composants du SDK : le modèle embarque `ui.py` pour rester autonome. Ne pas définir de couleurs directement dans l'outil ni recréer une API locale différente du modèle.

Le SDK est une base de développement. La signature et la publication restent des opérations séparées du parcours normal.

Le SDK livré avec le Launcher 1.4.0 correspond à son API. Les helpers `open_file`, `open_path`, `confirm`, `choose_file`, `choose_folder` et `get_app_info` ne sont pas fournis par le Launcher public 1.3.0 : pour cette cible, prévoir une compatibilité explicite, comme dans Files. Les icônes Windows se lisent avec `QFileIconProvider` ; l’API ne fournit pas de méthode d’extraction d’icônes.
