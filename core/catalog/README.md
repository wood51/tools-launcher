# Catalogue (noyau)

Fait partie du lanceur (menu Launcher > Catalogue), pas une extension : il peut donc remplacer n'importe quelle extension.

Installe, met à jour et retire des extensions.

- **Sources** : « Source… » gère la liste des sources (dossier ou partage, dépôt Git en HTTPS avec jeton chiffré), chacune activable. Une extension présente dans plusieurs sources vous laisse choisir laquelle installer. Les extensions sont listées avec leur état (non installée, installée, mise à jour disponible).
- **Clés de confiance…** : affiche les clés publiques connues et importe un fichier `.pub.json`, sans installer l’outil Publication et sans clé privée. Avant approbation, l’écran présente le signataire, l’empreinte SHA-256 à comparer par un autre canal et les identifiants des outils autorisés (vide = tous les outils). Les clés importées restent dans `core/data/trusted_keys.json`, préservé lors des mises à jour. Une clé existante n’est pas remplacée par import ; les révocations et restrictions distribuées avec le Launcher restent prioritaires. Les clés locales autorisent les extensions, pas la signature des versions du Launcher.
- **Retirer la confiance** : sélectionner une clé, puis confirmer son retrait. Ses prochaines installations et mises à jour seront refusées ; les outils déjà installés restent présents. Le retrait est mémorisé localement, y compris pour une clé livrée avec le Launcher. **Rétablir la confiance** permet d’annuler ce choix ; une clé révoquée par le distributeur ne peut pas être réactivée localement.
- **Vérifications avant installation** : empreinte SHA-256 de l'index vérifiée sur la copie locale, signature Ed25519 du zip (`SIGNATURE.json`, clé distribuée dans `core/assets/trusted_keys.json` ou approuvée localement, obligatoire sauf source marquée « non signée »), et le zip doit contenir l'id et la version annoncés et être plus récent que l'installé.
- **Glisser-déposer** : déposer un `.zip` ou un dossier d'extension n'importe où dans la fenêtre (sans signature : « Provenance NON vérifiée »).
- **Avant d'installer** : la fenêtre résume le contenu (outil, plugin, thème), le signataire, les paquets Python demandés et rappelle que le code s'exécute avec vos droits.
- **Mise à jour** : le dossier `data/` de l'extension est conservé ; l'ancienne version est gardée une génération dans `.extensions_backup/` (bouton « Revenir à… »).
- **Désinstaller** : au choix, garder ou supprimer les données.
- Un plugin installé ou mis à jour s'active au prochain démarrage du lanceur ; un outil ou un thème tout de suite.
- Si l'extension est ouverte (outil en cours), l'installation est refusée : la fermer d'abord.

Publier : `python scripts/publish.py <id | zip> --catalog <dossier> --notes "ce qui change"` signe l'extension, crée le zip versionné et met à jour `index.json`.

Code : `main.pyw` (fenêtre), `index.py` (lecture des index, mises à jour), `sources.py` (sources, jetons, Git), `sources_dialog.py` (gestion des sources), `public_keys_dialog.py` (approbation des clés publiques).
Données : `core/data/catalog.json` (liste des sources), `core/data/catalog_git/` (copies locales des dépôts Git), `core/data/trusted_keys.json` (clés publiques approuvées sur ce poste).
