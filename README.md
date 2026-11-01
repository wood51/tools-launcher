# Tools Launcher

Lanceur d'outils pour Windows. Une icône dans la zone de notification ouvre un menu :

- **Outils** : de petites applications, chacune dans sa fenêtre.
- **Plugins** : des entrées ajoutées directement au menu.
- **Thèmes** : des palettes de couleurs partagées par toutes les fenêtres.
- **Launcher** : paramètres, choix du thème et **Catalogue**.

Le lanceur lui-même ne fait presque rien : tout le reste est une **extension**, installée depuis un **catalogue**, vérifiée avant d'être exécutée. Python et PySide6 (Qt 6).

## Installation

Commencez par le [guide PDF](docs/installation/Guide-installation-Windows.pdf) ou le [LIRE-MOI](docs/installation/LIRE-MOI.txt), disponibles séparément sur la page de release et dans le ZIP. Présentation pages 1–2 ; installation à partir de la page 3.

**Essayez d'abord de lancer l'application.** Python est à installer seulement si le PC le demande ou ouvre le Microsoft Store. Dans ce cas, installez **Python 3.13**, publié par **Python Software Foundation**, depuis le [Microsoft Store](https://apps.microsoft.com/detail/9pnrbtzxmb4z?hl=fr-FR&gl=FR), puis relancez le même fichier. Si le launcher démarre, cette étape est inutile. Aucune commande ni vérification de version n'est demandée dans le guide.

1. Téléchargez `ToolsLauncher.zip` depuis le [site officiel](https://wood51.github.io/tools-launcher/#installer) et dézippez-le dans un dossier **définitif** (le `.venv` créé au premier lancement n'est pas déplaçable).
2. Lancez `Lancer Tools Launcher.cmd`. Une fenêtre « Préparation… » crée l'environnement et télécharge PySide6 (environ 80 Mo), une seule fois.
3. L'icône apparaît dans la zone de notification (parfois sous la flèche ^). **Launcher > Catalogue > Source…** ajoute vos sources. **Launcher > Paramètres** règle les favoris et les catégories des outils (favoris en haut du menu de l'icône),  le démarrage avec Windows, le raccourci du bureau, les notifications et les plugins.

Si Python est mis à jour par le Store et que le lanceur ne démarre plus, relancez `Lancer Tools Launcher.cmd` : l'environnement se répare tout seul (réglages et extensions conservés).

Vérifiez les fichiers téléchargés (après le premier lancement, le `.venv` contient ce qu'il faut) : `SHA256SUMS` donne leurs empreintes et `SHA256SUMS.sig` est sa signature.

```
.venv/Scripts/python.exe scripts/sign.py verify SHA256SUMS
.venv/Scripts/python.exe scripts/sign.py fingerprint
```

La seconde commande affiche l'empreinte de chaque clé de confiance. Comparez-la, **par un autre canal que ce dépôt**, à celle de l'auteur :

```
wood51 · wood51
  9ed2 b7bf b829 d8b3 4b9b 9e60 04d5 1363 8e33 d30b db92 2f45 02ac a69c 9aef bacb
```

## Installation vierge

Le launcher est livré **sans extension, plugin ni thème supplémentaire**. Les apparences Sombre et Clair font partie du noyau. Le menu Outils et le Catalogue sont initialement vides ; les extensions s'ajoutent ensuite selon vos besoins.

Depuis la version **1.3.0**, le ZIP est vierge et contient le guide PDF et le LIRE-MOI. Ceux-ci sont aussi disponibles séparément. La release 1.2.0 conserve son contenu historique.

## Comment ça marche

### Extensions
Une extension est un dossier avec un `extension.json` (nom, version, et un bloc `tool`, `plugin` ou `theme`), son code et éventuellement un `requirements.txt`. Un **outil** tourne dans son propre processus ; un **plugin** tourne dans le lanceur et passe par une API (`add_menu`, `notify`, `set_badge`, réglages…). Le détail est dans [`docs/EXTENSIONS.md`](docs/EXTENSIONS.md). Les données d'une extension sont dans son sous-dossier `data/`, jamais écrasé par une mise à jour.

### Catalogue et sources
Un **catalogue** est un `index.json` plus des zips versionnés. Le lanceur en lit plusieurs, appelées **sources** :
- un **dossier** (partage réseau, NAS…) ;
- un **dépôt Git en HTTPS** (GitHub, GitLab, serveur interne…), récupéré avec la bibliothèque dulwich, sans `git.exe`. Pour un dépôt privé, un **jeton en lecture seule** limité à ce dépôt suffit : il est chiffré avec DPAPI (lié à votre session Windows), jamais écrit en clair.

Une extension présente dans plusieurs sources vous laisse choisir celle à installer. Le lanceur vérifie les mises à jour au démarrage puis toutes les heures (badge bleu et notification) ; l'installation se fait toujours à la main, depuis le Catalogue. L'ancienne version est gardée pour un retour arrière.

### Signatures
Chaque zip d'extension contient un `SIGNATURE.json` (Ed25519) qui couvre son identifiant, sa version et le contenu de **tous** ses fichiers. Le lanceur ne l'installe depuis un catalogue que si la signature est valide **et** faite par une clé de `core/assets/trusted_keys.json`. Une clé peut être :
- **limitée** à certaines extensions (un auteur ne peut pas remplacer l'outil d'un autre) ;
- **révoquée**.

Le catalogue (`index.json`) n'est qu'une liste, il n'est pas signé : quelqu'un qui peut écrire dans le dossier ou le dépôt peut masquer une mise à jour, mais pas faire installer du code non signé, ni une autre version que celle annoncée, ni une version plus ancienne que celle installée. Un zip glissé à la main sans signature reste installable, avec l'avertissement « Provenance NON vérifiée ».

Une extension est du code exécuté avec vos droits : ne faites confiance qu'aux clés dont vous connaissez le propriétaire.

## Publier ses propres extensions

```
python scripts/sign.py keygen <id> "<Nom affiché>"
python scripts/publish.py <extension | fichier.zip> --catalog <dossier du catalogue>
```

- `keygen` crée votre clé privée (chiffrée par mot de passe, dans `~/.tools_launcher_signing/`, jamais dans un dépôt) et ajoute la clé publique à `core/assets/trusted_keys.json`. **Sauvegardez la clé privée hors ligne** : sans elle, impossible de signer.
- `publish.py` empaquette, signe et ajoute l'extension au catalogue (zip versionné, `index.json`). Une version publiée ne s'écrase pas.
- Pour un catalogue Git, `--catalog` désigne un clone local : commitez et poussez ensuite.
- Pour que d'autres lanceurs acceptent votre clé, sa partie publique doit figurer dans leur `trusted_keys.json`.
- `scripts/sign.py sign-zip` signe un zip existant ; `resign-catalog` signe tous les zips d'un catalogue déjà publié.

### Avec Claude
Le dossier [`.claude/skills/new-extension/`](.claude/skills/new-extension) est un skill qui génère une extension à partir d'une description (questionnaire, résumé, puis code). Il est aussi fourni en zip dans chaque release. L'extension produite n'est **pas signée** : relisez son code, puis signez-la et publiez-la comme ci-dessus.

## Licence

[MIT](LICENSE).
