import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.paths import CORE_DIR, ICONS_DIR, PYTHONW
from core.catalog.index import find_updates
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QActionGroup, QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from core.theme import apply_theme, discover_themes, get_theme, set_theme
from core.registry import discover_tools, launch_tool
from core.channel import ChannelServer
from core.menus import LeftSubMenu
from core.plugin_api import PluginHost
from core.plugin_loader import load_plugins


def tool_icon(tool: dict) -> QIcon:
    """Icône du manifeste (champ `icon`, relatif au dossier de l'outil), sinon icône générique."""
    icon_file = tool.get("icon")
    if icon_file:
        path = tool["folder"] / icon_file
        if path.exists():
            return QIcon(str(path))
    return DEFAULT_TOOL_ICON


def rebuild_tools_menu() -> None:
    tools_menu.clear()
    tools = discover_tools()
    if not tools:
        tools_menu.addAction("(aucun outil)").setEnabled(False)
        return
    for tool in tools:
        action = tools_menu.addAction(tool_icon(tool), tool["name"])
        action.setToolTip(tool.get("tooltip", ""))
        action.triggered.connect(lambda checked=False, t=tool: run_tool(t))


def rebuild_theme_menu() -> None:
    current = get_theme()
    theme_menu.clear()

    for name, theme in discover_themes().items():
        action = theme_menu.addAction(theme["label"])
        action.setCheckable(True)
        action.setChecked(name == current)
        theme_group.addAction(action)
        action.triggered.connect(lambda checked=False, n=name: set_theme(n, app))


def run_tool(tool: dict) -> None:
    """Lance l'outil et signale par une notification s'il s'arrête aussitôt avec une erreur."""
    process = launch_tool(tool)

    def report() -> None:
        if process.poll() not in (None, 0):
            host.notify(
                tool["id"],
                f"« {tool.get('name', 'Outil')} » s'est arrêté",
                "Détails dans core/data/plugins.log",
                "error",
            )

    QTimer.singleShot(5000, report)


#### Mises à jour des extensions ####


class UpdateChecker(QObject):
    found = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.running = False

    def check(self) -> None:
        """Compare au catalogue dans un thread (le partage peut être lent) ; `found` part dans le thread Qt."""
        if self.running:
            return
        self.running = True

        def work() -> None:
            try:
                updates = find_updates()
            except Exception:
                updates = []
            self.running = False
            self.found.emit(updates)

        threading.Thread(target=work, daemon=True).start()


def on_updates(updates: list) -> None:
    global notified_updates
    if not updates:
        host.badges.pop("catalog", None)
        host.refresh_icon()
        notified_updates = set()
        return
    host.badges["catalog"] = "blue"
    host.refresh_icon()
    current = {(u["id"], u["version"]) for u in updates}
    if current - notified_updates:  # n'avertit que pour une nouveauté
        notified_updates = current
        names = ", ".join(u["name"] for u in updates)
        host.notify("catalog", "Mises à jour disponibles", names, "info", open_catalog)


def open_catalog() -> None:
    run_tool({"id": "catalog", "name": "Catalogue", "folder": CORE_DIR / "catalog", "entry": "main.pyw"})
    QTimer.singleShot(15000, update_checker.check)  # reprend le badge après une installation


def open_settings() -> None:
    run_tool({"id": "settings", "name": "Paramètres", "folder": CORE_DIR / "settings", "entry": "main.pyw"})


def restart_launcher() -> None:
    """Un processus relais relance le lanceur une fois celui-ci arrêté (le verrou est alors libre)."""
    launcher = str(CORE_DIR / "launcher.pyw")
    code = (
        "import subprocess, time; time.sleep(3); "
        f"subprocess.Popen([{str(PYTHONW)!r}, {launcher!r}], creationflags=subprocess.CREATE_NO_WINDOW)"
    )
    subprocess.Popen([str(PYTHONW), "-c", code], creationflags=subprocess.CREATE_NO_WINDOW)
    app.quit()


app = QApplication(sys.argv)
apply_theme(app)

DEFAULT_TOOL_ICON = QIcon(str(ICONS_DIR / "tool.svg"))

app.setQuitOnLastWindowClosed(False)  # pas de fenêtre, mais on reste ouvert

tray = QSystemTrayIcon(QIcon(str(ICONS_DIR / "launcher.ico")))
tray.setToolTip("Mes outils")

menu = QMenu()
menu.setLayoutDirection(Qt.RightToLeft)  # flèches des sous-menus vers la gauche

tools_menu = LeftSubMenu("Outils", menu)
menu.addMenu(tools_menu)
tools_menu.setToolTipsVisible(True)
tools_menu.aboutToShow.connect(rebuild_tools_menu)  # reconstruit à chaque ouverture

launcher_menu = LeftSubMenu("Launcher", menu, has_submenus=True)
menu.addMenu(launcher_menu)

theme_menu = LeftSubMenu("Thème", launcher_menu)
launcher_menu.addMenu(theme_menu)
theme_group = QActionGroup(theme_menu)
theme_menu.aboutToShow.connect(rebuild_theme_menu)

launcher_menu.addAction("Catalogue…", open_catalog)
launcher_menu.addAction("Paramètres…", open_settings)

menu.addSeparator()
menu.addAction("Quitter", app.quit)

host = PluginHost(
    tray, menu, launcher_menu.menuAction()
)  # les plugins s'insèrent avant Launcher
channel = ChannelServer(host, on_restart=restart_launcher)
if not channel.start():  # le nom est pris : un autre lanceur tourne déjà
    sys.exit(0)

load_plugins(host)

tray.setContextMenu(menu)
tray.show()
host.run_start()

notified_updates: set = set()
update_checker = UpdateChecker()
update_checker.found.connect(on_updates)
QTimer.singleShot(3000, update_checker.check)
update_timer = QTimer()
update_timer.timeout.connect(update_checker.check)
update_timer.start(60 * 60 * 1000)  # toutes les heures

app.aboutToQuit.connect(host.run_quit)

sys.exit(app.exec())
