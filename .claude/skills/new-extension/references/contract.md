# Le contrat d'une extension Tools Launcher

Copie condensée, valable sans le dépôt. Version de l'API décrite : **7 (étapes 1 à 7 de la migration, `core/api.py`)**. Si le dépôt est présent, ses fichiers (`CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/EXTENSIONS.md`, `core/api.py`) font foi en cas de différence.

## Le projet

Tools Launcher est un lanceur Windows en Python et PySide6 (Qt 6). Une icône dans la zone de notification ouvre un menu : **Outils** (les outils installés), **Plugins** (activer ou désactiver), entrées ajoutées par les plugins, **Thème**, **Quitter**. Un seul venv (`.venv`, `PySide6==6.12.0`) pour le lanceur et toutes les extensions. Point de lancement : `bootstrap.pyw` (crée le venv, installe les dépendances, lance `core/launcher.pyw`).

```
bootstrap.pyw
requirements.txt        PySide6_Essentials==6.12.0 (+ cryptography, dulwich)
core/                   le noyau (paquet Python `core`) : à ne jamais modifier pour une extension
  api.py  plugin_api.py  channel.py  deps.py  registry.py  theme.py  paths.py  toast.py  menus.py ...
  data/                 données du noyau (non versionné)
  assets/               icônes, themes/dark.json et light.json, theme.qss
extensions/<id>/        UNE extension par dossier : c'est là qu'on travaille
  extension.json  README.md  code...  requirements.txt (optionnel)
  data/                 données de l'extension (non versionné, jamais écrasé)
```

Installer une extension = **glisser son zip ou son dossier dans l'outil Catalogue** (menu Launcher > Catalogue), qui le contrôle, résume son contenu et l'installe après confirmation (un zip sans `SIGNATURE.json` s'installe avec l'avertissement « Provenance NON vérifiée » ; la signature est ajoutée par l'extension `publisher`, jamais à la main ; ou, à la main, déposer le dossier dans `extensions/`). Un **outil** apparaît au prochain ouverture du menu Outils ; un **plugin** est chargé au prochain démarrage du lanceur ; un **thème** apparaît au prochain ouverture du menu Thème.

## Les trois blocs

| | Outil (`tool`) | Plugin (`plugin`) | Thème (`theme`) |
|---|---|---|---|
| Rôle | programme avec sa fenêtre | ajoute au menu du lanceur, réagit à ses événements | palette de couleurs |
| Processus | séparé (`pythonw.exe` du venv) | **celui du lanceur** | aucun (fichier lu) |
| Plantage | sans effet sur le lanceur | journalisé, plugin ignoré | thème ignoré |

Une extension peut cumuler plusieurs blocs (ex. `files` : un plugin de menu et un outil éditeur). Un plugin tourne avec tous les droits de l'utilisateur dans le lanceur : pas de bac à sable, donc code relu, jamais de traitement long dans un callback.

## `extension.json`

```json
{
  "id": "mon_outil",
  "name": "Mon outil",
  "version": "1.0.0",
  "tooltip": "Ce que fait l'extension",
  "tool": { "entry": "main.pyw", "icon": "icon.svg" }
}
```

- Obligatoires : `id` (égal au nom du dossier ; minuscules, chiffres, `_`, `-`, commence par une lettre ou un chiffre), `name`, `version` (`1.2.3`), et au moins un bloc.
- `tooltip` optionnel (info-bulle du menu). `category` optionnel : catégorie proposée pour l'outil dans le menu Outils (texte court, par exemple « Bureau » ; l'utilisateur peut la changer ; sans lui, l'outil reste à la racine). `author` optionnel : simple mention affichée sur la carte du Catalogue (le signataire du zip fait foi, pas ce champ).
- Bloc `tool` : `entry` (obligatoire, script de l'outil), `name` (libellé du menu Outils ; sinon `name` de l'extension), `icon` (image ; sans elle, icône générique), `multiple` (booléen ; par défaut `false` : relancer un outil déjà ouvert ramène sa fenêtre au premier plan au lieu d'en ouvrir une seconde).
- Bloc `plugin` : `entry` (obligatoire, défini `register(api)`).
- Bloc `theme` : `file` (obligatoire, JSON des couleurs).
- Les chemins (`entry`, `file`, `icon`) sont relatifs au dossier de l'extension, **ne peuvent ni être absolus ni en sortir** (`..`), et `entry`/`file` doivent exister. Un manifeste invalide est ignoré avec un message, jamais bloquant.
- Chaque extension a un `README.md` : ce qu'elle fait, ses données, ses dépendances.

## Lancement d'un outil

Processus séparé : `.venv\Scripts\pythonw.exe <entry>`, `cwd` = dossier de l'extension, `PYTHONPATH` = racine du projet (donc `from core.api import get_api` fonctionne, et aussi `from extensions.autre.module import ...`), variable `TL_EXTENSION_ID` = id. `pythonw` n'affiche aucune erreur : pour déboguer, lancer avec `python.exe` dans un terminal depuis le dossier de l'extension, avec `PYTHONPATH` = racine.

Sortie d'erreur et plantages : le lanceur redirige la sortie de l'outil vers `core/data/plugins.log`, notifie si l'outil s'arrête aussitôt avec une erreur, et affiche une boîte d'erreur (une fois) pour une exception non attrapée. L'icône de la fenêtre vient du manifeste (`tool.icon`), sinon l'icône générique ; chaque outil a son groupe dans la barre des tâches. Un outil réservé au lanceur doit afficher un message clair s'il est lancé seul (voir `skeletons.md`).

## Dépendances

`requirements.txt` dans le dossier de l'extension : fusionné par le bootstrap (hash de tous les fichiers ; pip ne repasse que si ça change). **Versions fixées** (`paquet==x.y.z`). Une extension dont l'installation échoue est ignorée, le lanceur démarre quand même. Ne pas installer de paquet soi-même ; confirmer avec l'utilisateur puis avec le mainteneur avant d'ajouter une dépendance (code tiers).

## Règles

- Noms de dossiers, fichiers, fonctions et variables **en anglais** ; textes affichés à l'utilisateur **en français**.
- Commentaires courts, seulement quand nécessaires ; style cohérent avec l'existant (signatures typées `-> bool`).
- Données uniquement par l'API (`api.data_dir`, `load_settings`…), jamais par un chemin construit à la main ; écritures JSON par l'API (atomiques).
- `read_text()` / `write_text()` / `open()` toujours avec `encoding="utf-8"` (`utf-8-sig` en lecture pour tolérer un BOM).
- Tout `subprocess` lancé depuis un `.pyw` : `creationflags=subprocess.CREATE_NO_WINDOW`, sinon une console clignote.
- Une extension ne modifie pas `core/`. Si l'API manque, le dire.
- Confirmer avant toute action externe (push, installation).

## Pièges (Qt et Windows)

- `QIcon` n'accepte pas un `Path` : `QIcon(str(chemin))`.
- Les icônes SVG sont vides si `PySide6.QtSvg` n'a pas été importé ; `apply_theme` l'importe, donc l'appeler avant de créer les icônes (ou `from PySide6 import QtSvg`).
- Le widget central d'une fenêtre doit avoir `setObjectName("root")` (ou être un `QMainWindow`), sinon fond système et texte illisible en thème clair.
- Un `QFileSystemWatcher` sur un dossier inexistant échoue en silence : créer le dossier d'abord.
- `subprocess.run` renvoie un objet : tester `.returncode == 0`.
- `append` dans la boucle `for`, pas après.
- Un module ou dossier nommé `core`, `tools`, `plugins` à la racine peut en masquer un autre : ne pas nommer un module d'extension comme un module du noyau.
- Un plugin est importé comme un paquet : `from .autre import x` fonctionne, `import autre` non.
- Ctrl+F5 de VS Code tue les processus enfants à la fin du script : tester un lancement depuis un terminal.
- Windows lit en cp1252 par défaut : sans `encoding="utf-8"`, les accents sont abîmés.

## Sécurité

- Chemins du manifeste contenus dans le dossier de l'extension (refus sinon).
- Un plugin a tous les droits de l'utilisateur : relire le code, valider les entrées, ne jamais exécuter de texte venu d'un fichier ou du réseau (`eval`, `exec`, `shell=True`), ne jamais construire une commande par concaténation d'une entrée utilisateur.
- Ne rien écrire hors de `data/` sans raison ; ne jamais stocker de mot de passe ou jeton en clair dans `data/`.
- Un fichier de `data/` peut être absent, vide, corrompu ou édité à la main : toujours le lire en tolérant l'échec et valider ce qu'il contient.
- Une dépendance = du code tiers : version fixée, paquet connu, justifiée.
