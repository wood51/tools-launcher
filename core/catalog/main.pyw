import sys
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QSizePolicy,
    QWidget,
)

from core.catalog.index import fetch_zip, is_newer, load_catalog
from core.catalog.sources import get_source, load_sources
from core.catalog.sources_dialog import SourcesDialog
from core.deps import install_deps
from core.installer import (
    InstallError,
    Prepared,
    backup_version,
    commit,
    discard,
    installed_version,
    prepare_folder,
    prepare_zip,
    restore_backup,
    uninstall,
    version_key,
)
from core.paths import EXTENSIONS_DIR
from core.registry import discover_extensions
from core.theme import apply_theme

BLOCK_LABELS = {"tool": "outil", "plugin": "plugin", "theme": "thème"}


def set_hover(widget: QWidget, hover: bool) -> None:
    widget.setProperty("hover", hover)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class ReadmeDialog(QDialog):
    def __init__(self, title: str, markdown: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        view = QTextBrowser()
        view.setMarkdown(markdown)
        QVBoxLayout(self).addWidget(view)
        self.resize(640, 480)


class CatalogWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Catalogue")
        self.setAcceptDrops(True)
        self.entries: dict[str, dict] = {}
        self.index_error = ""

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel("Catalogue")
        title.setObjectName("title")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.source_label = QLabel()
        self.source_label.setObjectName("muted")
        self.source_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # un long chemin n'élargit pas la fenêtre
        source_button = QPushButton("Source…")
        source_button.clicked.connect(self.choose_source)
        refresh_button = QPushButton("Actualiser")
        refresh_button.clicked.connect(self.reload)
        top.addWidget(self.source_label, 1)
        top.addWidget(source_button)
        top.addWidget(refresh_button)
        layout.addLayout(top)

        self.drop = QFrame()
        self.drop.setObjectName("drop")
        drop_layout = QVBoxLayout(self.drop)
        hint = QLabel("Glissez ici un .zip ou un dossier d'extension pour l'installer")
        hint.setAlignment(Qt.AlignCenter)
        hint.setObjectName("muted")
        drop_layout.addWidget(hint)
        self.drop.setMinimumHeight(70)
        layout.addWidget(self.drop)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher…")
        self.search.textChanged.connect(self.reload_cards)
        layout.addWidget(self.search)

        self.cards_widget = QWidget()
        self.cards_widget.setObjectName("root")
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.cards_widget)
        layout.addWidget(scroll, 1)

        self.resize(720, 640)
        self.reload()

    #### Source et liste ####

    def choose_source(self) -> None:
        dialog = SourcesDialog(self)
        dialog.exec()
        if dialog.changed:
            self.reload()

    def reload(self) -> None:
        sources = [s for s in load_sources() if s.get("enabled", True)]
        self.entries = {}
        if not sources:
            self.source_label.setText("Aucune source active : seuls les extensions installées et le glisser-déposer sont disponibles.")
        else:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.entries, errors = load_catalog()
            finally:
                QApplication.restoreOverrideCursor()
            text = f"{len(sources)} source(s) active(s)"
            if errors:
                text += f" · illisible : {' ; '.join(errors)}"
            self.source_label.setText(text)
            self.source_label.setToolTip(text)
        self.reload_cards()

    def reload_cards(self) -> None:
        while (item := self.cards_layout.takeAt(0)) is not None:
            if item.widget():
                item.widget().deleteLater()
        local = {e["id"]: e for e in discover_extensions()}
        needle = self.search.text().strip().lower()
        ids = sorted(set(local) | set(self.entries), key=lambda i: (local.get(i) or self.entries[i][0])["name"].lower())
        for extension_id in ids:
            entries = self.entries.get(extension_id, [])
            manifest = local.get(extension_id)
            name = (manifest or entries[0])["name"]
            description = (manifest or {}).get("tooltip") or (entries[0].get("tooltip", "") if entries else "")
            if needle and needle not in f"{name} {description} {extension_id}".lower():
                continue
            self.cards_layout.addWidget(self.make_card(extension_id, name, description, manifest, entries))
        self.cards_layout.addStretch(1)

    #### Cartes ####

    def make_card(self, extension_id: str, name: str, description: str, manifest: dict | None, entries: list[dict]) -> QFrame:
        entry = entries[0] if entries else None  # la plus récente
        installed = manifest["version"] if manifest else None
        card = QFrame()
        card.setObjectName("card")
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 12, 16, 12)

        text = QVBoxLayout()
        author = (manifest or {}).get("author") or (entry or {}).get("author")
        by = f"  <span style='color:gray'>par {escape(author)}</span>" if author else ""
        title = QLabel(f"<b>{escape(name)}</b>  <span style='color:gray'>{installed or entry['version']}</span>{by}")
        title.setTextFormat(Qt.RichText)
        text.addWidget(title)
        if description:
            label = QLabel(description)
            label.setWordWrap(True)
            label.setObjectName("muted")
            text.addWidget(label)
        if entry and entry.get("notes"):
            notes = QLabel(f"Nouveautés : {entry['notes']}")
            notes.setWordWrap(True)
            notes.setObjectName("muted")
            text.addWidget(notes)
        text.addWidget(QLabel(self.state_text(installed, entry)))
        if len({e["source_id"] for e in entries}) > 1:
            warning = QLabel("Présente dans plusieurs sources : choisissez celle à utiliser.")
            warning.setObjectName("muted")
            text.addWidget(warning)
            top = entries[0]
            if any(e["version"] == top["version"] and e["sha256"].lower() != top["sha256"].lower() for e in entries[1:]):
                text.addWidget(QLabel("⚠ Même version mais empreintes différentes selon les sources."))
        row.addLayout(text, 1)

        buttons = QVBoxLayout()
        if entry and is_newer(entry, installed):
            combo = None
            if len(entries) > 1:
                combo = QComboBox()
                for e in entries:
                    combo.addItem(f"{e['source_name']} · {e['version']}", e)
                buttons.addWidget(combo)
            button = QPushButton("Installer" if installed is None else "Mettre à jour")
            button.setObjectName("primary")
            button.clicked.connect(
                lambda checked=False, e=entry, c=combo: self.install_from_catalog(c.currentData() if c else e)
            )
            buttons.addWidget(button)
        if installed is not None:
            readme = EXTENSIONS_DIR / extension_id / "README.md"
            if readme.is_file():
                button = QPushButton("Lisez-moi")
                button.setObjectName("link")
                button.clicked.connect(lambda checked=False, p=readme, n=name: self.show_readme(n, p))
                buttons.addWidget(button)
            previous = backup_version(extension_id)
            if previous:
                button = QPushButton(f"Revenir à {previous}")
                button.clicked.connect(lambda checked=False, i=extension_id: self.restore(i))
                buttons.addWidget(button)
            button = QPushButton("Désinstaller")
            button.clicked.connect(lambda checked=False, i=extension_id, n=name: self.remove(i, n))
            buttons.addWidget(button)
        row.addLayout(buttons)
        return card

    @staticmethod
    def state_text(installed: str | None, entry: dict | None) -> str:
        if installed is None:
            return "Non installée"
        if entry and is_newer(entry, installed):
            return f"Installée ({installed}) · mise à jour disponible : {entry['version']}"
        return f"Installée ({installed})" + ("" if entry else " · hors catalogue")

    def show_readme(self, name: str, path: Path) -> None:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as e:
            text = f"Lecture impossible : {e}"
        ReadmeDialog(f"{name} · Lisez-moi", text, self).exec()

    #### Actions ####

    def install_from_catalog(self, entry: dict) -> None:
        local = None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            local = fetch_zip(entry)
            source = get_source(entry["source_id"])
            prepared = prepare_zip(local, entry["sha256"], require_signature=not (source or {}).get("unsigned_ok"))
            # l'index n'est pas signé : le zip doit être bien celui annoncé, et plus récent que l'installé
            if prepared.id != entry["id"] or prepared.version != entry["version"]:
                discard(prepared)
                raise InstallError(f"le zip contient {prepared.id} {prepared.version}, pas {entry['id']} {entry['version']} : refusé")
            if prepared.previous_version and version_key(prepared.version) <= version_key(prepared.previous_version):
                discard(prepared)
                raise InstallError("version non plus récente que celle installée : refusée")
        except (OSError, ValueError, InstallError) as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Installation impossible", str(e))
            return
        finally:
            if local is not None:
                local.unlink(missing_ok=True)
        QApplication.restoreOverrideCursor()
        self.confirm_and_commit(prepared)

    def install_dropped(self, path: Path) -> None:
        try:
            prepared = prepare_folder(path) if path.is_dir() else prepare_zip(path)
        except (OSError, InstallError) as e:
            QMessageBox.warning(self, "Installation impossible", str(e))
            return
        self.confirm_and_commit(prepared)

    def confirm_and_commit(self, prepared: Prepared) -> None:
        kinds = ", ".join(BLOCK_LABELS[b] for b in prepared.blocks)
        action = "Mettre à jour" if prepared.previous_version else "Installer"
        lines = [f"{action} « {prepared.name} » {prepared.version} ({kinds}) ?"]
        if prepared.previous_version:
            lines.append(f"Version actuelle : {prepared.previous_version}. Vos données sont conservées.")
        if prepared.has_requirements:
            lines.append("Cette extension demande des paquets Python : ils seront téléchargés et installés.")
        lines.append(f"Signé par {prepared.signer}." if prepared.signer else "Provenance NON vérifiée (aucune signature).")
        lines.append("\nCe code s'exécute avec vos droits : installez seulement ce que vous avez relu ou reçu d'une source sûre.")
        answer = QMessageBox.question(self, action, "\n".join(lines))
        if answer != QMessageBox.Yes:
            discard(prepared)
            return
        try:
            commit(prepared)
        except InstallError as e:
            QMessageBox.warning(self, "Installation impossible", str(e))
            self.reload()
            return
        notes = [f"« {prepared.name} » {prepared.version} est installée."]
        if prepared.has_requirements:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                failed = install_deps()
            finally:
                QApplication.restoreOverrideCursor()
            if failed is None:
                notes.append("Installation des paquets du noyau échouée : relancez bootstrap.pyw.")
            elif prepared.id in failed:
                notes.append("Ses paquets Python n'ont pas pu être installés (réseau, proxy ?) : elle sera ignorée par le lanceur.")
        if "plugin" in prepared.blocks:
            notes.append("Plugin : quittez puis relancez le lanceur pour l'activer.")
        QMessageBox.information(self, "Catalogue", "\n".join(notes))
        self.reload()

    def remove(self, extension_id: str, name: str) -> None:
        box = QMessageBox(QMessageBox.Question, "Désinstaller", f"Désinstaller « {name} » ?\nGarder ses données ?", parent=self)
        keep = box.addButton("Garder les données", QMessageBox.AcceptRole)
        drop = box.addButton("Tout supprimer", QMessageBox.DestructiveRole)
        box.addButton("Annuler", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() not in (keep, drop):
            return
        try:
            uninstall(extension_id, keep_data=box.clickedButton() is keep)
        except InstallError as e:
            QMessageBox.warning(self, "Désinstallation impossible", str(e))
        self.reload()

    def restore(self, extension_id: str) -> None:
        try:
            restore_backup(extension_id)
        except InstallError as e:
            QMessageBox.warning(self, "Retour arrière impossible", str(e))
        self.reload()

    #### Glisser-déposer ####

    @staticmethod
    def dropped_path(event) -> Path | None:
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.is_dir() or path.suffix.lower() == ".zip":
                    return path
        return None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self.dropped_path(event):
            set_hover(self.drop, True)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        set_hover(self.drop, False)

    def dropEvent(self, event: QDropEvent) -> None:
        set_hover(self.drop, False)
        path = self.dropped_path(event)
        if path:
            event.acceptProposedAction()
            self.install_dropped(path)


app = QApplication(sys.argv)
apply_theme(app)
window = CatalogWindow()
window.show()
sys.exit(app.exec())
