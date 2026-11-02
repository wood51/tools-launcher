# Standard UI Tools Launcher

Cette feuille est la référence courte à respecter dans chaque outil.

## Principes

- Interface en français ; identifiants Python en anglais.
- Fenêtre principale avec un widget racine nommé `root`.
- Thème appliqué par `create_app()` ; aucune couleur en dur dans l'outil.
- Utiliser les composants du SDK avant de créer un style particulier.
- Les boutons restent courts et décrivent l'action : `Enregistrer`, `Annuler`, `Supprimer`.
- Les erreurs attendues sont affichées dans la fenêtre, jamais seulement dans la console.
- Les ascenseurs horizontaux sont désactivés sauf besoin réel.

## Identifiants de style

Le launcher fournit les styles communs. Le SDK les sélectionne avec `objectName` :

| Besoin | Identifiant |
|---|---|
| Action principale | `primary` |
| Action dangereuse | `danger` |
| Titre de page | `title` |
| Titre de section | `section` |
| Texte secondaire | `footer` |

Ne pas remplacer ces règles par des appels `setStyleSheet()` dans l'outil.
