# Thème et styles

## Principe

Chaque outil est un processus avec son `QApplication` : il appelle `api.apply_theme(app)` juste après l'avoir créé. Le thème choisi dans le menu **Thème** du lanceur est écrit dans `core/data/settings.json` ; les outils ouverts le surveillent et changent de thème en direct. Le style est une feuille QSS (sous-ensemble de CSS de Qt : pas de variables, d'où des jetons `@NOM` remplacés par les couleurs du thème).

## Écrire une interface qui suit le thème

- Pas de couleur écrite en dur dans un widget : laisser la feuille de style commune faire, ou utiliser les identifiants ci-dessous.
- Widget central : `setObjectName("root")` (ou `QMainWindow`).
- « Classe » de style : `widget.setObjectName("primary")` ou propriété `widget.setProperty("hover", True)` puis `widget.style().unpolish(widget); widget.style().polish(widget)` pour réévaluer.

Identifiants fournis par la feuille commune :

| Cible | Effet |
|---|---|
| `QLabel#title` | grand titre (18 pt, gras) |
| `QLabel#subtitle`, `QLabel#muted` | texte secondaire (couleur `MUTED`) |
| `QFrame#card` | carte : fond `SURFACE`, bordure, coins arrondis ; `QLabel#cardValue` (grande valeur) et `QLabel#cardLabel` (légende) dedans |
| `QPushButton` | bouton standard |
| `QPushButton#primary` | action principale (fond `ACCENT`, texte `ON_ACCENT`) |
| `QPushButton#toggle` | bouton à bascule (`checkable`), teinte d'avertissement une fois coché |
| `QPushButton#link` | bouton en forme de lien |
| `QFrame#drop` + propriété `hover="true"` | zone de glisser-déposer (bordure pointillée, accent au survol) |
| `QTableWidget`, `QHeaderView`, `QProgressBar` (fine), `QScrollBar`, `QComboBox`, `QLineEdit`, `QGroupBox`, `QTabWidget`, `QToolTip`, `QMenu`, `QMessageBox`, `QDialog` | déjà stylés |

Police : Segoe UI 10 pt. Pour un style absent de la liste, ajouter une règle locale avec `widget.setStyleSheet(...)` **en n'utilisant que des couleurs lues du thème**, ou un fichier `.qss` d'un thème ; sinon accepter le style par défaut.

## Jetons de couleur (16)

`BG` (fond des fenêtres), `SURFACE` (cartes, tables), `SURFACE_2` (boutons, champs, en-têtes), `BORDER`, `TEXT`, `MUTED` (texte secondaire), `ACCENT`, `ACCENT_HOVER`, `ALT_ROW` (lignes alternées), `HOVER_ROW`, `SELECTION`, `SELECTION_STRONG`, `WARN`, `WARN_BG`, `DROP_HOVER`, `ON_ACCENT` (texte sur l'accent).

Thème sombre de référence (`dark.json`) :
`BG #0f1218`, `SURFACE #171b24`, `SURFACE_2 #1e2330`, `BORDER #2a3040`, `TEXT #e6e9ef`, `MUTED #8b93a7`, `ACCENT #4173d1`, `ACCENT_HOVER #6a9dff`, `ALT_ROW #1a1f2a`, `HOVER_ROW #232a3a`, `ON_ACCENT #ffffff`.

Thème clair (`light.json`) :
`BG #f4f6fa`, `SURFACE #ffffff`, `SURFACE_2 #eceff5`, `BORDER #d3d9e4`, `TEXT #1b2130`, `MUTED #5f6880`, `ACCENT #2f6fed`, `ACCENT_HOVER #4d85f2`, `ALT_ROW #f7f9fc`, `HOVER_ROW #e8edf7`, `SELECTION #cddcfb`, `SELECTION_STRONG #bcd0fa`, `WARN #b36b00`, `WARN_BG #fff1d6`, `DROP_HOVER #eef3ff`, `ON_ACCENT #ffffff`.

## Créer un thème

Un fichier JSON de couleurs (`label`, `scheme` `dark`/`light`, `colors` ; les jetons absents viennent du sombre) dans une extension de type `theme` (voir `skeletons.md`). Vérifier les contrastes (rapport WCAG) : `TEXT` sur `BG` et `SURFACE` ≥ 4,5 ; `ON_ACCENT` sur `ACCENT` ≥ 4,5 ; `MUTED` sur `SURFACE` ≥ 3 au moins. Formule : luminance relative `L = 0,2126 R + 0,7152 G + 0,0722 B` (composantes linéarisées), contraste `(L1 + 0,05) / (L2 + 0,05)`, `L1` la plus claire.
