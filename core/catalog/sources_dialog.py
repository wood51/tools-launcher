"""Fenêtres de gestion des sources du catalogue (liste, ajout, modification, test)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.catalog.index import read_index
from core.catalog.sources import (
    SOURCE_TYPES,
    encrypt_token,
    load_sources,
    new_source,
    remove_git_cache,
    save_sources,
    validate_source,
)

LOCATION_LABELS = {
    "folder": ("Dossier", "\\\\serveur\\partage\\catalogue"),
    "git": ("Adresse du dépôt", "https://github.com/propriétaire/nom.git"),
}


class SourceEditDialog(QDialog):
    def __init__(self, parent: QWidget, source: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Modifier la source" if source else "Nouvelle source")
        self.source = dict(source) if source else new_source()
        self.had_token = bool(self.source.get("token"))

        self.name = QLineEdit(self.source.get("name", ""))
        self.type = QComboBox()
        for key, label in SOURCE_TYPES.items():
            self.type.addItem(label, key)
        self.type.setCurrentIndex(max(0, self.type.findData(self.source.get("type", "folder"))))
        self.location = QLineEdit(self.source.get("location", ""))
        self.browse = QPushButton("Parcourir…")
        self.browse.clicked.connect(self.choose_folder)
        self.ref = QLineEdit(self.source.get("ref", ""))
        self.ref.setPlaceholderText("branche ou étiquette (défaut : celle du dépôt)")
        self.path = QLineEdit(self.source.get("path", ""))
        self.path.setPlaceholderText("sous-dossier contenant index.json (facultatif)")
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.Password)
        self.token.setPlaceholderText("jeton enregistré, laisser vide pour le conserver" if self.had_token else "facultatif pour un dépôt public")
        self.clear_token = QCheckBox("Supprimer le jeton enregistré")
        self.unsigned = QCheckBox("Accepter des extensions non signées (déconseillé)")
        self.unsigned.setChecked(self.source.get("unsigned_ok", False))
        self.enabled = QCheckBox("Source active")
        self.enabled.setChecked(self.source.get("enabled", True))

        location_row = QHBoxLayout()
        location_row.setContentsMargins(0, 0, 0, 0)
        location_row.addWidget(self.location, 1)
        location_row.addWidget(self.browse)
        self.location_box = QWidget()
        self.location_box.setLayout(location_row)
        self.location_label = QLabel()

        self.form = QFormLayout()
        self.form.addRow("Nom", self.name)
        self.form.addRow("Type", self.type)
        self.form.addRow(self.location_label, self.location_box)
        self.form.addRow("Branche", self.ref)
        self.form.addRow("Sous-dossier", self.path)
        self.form.addRow("Jeton", self.token)
        self.form.addRow("", self.clear_token)
        self.form.addRow("", self.unsigned)
        self.form.addRow("", self.enabled)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok = QPushButton("Enregistrer")
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept_if_valid)
        cancel = QPushButton("Annuler")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)

        layout = QVBoxLayout(self)
        layout.addLayout(self.form)
        layout.addLayout(buttons)
        self.type.currentIndexChanged.connect(self.update_fields)
        self.update_fields()
        self.setMinimumWidth(520)

    def update_fields(self) -> None:
        kind = self.type.currentData()
        label, example = LOCATION_LABELS[kind]
        self.location_label.setText(label)
        self.location.setPlaceholderText(example)
        self.browse.setVisible(kind == "folder")
        remote = kind != "folder"
        self.form.setRowVisible(self.ref, kind == "git")
        self.form.setRowVisible(self.path, kind == "git")
        self.form.setRowVisible(self.token, remote)
        self.form.setRowVisible(self.clear_token, remote and self.had_token)

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Dossier du catalogue (contenant index.json)")
        if folder:
            self.location.setText(folder)

    def accept_if_valid(self) -> None:
        kind = self.type.currentData()
        source = {
            **self.source,
            "name": self.name.text().strip(),
            "type": kind,
            "location": self.location.text().strip(),
            "enabled": self.enabled.isChecked(),
            "unsigned_ok": self.unsigned.isChecked(),
        }
        for key, field in (("ref", self.ref), ("path", self.path)):
            value = field.text().strip()
            if value and kind == "git":
                source[key] = value
            else:
                source.pop(key, None)
        if kind == "folder" or self.clear_token.isChecked():
            source.pop("token", None)
        text = self.token.text().strip()
        try:
            validate_source(source)
            if text and kind != "folder":
                source["token"] = encrypt_token(text)
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, "Source invalide", str(e))
            return
        self.source = source
        self.accept()


class SourcesDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sources du catalogue")
        self.sources = load_sources()
        self.changed = False

        hint = QLabel("Cochez les sources à utiliser. Une extension présente dans plusieurs sources vous laisse choisir laquelle installer.")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        self.list = QListWidget()
        self.list.itemChanged.connect(self.on_toggle)
        self.list.itemDoubleClicked.connect(lambda _item: self.edit())

        side = QVBoxLayout()
        for text, slot in (("Ajouter…", self.add), ("Modifier…", self.edit), ("Supprimer", self.remove), ("Tester", self.test)):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, s=slot: s())
            side.addWidget(button)
        side.addStretch(1)
        close = QPushButton("Fermer")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        side.addWidget(close)

        body = QHBoxLayout()
        body.addWidget(self.list, 1)
        body.addLayout(side)
        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addLayout(body)
        self.refresh()
        self.resize(640, 380)

    def refresh(self, select: int = 0) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for source in self.sources:
            item = QListWidgetItem(f"{source['name']}  ·  {SOURCE_TYPES[source['type']]}  ·  {source.get('location', '')}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if source.get("enabled", True) else Qt.Unchecked)
            self.list.addItem(item)
        self.list.blockSignals(False)
        if self.sources:
            self.list.setCurrentRow(min(select, len(self.sources) - 1))

    def save(self) -> None:
        save_sources(self.sources)
        self.changed = True

    def current(self) -> int:
        return self.list.currentRow()

    def on_toggle(self, item: QListWidgetItem) -> None:
        row = self.list.row(item)
        self.sources[row]["enabled"] = item.checkState() == Qt.Checked
        self.save()

    def add(self) -> None:
        dialog = SourceEditDialog(self)
        if dialog.exec():
            self.sources.append(dialog.source)
            self.save()
            self.refresh(len(self.sources) - 1)

    def edit(self) -> None:
        row = self.current()
        if row < 0:
            return
        dialog = SourceEditDialog(self, self.sources[row])
        if dialog.exec():
            self.sources[row] = dialog.source
            self.save()
            self.refresh(row)

    def remove(self) -> None:
        row = self.current()
        if row < 0:
            return
        name = self.sources[row]["name"]
        if QMessageBox.question(self, "Supprimer", f"Supprimer la source « {name} » ?\n(Les extensions déjà installées restent.)") == QMessageBox.Yes:
            remove_git_cache(self.sources[row]["id"])
            del self.sources[row]
            self.save()
            self.refresh(row)

    def test(self) -> None:
        row = self.current()
        if row < 0:
            return
        source = self.sources[row]
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            count = len(read_index(source))
            message = f"« {source['name']} » : {count} extension(s) lisible(s)."
            icon = QMessageBox.Information
        except (OSError, ValueError) as e:
            message = f"« {source['name']} » : {e}"
            icon = QMessageBox.Warning
        finally:
            QApplication.restoreOverrideCursor()
        QMessageBox(icon, "Test de la source", message, parent=self).exec()
