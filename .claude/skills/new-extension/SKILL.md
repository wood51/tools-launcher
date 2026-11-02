---
name: new-extension
description: Créer ou modifier un outil, plugin ou thème Tools Launcher avec le SDK commun.
---

# Créer avec le SDK

1. Lire le projet concerné et son `PROJECT.md` s’il existe, puis [sdk/README.md](../../../sdk/README.md).
2. Lire seulement [UI_STANDARD.md](../../../sdk/UI_STANDARD.md), [API.md](../../../sdk/API.md) et le [modèle utile](../../../sdk/templates/).
3. Créer ou modifier le vrai code, puis vérifier le parcours demandé.

Création par défaut ; apprentissage uniquement si demandé. Une demande précise ne déclenche pas de questionnaire. Ne pas charger toute la documentation ni tout l’historique.

## Construire

- Un seul projet, généralement dans `projects/<id>/`. Préserver le travail local et les données.
- Interface française, code anglais. Réutiliser les composants fournis avec le modèle et l’API du Launcher, en vérifiant la version ciblée.
- Ne pas modifier `core/` pour une extension. Si le contrat paraît insuffisant, vérifier les fonctions réellement disponibles dans `core/api.py` ou `core/plugin_api.py`.
- Garder les dépendances nécessaires fixées dans `requirements.txt`. Le ZIP exclut secrets, données et environnement Python.

## Vérifier et livrer

Outil autonome : essayer `install_dev.cmd` et `run_dev.cmd` hors du Launcher. Plugin ou thème : essayer dans une copie du Launcher. Outil double : vérifier les deux parcours. Contrôler aussi l’interface visible.

Quand le ZIP est demandé, utiliser `build_zip.cmd`, inspecter l’archive et essayer sa copie extraite. Un plugin dépend du Launcher ; une entrée Python seule ne constitue pas une édition EXE.

ZIP local, signature et publication sont trois actions distinctes ; signer et publier uniquement sur demande. Aucun rapport supplémentaire : mettre à jour le `PROJECT.md` existant seulement si l’état durable change.
