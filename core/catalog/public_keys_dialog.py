"""Approbation explicite d'une clé publique sur un poste destinataire."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from core.signing import fingerprint, import_public_key, read_public_key, set_key_trust, trusted_keys


class PublicKeyImportDialog(QDialog):
    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("root")
        self.setWindowTitle("Approuver une clé publique")
        self.resize(640, 320)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(entry["name"])
        key_id = QLabel(entry["id"])
        key_id.setTextFormat(Qt.PlainText)
        self.fingerprint = QLabel(fingerprint(entry["public"]))
        self.fingerprint.setWordWrap(True)
        self.fingerprint.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.allowed_ids = QLineEdit(", ".join(entry.get("ids", [])))
        self.allowed_ids.setPlaceholderText("Facultatif : programmes, publisher… Vide = tous les outils")
        form.addRow("Identifiant", key_id)
        form.addRow("Signataire", self.name)
        form.addRow("Empreinte SHA-256", self.fingerprint)
        form.addRow("Outils autorisés", self.allowed_ids)
        layout.addLayout(form)
        hint = QLabel("Comparez cette empreinte avec celle communiquée par l’auteur par un autre canal.\n"
                      "Approuver cette clé autorise l’installation des outils qu’elle signe ; leur code s’exécute avec vos droits.\n"
                      "Sans restriction d’outils, tous les outils de ce signataire sont acceptés.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.error = QLabel()
        self.error.setTextFormat(Qt.PlainText)
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Annuler")
        cancel.clicked.connect(self.reject)
        approve = QPushButton("Approuver cette clé")
        approve.setObjectName("primary")
        approve.setAutoDefault(False)
        approve.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addWidget(approve)
        layout.addLayout(actions)

    def accept(self):
        entry = {key: value for key, value in self.entry.items() if key != "ids"}
        entry["name"] = self.name.text().strip()
        ids = [value.strip() for value in self.allowed_ids.text().split(",") if value.strip()]
        if ids:
            entry["ids"] = ids
        try:
            import_public_key(entry)
        except (OSError, ValueError) as error:
            self.error.setText(str(error))
            return
        super().accept()


class PublicKeysDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("root")
        self.setWindowTitle("Clés de confiance")
        self.resize(760, 390)
        layout = QVBoxLayout(self)
        hint = QLabel("Ces clés publiques permettent de reconnaître les auteurs des extensions.\n"
                      "Aucune clé privée ni aucun mot de passe de publication n’est nécessaire sur ce poste.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Signataire", "Outils autorisés", "Empreinte SHA-256"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemSelectionChanged.connect(self.update_actions)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        layout.addWidget(self.table, 1)
        self.status = QLabel()
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.import_button = QPushButton("Importer une clé…")
        self.import_button.setObjectName("primary")
        self.import_button.clicked.connect(self.choose_file)
        actions.addWidget(self.import_button)
        self.trust_button = QPushButton("Retirer la confiance")
        self.trust_button.setObjectName("danger")
        self.trust_button.clicked.connect(self.toggle_trust)
        actions.addWidget(self.trust_button)
        actions.addStretch()
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self):
        entries = sorted(trusted_keys().values(), key=lambda key: str(key.get("name", key["id"])).casefold())
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            try:
                digest = fingerprint(entry["public"])
            except (ValueError, TypeError):
                digest = "Clé invalide"
            scope = ("Confiance retirée" if entry.get("disabled_locally") else "Révoquée") if entry.get("revoked") is True else ", ".join(entry.get("ids", [])) or "Tous les outils"
            for column, text in enumerate((f'{entry.get("name", entry["id"])} ({entry["id"]})', scope, digest)):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                item.setData(Qt.UserRole, entry["id"])
                self.table.setItem(row, column, item)
        self.update_actions()

    def selected_key(self):
        rows = self.table.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        return trusted_keys().get(self.table.item(rows[0].row(), 0).data(Qt.UserRole))

    def update_actions(self):
        key = self.selected_key()
        self.trust_button.setEnabled(bool(key) and (key.get("revoked") is not True or bool(key.get("disabled_locally"))))
        self.trust_button.setText("Rétablir la confiance" if key and key.get("disabled_locally") else "Retirer la confiance")

    def toggle_trust(self):
        key = self.selected_key()
        if not key:
            return
        restore = bool(key.get("disabled_locally"))
        title = "Rétablir la confiance" if restore else "Retirer la confiance"
        message = (f'Autoriser à nouveau les outils signés par « {key.get("name", key["id"])} » ?' if restore else
                   f'Refuser les prochaines installations et mises à jour signées par « {key.get("name", key["id"])} » ?\nLes outils déjà installés restent en place.')
        if QMessageBox.question(self, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            set_key_trust(key["id"], restore)
        except (OSError, ValueError) as error:
            self.status.setText(str(error))
            return
        self.refresh()
        self.status.setText("Confiance rétablie sur ce poste." if restore else "Confiance retirée sur ce poste. Les futures installations et mises à jour de ce signataire seront refusées.")

    def choose_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Importer une clé publique", "", "Clé publique (*.pub.json);;JSON (*.json)")
        if not filename:
            return
        from pathlib import Path
        try:
            entry = read_public_key(Path(filename))
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Clé publique", str(error))
            return
        dialog = PublicKeyImportDialog(entry, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            self.status.setText("Clé publique approuvée sur ce poste. Vous pouvez maintenant installer les outils autorisés qu’elle signe.")
