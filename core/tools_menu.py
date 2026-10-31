"""Organisation du menu Outils : favoris et catégories. Stdlib seulement, sans Qt.

Réglages dans `core/data/config.json`, section `tools` :
- `favorites` : ids des outils affichés en haut du menu principal ;
- `categories` : `{id: nom}` qui remplace la catégorie proposée par l'auteur (`category` du manifeste) ;
  un nom vide range l'outil à la racine ;
- `group` : regrouper les outils par catégorie (sous-menus) ; sinon liste plate.
"""

from dataclasses import dataclass, field

from core.config import get_section, set_section

SECTION = "tools"
MAX_CATEGORY = 40


@dataclass
class Layout:
    favorites: list[dict] = field(default_factory=list)  # outils favoris, par nom
    groups: list[tuple[str, list[dict]]] = field(default_factory=list)  # (catégorie, outils), catégories par nom
    loose: list[dict] = field(default_factory=list)  # outils sans catégorie (ou tous si pas de regroupement)


def load_settings() -> dict:
    """Réglages normalisés : valeurs invalides ignorées, rien ne lève."""
    raw = get_section(SECTION)
    favorites = [i for i in raw.get("favorites", []) if isinstance(i, str)] if isinstance(raw.get("favorites"), list) else []
    categories = raw.get("categories") if isinstance(raw.get("categories"), dict) else {}
    return {
        "favorites": favorites,
        "categories": {k: clean_category(v) for k, v in categories.items() if isinstance(k, str) and isinstance(v, str)},
        "group": raw.get("group") is True,
    }


def save_settings(settings: dict) -> None:
    set_section(SECTION, settings)


def clean_category(name: str) -> str:
    """Nom de catégorie : espaces nettoyés, longueur limitée."""
    return " ".join(name.split())[:MAX_CATEGORY]


def effective_category(tool: dict, settings: dict) -> str:
    """Catégorie réglée par l'utilisateur, sinon celle de l'auteur, sinon vide."""
    chosen = settings["categories"].get(tool["id"])
    return clean_category(chosen) if chosen is not None else clean_category(tool.get("category", ""))


def organize(tools: list[dict], settings: dict) -> Layout:
    by_name = sorted(tools, key=lambda t: t["name"].lower())
    layout = Layout(favorites=[t for t in by_name if t["id"] in settings["favorites"]])
    if not settings["group"]:
        layout.loose = by_name
        return layout
    groups: dict[str, list[dict]] = {}
    for tool in by_name:
        category = effective_category(tool, settings)
        if category:
            groups.setdefault(category, []).append(tool)
        else:
            layout.loose.append(tool)
    layout.groups = sorted(groups.items(), key=lambda item: item[0].lower())
    return layout


def known_categories(tools: list[dict], settings: dict) -> list[str]:
    """Catégories déjà en usage (pour la liste de choix des Paramètres)."""
    names = {effective_category(t, settings) for t in tools} - {""}
    return sorted(names, key=str.lower)
