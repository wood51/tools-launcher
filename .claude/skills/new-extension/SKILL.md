---
name: new-extension
description: >-
  Crée ou modifie une extension Tools Launcher (outil, plugin ou thème), pour le
  lanceur ou en version autonome, à partir du besoin de l'utilisateur. Fonctionne
  avec ou sans le dépôt Tools Launcher et assure le suivi des sources pour une
  reprise avec un autre assistant. À utiliser pour créer ou faire évoluer une extension.
---

# Créer une extension Tools Launcher

Quand ce skill est invoqué, l'utilisateur (le mainteneur du lanceur, un proche ou un collègue) délègue : **l'assistant écrit le code**. Un mode apprentissage reste possible sur demande, par petites étapes. Les règles de nommage, de style et de sécurité sont dans `references/contract.md`.

## 0. D'où je lis les règles

Ce skill est **autonome** : tout ce qu'il faut est dans `references/` (à côté de ce fichier). Il marche dans une discussion qui ne connaît ni les outils ni le dépôt.

- `references/contract.md` : projet, blocs, `extension.json`, règles, pièges, sécurité.
- `references/api.md` : l'API (`get_api`, `PluginAPI`), signatures et comportements.
- `references/skeletons.md` : squelettes outil, plugin, deux blocs, thème.
- `references/theming.md` : thème, jetons de couleur, identifiants de style.
- `references/standalone.md` et `references/tl_shim.py` : version autonome d'un outil.
- `references/project-workflow.md` : reprise entre assistants, suivi `PROJECT.md`, versions et capitalisation. À lire pour une création ou une reprise ; garder le suivi proportionné à l'outil.

Si le dépôt Tools Launcher est accessible (dossiers `core/` et `extensions/` présents), lire en plus ses instructions d'entrée, `docs/WORKFLOW.md` et `docs/STATUS.md` s'ils existent, puis les fichiers actuels utiles (`README.md`, `docs/EXTENSIONS.md`, docstrings de `core/api.py` et `core/plugin_api.py`) et une extension proche pour son style. **En cas de différence, le dépôt fait foi** ; corriger les références dans le cadre d'un travail autorisé sur le skill, sinon signaler l'écart au mainteneur. Sans le dépôt, les références livrées restent suffisantes.

## 1. Préciser les fonctionnalités

Le but : aider l'utilisateur à décrire ce qu'il veut, pas écrire tout de suite. Avec `AskUserQuestion` si l'outil existe (1 à 4 questions à choix, ta recommandation en premier, plusieurs tours si besoin), sinon par une courte liste de questions numérotées à choix, faire préciser ce que la demande ne dit pas : ce que l'extension fait de bout en bout, ce qu'elle lit et produit, les données à garder, les cas limites (fichier absent, liste vide, erreur), les interactions avec le lanceur (menu, notification, badge) et une éventuelle dépendance externe. Ne pas demander ce qui a une valeur par défaut évidente ni ce que la demande dit déjà.

Poser **toujours** la question de la forme : **version lanceur** (déposée dans `extensions/`, thème et notifications du lanceur), **version autonome** (un outil qui tourne seul ; voir `references/standalone.md`), ou **les deux** (un seul dossier qui marche des deux façons : choix recommandé pour un outil). Un plugin n'a pas de version autonome.

Proposer aussi 2 ou 3 ajouts utiles et peu coûteux quand l'idée est simple (mémoriser le dernier dossier, message quand la liste est vide, raccourci clavier, notification de fin d'une tâche longue), comme choix du questionnaire : jamais ajoutés d'office.

**Demande déjà précise** (petite correction, ajout nommé, pas de choix ouvert) : sauter le questionnaire et les ajouts, et n'écrire qu'une ligne de ce que tu vas faire. Résumé et OK restent pour une création ou dès qu'un choix est ouvert.

Puis **écrire un résumé** court : nom, type (`tool` fenêtre propre, `plugin` menu du lanceur, `theme` palette ; une extension peut cumuler), forme (lanceur, autonome ou les deux), fonctionnalités retenues sous forme de liste, données gardées, dépendance éventuelle, ce qui est volontairement exclu. Demander « OK ou à modifier ? » et **n'écrire aucun fichier avant le OK**. Si l'utilisateur modifie, mettre le résumé à jour et redemander.

`id` = nom du dossier (minuscules, chiffres, `_`, `-`), `version` `1.0.0` au départ.

## 2. Écrire (après le OK du résumé)

- Dossier `extensions/<id>/` dans le dépôt, sinon un dossier `<id>/` livré tel quel : `extension.json`, `README.md` (ce qu'elle fait, ses données), code.
- Tout passe par l'API (`references/api.md`). Jamais de chemin de données construit à la main, jamais d'écriture JSON directe (l'API écrit de façon atomique).
- Outil : suivre `references/skeletons.md` ; pour une version autonome ou double, suivre `references/standalone.md` et copier `references/tl_shim.py` à côté de `main.pyw`. Plugin : `register(api)`, rien de long dans un callback.
- Interface : identifiants de style de `references/theming.md`, jamais de couleur écrite en dur.
- `requirements.txt` seulement si nécessaire, versions fixées (`==`) ; une version autonome ou double a au minimum `PySide6_Essentials==6.12.0`. Ne pas installer soi-même ; confirmer avec l'utilisateur, puis le mainteneur, avant d'ajouter une dépendance externe.
- Ne jamais modifier `core/` pour une extension : si l'API manque, le dire à l'utilisateur et au mainteneur.
- Textes affichés en français, noms de code en anglais, commentaires courts et seulement si nécessaires.

## 3. Vérifier

Relire le code écrit pour la sécurité et la stabilité : chemins, `subprocess` (`creationflags=CREATE_NO_WINDOW`), entrées de l'utilisateur, données lues dans `data/` (fichier absent ou invalide), `encoding="utf-8"` partout, pièges de `references/contract.md`. Lancer l'outil (hors écran avec `QT_QPA_PLATFORM=offscreen`) ou charger le plugin si c'est possible sans effet de bord, et dire clairement ce qui n'a pas pu être testé (apparence, comportement d'une vraie fenêtre, lanceur réel) plutôt que prétendre l'avoir testé.

## 4. Terminer

Mettre à jour le suivi court `PROJECT.md` dans les sources, suivant `references/project-workflow.md`. Résumer en quelques lignes : ce qui a été créé, comment le lancer (menu Outils ; relancer le lanceur pour un plugin ; `python main.pyw` en autonome), ce qui n'est pas vérifié et la prochaine étape. Ne pas commiter ni pousser sans demande. Préciser si le travail reste uniquement local.

**Livraison** : un dossier `<id>/` ou, si un outil d'exécution de code est disponible, un zip `<id>.zip` (`extension.json` à la racine, sans `data/` ni `__pycache__`, notes `PROJECT.md`, instructions d'assistants ou tests). Garder le suivi dans les sources, hors du paquet livré. Deux parcours :

- **Version lanceur** (ou double) : le mainteneur **glisse le dossier ou le zip dans l'outil Catalogue** (menu Launcher > Catalogue) : il y est contrôlé, résumé, puis installé après son OK (un zip non signé affiche « Provenance NON vérifiée » : normal, la signature se fait à la publication ; ne jamais créer ni copier de `SIGNATURE.json`). Aucune autre manipulation (pas de copie dans `extensions/`, pas de commande).
- **Version autonome seule** : hors lanceur, il faut Python et `pip install -r requirements.txt` puis `python main.pyw`. Le dire clairement ; pour un collègue non technique, proposer plutôt la version lanceur.

Si l'utilisateur précise un choix durable pour son outil, le conserver dans `PROJECT.md`. Capitaliser une leçon réutilisable dans le carnet ou les règles communes du projet, sans dépendre d'un plugin propre à un assistant. Une modification du skill installé ou une publication reste une action distincte à autoriser.
