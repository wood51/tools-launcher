from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu


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
