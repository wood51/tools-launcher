from typing import Callable

from PySide6.QtCore import QRectF
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from core import winnotify
from core.api import ExtensionAPI, log_error
from core.config import get_section
from core.menus import LeftSubMenu
from core.paths import ICONS_DIR, TRAY_ICONS
from core.toast import ToastManager


def safe_call(plugin_id: str, fn: Callable, *args) -> None:
    """Un plugin qui plante ne doit jamais faire tomber le lanceur."""
    try:
        fn(*args)
    except Exception as e:
        log_error(plugin_id, e)


BADGE_COLORS = {"blue": "#0a6cff", "red": "#ff2d2d"}


def badge_icon(level: str | None) -> QIcon:
    """Icône du lanceur ; avec un badge, un gros point à bord blanc dessiné en bas à droite à chaque taille."""
    base = QIcon(str(ICONS_DIR / TRAY_ICONS[None]))
    if level not in BADGE_COLORS:
        return base
    icon = QIcon()
    for size in (16, 24, 32, 48, 64):
        pixmap = base.pixmap(size, size)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        diameter = size * 0.7
        ring = max(1.5, size / 12)
        rect = QRectF(size - diameter, size - diameter, diameter, diameter)
        painter.setPen(QPen(QColor("white"), ring))
        painter.setBrush(QColor(BADGE_COLORS[level]))
        painter.drawEllipse(rect.adjusted(ring / 2, ring / 2, -ring / 2, -ring / 2))
        painter.end()
        icon.addPixmap(pixmap)
    return icon


class PluginHost:
    """Ce que le lanceur partage avec les plugins : menu, icône, rappels de début et de fin."""

    def __init__(self, tray: QSystemTrayIcon, menu: QMenu, anchor: QAction) -> None:
        self.tray = tray
        self.menu = menu
        self.anchor = anchor  # les entrées des plugins s'insèrent avant cette action
        self.start_callbacks: list[tuple[str, Callable]] = []
        self.quit_callbacks: list[tuple[str, Callable]] = []
        self.badges: dict[str, str] = {}
        self.toasts = ToastManager()

    def run_start(self) -> None:
        for plugin_id, fn in self.start_callbacks:
            safe_call(plugin_id, fn)

    def run_quit(self) -> None:
        for plugin_id, fn in self.quit_callbacks:
            safe_call(plugin_id, fn)

    def notify(
        self,
        extension_id: str,
        title: str,
        message: str,
        level: str = "info",
        on_click: Callable[[], None] | None = None,
    ) -> None:
        """Notification selon la configuration (section `notifications` : `mode` toast ou windows ;
        `sound`). Le clic (`on_click`) n'existe que pour le toast du lanceur."""
        settings = get_section("notifications")
        sound = settings.get("sound") is True
        if settings.get("mode") == "windows":
            winnotify.show_toast(extension_id, title, message, sound)
        else:
            self.toasts.show(title, message, level, on_click)
            if sound:
                winnotify.play_sound(level)

    def refresh_icon(self) -> None:
        levels = set(self.badges.values())
        level = "red" if "red" in levels else "blue" if "blue" in levels else None
        self.tray.setIcon(badge_icon(level))


class PluginAPI(ExtensionAPI):
    """L'objet `api` reçu par `register(api)`. Un exemplaire par plugin."""

    def __init__(self, plugin_id: str, host: PluginHost) -> None:
        super().__init__(plugin_id)
        self._host = host

    def add_menu(
        self, title: str, build: Callable[[QMenu], None], icon: QIcon | None = None
    ) -> None:
        """Ajoute un sous-menu ; `build(menu)` est appelé à chaque ouverture pour le remplir."""
        submenu = LeftSubMenu(title, self._host.menu)
        submenu.setToolTipsVisible(True)
        if icon:
            submenu.setIcon(icon)

        def fill() -> None:
            submenu.clear()
            safe_call(self._id, build, submenu)

        submenu.aboutToShow.connect(fill)
        self._host.menu.insertMenu(self._host.anchor, submenu)

    def add_action(
        self, text: str, callback: Callable[[], None], icon: QIcon | None = None
    ) -> None:
        """Ajoute une entrée simple au menu principal."""
        action = QAction(text, self._host.menu)
        if icon:
            action.setIcon(icon)
        action.triggered.connect(lambda checked=False: safe_call(self._id, callback))
        self._host.menu.insertAction(self._host.anchor, action)

    def on_start(self, fn: Callable[[], None]) -> None:
        self._host.start_callbacks.append((self._id, fn))

    def on_quit(self, fn: Callable[[], None]) -> None:
        self._host.quit_callbacks.append((self._id, fn))

    def notify(
        self,
        title: str,
        message: str,
        level: str = "info",
        on_click: Callable[[], None] | None = None,
    ) -> None:
        """Notification du lanceur (toast maison, notification Windows ou les deux, au choix de
        l'utilisateur dans les Paramètres). `level` : info, warning ou error."""
        callback = (lambda: safe_call(self._id, on_click)) if on_click else None
        self._host.notify(self._id, title, message, level, callback)

    def set_badge(self, level: str | None) -> None:
        """`"blue"`, `"red"` ou `None` (retire le badge de ce plugin). Le rouge l'emporte."""
        if level is None:
            self._host.badges.pop(self._id, None)
        elif level in ("blue", "red"):
            self._host.badges[self._id] = level
        else:
            raise ValueError(f"badge inconnu : {level}")
        self._host.refresh_icon()
