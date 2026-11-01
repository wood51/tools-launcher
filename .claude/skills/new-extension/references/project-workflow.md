# Continuité d'un projet d'extension

Créer des outils utilisables par conversation ; l'utilisateur n'a pas à connaître Python ou à tenir une documentation technique. Le même projet peut être repris avec différents assistants et sur différents postes.

## Reprendre

Identifier le dossier de sources, distinct de l'extension installée et des ZIP. Lire les instructions du projet et `PROJECT.md` s'il existe, puis les fichiers actuels. Dans un dépôt Git, vérifier l'état, la branche et les changements disponibles avant modification ; préserver les travaux locaux. Utiliser les dernières références compatibles réellement disponibles et indiquer si leur fraîcheur n'a pas pu être vérifiée.

Les références de ce skill sont un instantané. Si le dépôt du launcher est disponible, comparer son API et ses contrats actuels. Ne pas mettre à jour automatiquement les bibliothèques, ni remplacer un shim sans vérifier sa compatibilité et le fonctionnement autonome.

## Créer ou faire évoluer

L'assistant réalise par défaut la demande autorisée. Si l'utilisateur veut apprendre, avancer par petites notions et exercices issus de son outil, puis vérifier son travail. Ne pas lui imposer de cours pour obtenir une extension. Les décisions et autorisations déjà exprimées ne doivent pas être redemandées.

Tenir un seul `PROJECT.md` court à la racine du projet de sources. Pour une extension embarquée, il peut être dans son dossier. Pour un projet comprenant code, tests et fabrication de ZIP, le garder à côté de ces éléments, hors du dossier livré. Regrouper les rubriques lorsqu'il s'agit d'un petit outil : pas de dossier documentaire complet imposé.

```markdown
# Suivi de <nom>

## Besoin
Public, résultat attendu, exemples et limites convenus.
Usage et destination de publication si utiles (personnel, professionnel ou partagé).

## Versions et sources
Date de vérification, dépôt et branche si présents ; version dans le manifeste.
Version du launcher / révision du skill utilisés, version publiée et version installée si connues.
Si un élément n'a pas été vérifié, le dire. Aucun secret ni chemin métier sensible.

## État et vérifications
Ce qui fonctionne, travail en cours, résultats datés des essais et limites.
Indiquer les fichiers non commités et si la reprise reste uniquement locale.

## Décisions
Choix utiles à la reprise et leurs raisons ; éviter l'historique des discussions.

## Prochaine action
La prochaine étape concrète et les éventuels blocages.
```

À chaque étape utile, mettre à jour ce suivi et le README d'utilisation si nécessaire. Ne pas présenter un test hors écran comme une validation visuelle. Les projets parallèles utilisent des branches et des dossiers de travail distincts ; la reprise successive garde le contexte de la tâche.

## Capitaliser

Une recette réutilisable et éprouvée peut enrichir le carnet du projet ou, dans le dépôt du launcher, `docs/snippets.md` : but, petit exemple, piège et source actuelle. Un choix propre à l'outil reste dans son suivi. Une correction du contrat commun doit être vérifiée avec le code et les références du skill avant diffusion ; ne pas retoucher un skill global installé sans autorisation.

Le suivi reste dans les sources. Ne pas ajouter aux ZIP les notes de travail `PROJECT.md`, instructions d'assistants, tests, données utilisateur, secrets ou dossiers Git. Le README destiné à l'utilisateur reste livré. Ne jamais fabriquer de signature. Pour changer de poste, les sources et le suivi doivent être transférés par un moyen autorisé ; dans Git, commit et push nécessitent la demande correspondante.
