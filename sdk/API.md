# API du SDK

## `sdk.ui`

### `create_app(name)`

Crée une `QApplication`, applique le thème Tools Launcher quand le launcher est disponible et retourne `(app, api)`.

### `window(title, width=520, height=360)`

Crée une fenêtre standard avec un widget racine et un layout vertical. Retourne `(widget, layout)`.

### `button(text, callback=None, variant="accent")`

Crée un bouton standard. Variantes : `accent` (style `primary` du thème), `neutral`, `danger`.
Les widgets utilisent les identifiants de style du launcher ; l'outil ne fournit jamais de couleur en dur.

### `field(label, placeholder="")`

Crée un champ texte avec son libellé. Retourne `(container, input)`.

### `show_error(parent, title, message)`

Affiche une erreur lisible dans une boîte de dialogue.

## Données

Quand l'outil tourne dans le launcher, `api.load_json(name)` et `api.save_json(name, data)` utilisent le dossier de données de l'extension. En mode autonome, le SDK utilise `data/` à côté de l'application.

Le code métier appelle la même API dans les deux modes. En autonome, les notifications sont journalisées localement et `launch_tool` est signalé comme indisponible ; dans le launcher, ces appels utilisent les services réels.

## API du launcher pour un outil

Contrat du Launcher **1.4.0**. Les versions 1.3.0 et antérieures n’exposent pas les helpers de fichiers, de choix, de confirmation et d’information ajoutés ci-dessous. Ne pas supposer leur présence pour une extension visant une ancienne version.

`get_api()` renvoie aussi :

- `api.id` : identifiant de l'extension ;
- `api.data_dir` : dossier de données ;
- `api.load_settings()` / `api.save_settings(data)` ;
- `api.log(message)` ;
- `api.notify(title, message, level="info")` ;
- `api.set_badge(level)` avec `blue`, `red` ou `None` ;
- `api.launch_tool(extension_id)` ;
- `api.apply_theme(app)`.
- `api.open_path(path)`, `api.open_file(path)` et `api.open_folder(path)` ;
- `api.choose_file(parent, title, filter)` et `api.choose_folder(parent, title)` ;
- `api.confirm(parent, title, message)` ;
- `api.get_app_info()`.

## API d'un plugin

Un plugin reçoit l'objet `api` dans `register(api)`. Il peut utiliser :

### `api.add_action(text, callback, icon=None)`

Ajoute une entrée directe au menu principal.

### `api.add_menu(title, build, icon=None)`

Ajoute un sous-menu. `build(menu)` est rappelé à chaque ouverture.

### `api.on_start(callback)` et `api.on_quit(callback)`

Enregistre une action au démarrage ou à la fermeture du launcher.

### `api.notify(title, message, level="info", on_click=None)`

Affiche une notification. Les niveaux sont `info`, `warning` et `error`.

### `api.set_badge(level)`

Affiche un badge bleu, rouge ou aucun badge sur l'icône du launcher.

Exemple minimal :

```python
def register(api) -> None:
    api.add_action("Tester", lambda: api.notify("Mon plugin", "Tout fonctionne."))
```
