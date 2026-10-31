from pathlib import Path

from PySide6.QtCore import QFileInfo
from PySide6.QtWidgets import QFileIconProvider, QMenu

from .files import load_files, open_file


def register(api) -> None:
    icons = QFileIconProvider()

    def open_entry(entry: dict) -> None:
        try:
            open_file(entry)
        except OSError as e:
            api.notify("Fichier", f"Impossible d'ouvrir {entry['name']} : {e}", "error")

    def build(menu: QMenu) -> None:
        files = load_files()
        if not files:
            menu.addAction("(aucun fichier)").setEnabled(False)
        for entry in files:
            action = menu.addAction(icons.icon(QFileInfo(entry.get("app") or entry["path"])), entry["name"])
            action.setToolTip(entry["path"])
            action.setEnabled(Path(entry["path"]).exists())
            action.triggered.connect(lambda checked=False, e=entry: open_entry(e))
        menu.addSeparator()
        menu.addAction("Modifier la liste", lambda: api.launch_tool("files"))

    api.add_menu("Fichier", build)
