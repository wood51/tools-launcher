# Centièmes ↔ heures

Convertit une durée entre quatre formats, qui se mettent à jour ensemble pendant la frappe :

| Format | Exemple |
|---|---|
| Heures : minutes | `1:30` ou `1h30` |
| Minutes | `90` |
| Heures décimales | `1,5` |
| Centièmes d'heure (1 h = 100) | `150` |

- La virgule et le point sont acceptés. Une saisie invalide est entourée en couleur d'avertissement, avec un message ; les autres champs ne bougent pas.
- Sous les champs : la durée exacte à la seconde (`H:MM` est arrondi à la minute la plus proche).
- **Cumul** : *Entrée* (ou *Ajouter*) place la durée saisie dans une liste ; le total s'affiche en H:MM, centièmes, heures décimales et minutes, avec copie en un clic. *Suppr* retire la ligne choisie. La liste est conservée entre deux ouvertures (dossier `data/` de l'extension).

Les calculs utilisent des fractions exactes : aucune dérive d'arrondi entre les formats, l'arrondi n'a lieu qu'à l'affichage.
