import os
import sys
from pathlib import Path

from PySide6.QtCore import QFileInfo, Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from extensions.files.files import add_file, load_files, save_files
from core.theme import apply_theme

MISSING_COLOR = QColor("#e5484d")


class FilesEditor(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Éditeur de fichiers")
        self.setAcceptDrops(True)  # on peut déposer n'importe où dans la fenêtre
        self.icons = QFileIconProvider()
        self.files = load_files()

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        self.drop = QFrame()
        self.drop.setObjectName("drop")
        self.drop.setMinimumHeight(90)
        drop_layout = QVBoxLayout(self.drop)
        hint = QLabel("Glisse des fichiers ici pour les ajouter au menu Fichier")
        hint.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(hint)
        layout.addWidget(self.drop)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Nom (modifiable)", "Fichier", "Application"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.itemSelectionChanged.connect(self.update_buttons)
        QShortcut(QKeySequence(Qt.Key_Delete), self.table).activated.connect(self.remove_selected)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.add_button = QPushButton("Ajouter…")
        self.add_button.setObjectName("primary")
        self.app_button = QPushButton("Application…")
        self.default_button = QPushButton("Application par défaut")
        self.remove_button = QPushButton("Supprimer")
        self.add_button.clicked.connect(self.add_from_dialog)
        self.app_button.clicked.connect(self.choose_app)
        self.default_button.clicked.connect(self.clear_app)
        self.remove_button.clicked.connect(self.remove_selected)
        for button in (self.add_button, self.app_button, self.default_button, self.remove_button):
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.status = QLabel("")
        layout.addWidget(self.status)

        self.resize(780, 480)
        self.refresh()

    #### Affichage ####

    def refresh(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.files))
        for row, entry in enumerate(self.files):
            icon = self.icons.icon(QFileInfo(entry.get("app") or entry["path"]))
            name = QTableWidgetItem(icon, entry["name"])
            path = QTableWidgetItem(entry["path"])
            path.setFlags(path.flags() & ~Qt.ItemIsEditable)
            if not Path(entry["path"]).exists():
                path.setForeground(MISSING_COLOR)
                path.setToolTip("Fichier introuvable")
            app = QTableWidgetItem(Path(entry["app"]).stem if entry.get("app") else "Par défaut")
            app.setFlags(app.flags() & ~Qt.ItemIsEditable)
            app.setToolTip(entry.get("app", "Application par défaut de Windows"))
            for column, item in enumerate((name, path, app)):
                self.table.setItem(row, column, item)
        self.table.blockSignals(False)
        self.update_buttons()

    def update_buttons(self) -> None:
        has_selection = bool(self.selected_rows())
        for button in (self.app_button, self.default_button, self.remove_button):
            button.setEnabled(has_selection)

    def selected_rows(self) -> list[int]:
        return sorted({index.row() for index in self.table.selectedIndexes()})

    def set_drop_hover(self, hover: bool) -> None:
        self.drop.setProperty("hover", hover)
        self.drop.style().unpolish(self.drop)
        self.drop.style().polish(self.drop)

    #### Actions ####

    def add_paths(self, paths: list[str]) -> None:
        added = skipped = 0
        for path in paths:
            if os.path.isfile(path):
                add_file(os.path.normpath(path))
                added += 1
            else:
                skipped += 1  # dossier ou chemin inexistant
        self.files = load_files()
        self.refresh()
        message = f"{added} fichier(s) traité(s)"
        if skipped:
            message += f", {skipped} ignoré(s) (seuls les fichiers sont acceptés)"
        self.status.setText(message)

    def add_from_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Ajouter des fichiers")
        if paths:
            self.add_paths(paths)

    def choose_app(self) -> None:
        rows = self.selected_rows()
        app, _ = QFileDialog.getOpenFileName(
            self, "Choisir l'application", "C:/Program Files", "Programmes (*.exe)"
        )
        if not rows or not app:
            return
        for row in rows:
            self.files[row]["app"] = os.path.normpath(app)
        self.save_and_refresh()

    def clear_app(self) -> None:
        for row in self.selected_rows():
            self.files[row].pop("app", None)
        self.save_and_refresh()

    def remove_selected(self) -> None:
        rows = set(self.selected_rows())
        if rows:
            self.files = [entry for row, entry in enumerate(self.files) if row not in rows]
            self.save_and_refresh()

    def on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        entry = self.files[item.row()]
        entry["name"] = item.text().strip() or Path(entry["path"]).stem
        self.save_and_refresh()

    def save_and_refresh(self) -> None:
        save_files(self.files)
        self.refresh()

    #### Glisser-déposer ####

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.set_drop_hover(True)

    def dragLeaveEvent(self, event) -> None:
        self.set_drop_hover(False)

    def dropEvent(self, event) -> None:
        self.set_drop_hover(False)
        self.add_paths([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])


app = QApplication(sys.argv)
apply_theme(app)
window = FilesEditor()
window.show()
sys.exit(app.exec())
