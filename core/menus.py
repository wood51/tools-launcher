from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QWidget, QWidgetAction


class LeftSubMenu(QMenu):
    """Sous-menu qui s'ouvre à gauche de son parent, en gardant l'icône à gauche du texte.

    `has_submenus=True` : le sous-menu contient lui-même des sous-menus ; il prend alors la
    direction droite à gauche du menu principal pour que leurs flèches pointent aussi à gauche.
    """

    def __init__(self, title: str, parent: QMenu, has_submenus: bool = False) -> None:
        super().__init__(title, parent)
        self.setLayoutDirection(Qt.RightToLeft if has_submenus else Qt.LeftToRight)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        parent = self.parentWidget()
        if isinstance(parent, QMenu):
            self.move(parent.geometry().left() - self.width() + 8, self.y())


class FavoriteRow(QWidget):
    """Ligne d'un favori dans le menu principal : icône à gauche, puis le nom.

    Le menu principal est en lecture de droite à gauche (flèches des sous-menus à gauche), ce qui placerait l'icône
    d'une action ordinaire à droite : la ligne force donc la lecture normale et reproduit le survol des entrées."""

    def __init__(self, menu: QMenu, icon: QIcon, text: str, tooltip: str, activated) -> None:
        super().__init__(menu)
        self._menu = menu
        self._activated = activated
        self.setObjectName("favorite")
        self.setLayoutDirection(Qt.LeftToRight)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setToolTip(tooltip)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 24, 6)
        layout.setSpacing(8)
        picture = QLabel()
        picture.setPixmap(icon.pixmap(18, 18))
        picture.setFixedSize(18, 18)
        label = QLabel(text)
        for child in (picture, label):
            child.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(picture)
        layout.addWidget(label, 1)

    def _set_hover(self, hover: bool) -> None:
        """Propriété `hover` pour le style (Qt ignore `:hover` d'un parent dans un sélecteur descendant)."""
        self.setProperty("hover", hover)
        for widget in (self, *self.findChildren(QLabel)):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def enterEvent(self, event) -> None:
        self._set_hover(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._set_hover(False)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self._menu.close()
            self._activated()
        else:
            super().mouseReleaseEvent(event)


def favorite_action(menu: QMenu, tool: dict, icon: QIcon, activated) -> QWidgetAction:
    action = QWidgetAction(menu)
    action.setText(tool["name"])
    action.setDefaultWidget(FavoriteRow(menu, icon, tool["name"], tool.get("tooltip", ""), activated))
    return action


def fill_tools_menu(tools_menu: QMenu, layout, add_tool) -> None:
    """Remplit « Outils » : sous-menus de catégories, puis outils sans catégorie. `layout` vient de
    `core.tools_menu.organize` ; `add_tool(menu, tool)` ajoute l'action d'un outil. Avec des sous-menus, le menu
    prend la direction droite à gauche (flèches à gauche) ; sans, la liste plate garde les icônes à gauche."""
    tools_menu.clear()
    if not layout.groups and not layout.loose:
        tools_menu.setLayoutDirection(Qt.LeftToRight)
        tools_menu.addAction("(aucun outil)").setEnabled(False)
        return
    tools_menu.setLayoutDirection(Qt.RightToLeft if layout.groups else Qt.LeftToRight)
    for category, members in layout.groups:
        submenu = LeftSubMenu(category, tools_menu)
        submenu.setToolTipsVisible(True)
        tools_menu.addMenu(submenu)
        for tool in members:
            add_tool(submenu, tool)
    if layout.groups and layout.loose:
        tools_menu.addSeparator()
    for tool in layout.loose:
        add_tool(tools_menu, tool)


def fill_favorites(menu: QMenu, anchor, favorites: list[dict], previous: list, make_action) -> list:
    """Insère les favoris en haut de `menu`, avant `anchor`, suivis d'un séparateur ; retire d'abord ceux de la
    fois précédente (`previous`). `make_action(tool)` crée l'action d'un outil. Renvoie les actions insérées."""
    for action in previous:
        menu.removeAction(action)
        action.deleteLater()
    created = []
    if favorites:
        for tool in favorites:
            action = make_action(tool)
            menu.insertAction(anchor, action)
            created.append(action)
        separator = QAction(menu)
        separator.setSeparator(True)
        menu.insertAction(anchor, separator)
        created.append(separator)
    return created
