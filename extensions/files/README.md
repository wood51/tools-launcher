# Fichier

Menu **Fichier** : une liste de fichiers favoris, chacun ouvert avec l'application choisie (ou celle de Windows), avec l'icône de l'application.

- **Plugin** (`main.py`) : le menu. Une entrée est grisée si le fichier a disparu.
- **Outil** (`editor.pyw`) : éditeur de la liste, accessible par « Modifier la liste » ou le menu Outils. Glisser-déposer des fichiers, nom modifiable, choix de l'application, suppression (touche Suppr).
- **Logique** (`files.py`, sans Qt) : lecture, validation, écriture de la liste. Partagée par le plugin et l'éditeur.

Données : `data/files.json` (et `data/files.json.bak`, écrit avant chaque sauvegarde). Non versionnées.
