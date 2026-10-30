import os
import platform
import subprocess
import sys

import PySide6
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core import startup
from core.api import send_message
from core.config import get_section, set_section
from core.paths import DATA_DIR, LOG_FILE, launcher_version
from core.plugin_loader import discover_plugins, load_disabled, save_disabled
from core.theme import apply_theme

NOTIFY_MODES = (
    ("toast", "Notification du lanceur", "Petite fenêtre en bas à droite, aux couleurs du thème."),
    ("windows", "Notification Windows", "Centre de notifications de Windows, au nom de l'outil. Peut être bloquée par l'entreprise."),
)


def muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(True)
    return label


class Section(QFrame):
    """Une carte : titre, description, puis le contenu ajouté dans `body`."""

    def __init__(self, title: str, description: str = "") -> None:
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        heading = QLabel(title)
        heading.setObjectName("section")
        layout.addWidget(heading)
        if description:
            layout.addWidget(muted(description))
        self.body = QVBoxLayout()
        self.body.setSpacing(4)
        layout.addLayout(self.body)


class SettingsWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Paramètres")
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)

        content = QWidget()
        content.setObjectName("root")
        self.page = QVBoxLayout(content)
        self.page.setContentsMargins(20, 16, 20, 16)
        self.page.setSpacing(10)
        title = QLabel("Paramètres")
        title.setObjectName("title")
        self.page.addWidget(title)

        self.build_plugins()
        self.build_notifications()
        self.build_general()
        self.page.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.resize(620, 100)
        self.fit_height()

    def fit_height(self) -> None:
        """La fenêtre épouse son contenu ; l'ascenseur ne sert que si l'écran est trop petit."""
        available = QGuiApplication.primaryScreen().availableGeometry().height()
        height = self.page.totalHeightForWidth(self.width() - 4)  # les textes qui passent à la ligne comptent
        self.resize(self.width(), min(height + 4, int(available * 0.92)))

    #### Plugins ####

    def build_plugins(self) -> None:
        section = Section("Plugins", "Un changement s'applique au redémarrage du lanceur.")
        disabled = load_disabled()
        plugins = discover_plugins()
        if not plugins:
            section.body.addWidget(muted("Aucun plugin installé."))
        else:
            # liste compacte + détail du plugin choisi : reste lisible avec beaucoup de plugins
            self.plugin_filter = QLineEdit()
            self.plugin_filter.setPlaceholderText("Filtrer les plugins…")
            self.plugin_filter.setClearButtonEnabled(True)
            self.plugin_filter.textChanged.connect(self.filter_plugins)
            section.body.addWidget(self.plugin_filter)

            self.plugin_list = QListWidget()
            for plugin in sorted(plugins, key=lambda p: p["name"].lower()):
                item = QListWidgetItem(plugin["name"])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked if plugin["id"] in disabled else Qt.Checked)
                item.setData(Qt.UserRole, plugin)
                self.plugin_list.addItem(item)
            row = max(self.plugin_list.sizeHintForRow(0), 30)
            self.plugin_list.setFixedHeight(min(200, self.plugin_list.count() * row + 14))  # épouse peu de plugins, défile au-delà
            self.plugin_list.itemChanged.connect(self.plugin_item_changed)
            self.plugin_list.currentItemChanged.connect(self.show_plugin_detail)
            section.body.addWidget(self.plugin_list)

            self.plugin_detail = muted("")
            self.plugin_detail.setMinimumHeight(36)
            section.body.addWidget(self.plugin_detail)
            self.plugin_list.setCurrentRow(0)

        self.restart_bar = QWidget()  # n'apparaît qu'après un changement
        bar = QHBoxLayout(self.restart_bar)
        bar.setContentsMargins(0, 6, 0, 0)
        self.restart_label = muted("Modifié : redémarrez le lanceur pour appliquer.")
        restart = QPushButton("Redémarrer le lanceur")
        restart.setObjectName("primary")
        restart.clicked.connect(self.restart_launcher)
        bar.addWidget(self.restart_label, 1)
        bar.addWidget(restart)
        self.restart_bar.hide()
        section.body.addWidget(self.restart_bar)
        self.page.addWidget(section)

    def filter_plugins(self, text: str) -> None:
        needle = text.strip().lower()
        for row in range(self.plugin_list.count()):
            item = self.plugin_list.item(row)
            plugin = item.data(Qt.UserRole)
            item.setHidden(bool(needle) and needle not in f"{plugin['name']} {plugin['tooltip']} {plugin['id']}".lower())

    def show_plugin_detail(self, item: QListWidgetItem | None) -> None:
        if item is None:
            self.plugin_detail.setText("")
            return
        plugin = item.data(Qt.UserRole)
        text = f"{plugin['name']} · version {plugin['version']} · {plugin['id']}"
        self.plugin_detail.setText(f"{text}\n{plugin['tooltip']}" if plugin["tooltip"] else text)

    def plugin_item_changed(self, item: QListWidgetItem) -> None:
        self.toggle_plugin(item.data(Qt.UserRole)["id"], item.checkState() == Qt.Checked)

    def toggle_plugin(self, plugin_id: str, enabled: bool) -> None:
        disabled = load_disabled()
        if enabled:
            disabled.discard(plugin_id)
        else:
            disabled.add(plugin_id)
        save_disabled(disabled)
        self.restart_bar.show()
        self.fit_height()

    def restart_launcher(self) -> None:
        if send_message({"cmd": "restart", "ext": "settings"}):
            self.restart_label.setText("Redémarrage du lanceur…")
            QApplication.instance().quit()  # la fenêtre se ferme avec le redémarrage
        else:
            QMessageBox.information(self, "Paramètres", "Le lanceur ne tourne pas : lancez bootstrap.pyw pour le démarrer.")

    #### Notifications ####

    def build_notifications(self) -> None:
        section = Section("Notifications")
        settings = get_section("notifications")
        modes = [mode for mode, _, _ in NOTIFY_MODES]
        current = settings.get("mode") if settings.get("mode") in modes else "toast"

        self.radios: dict[str, QRadioButton] = {}
        for mode, label, description in NOTIFY_MODES:
            radio = QRadioButton(label)
            radio.setChecked(mode == current)
            radio.toggled.connect(lambda checked, m=mode: checked and self.save_notifications(mode=m))
            note = muted(description)
            note.setContentsMargins(26, 0, 0, 2)
            section.body.addWidget(radio)
            section.body.addWidget(note)
            self.radios[mode] = radio

        self.sound = QCheckBox("Jouer un son")
        self.sound.setChecked(settings.get("sound") is True)
        self.sound.toggled.connect(lambda checked: self.save_notifications(sound=checked))
        row = QHBoxLayout()
        row.addWidget(self.sound, 1)
        test = QPushButton("Envoyer un test")
        test.clicked.connect(self.send_test)
        row.addWidget(test)
        section.body.addLayout(row)
        self.test_status = muted("")
        self.test_status.hide()  # n'apparaît qu'en cas de problème
        section.body.addWidget(self.test_status)
        self.page.addWidget(section)

    def save_notifications(self, **values) -> None:
        set_section("notifications", {**get_section("notifications"), **values})

    def send_test(self) -> None:
        sent = send_message(
            {"cmd": "notify", "ext": "settings", "title": "Notification de test", "message": "Ceci est un essai.", "level": "info"}
        )
        self.test_status.setText("Le lanceur ne tourne pas : rien n'a été envoyé.")
        self.test_status.setVisible(not sent)

    #### Général ####

    def build_general(self) -> None:
        section = Section("Général")
        self.startup = QCheckBox("Démarrer avec Windows")
        self.startup.setChecked(startup.is_enabled())
        self.startup.toggled.connect(self.toggle_startup)
        section.body.addWidget(self.startup)

        row = QHBoxLayout()
        row.addStretch(1)
        for text, slot in (("Ouvrir le journal", self.open_log), ("Dossier des données", self.open_data_dir)):
            button = QPushButton(text)
            button.clicked.connect(slot)
            row.addWidget(button)
        section.body.addLayout(row)
        section.body.addWidget(
            muted(f"Tools Launcher {launcher_version()} · Python {platform.python_version()} · PySide6 {PySide6.__version__}")
        )
        self.page.addWidget(section)

    def toggle_startup(self, enabled: bool) -> None:
        try:
            startup.enable() if enabled else startup.disable()
        except (OSError, subprocess.SubprocessError) as e:
            QMessageBox.warning(self, "Démarrage avec Windows", f"Impossible de modifier le démarrage automatique :\n{e}")
            self.startup.blockSignals(True)  # remet la case dans l'état réel
            self.startup.setChecked(startup.is_enabled())
            self.startup.blockSignals(False)

    def open_log(self) -> None:
        try:
            LOG_FILE.parent.mkdir(exist_ok=True)
            LOG_FILE.touch()  # un journal encore vide s'ouvre aussi
            os.startfile(LOG_FILE)
        except OSError as e:
            QMessageBox.warning(self, "Journal", f"Impossible d'ouvrir le journal : {e}")

    def open_data_dir(self) -> None:
        try:
            DATA_DIR.mkdir(exist_ok=True)
            os.startfile(DATA_DIR)
        except OSError as e:
            QMessageBox.warning(self, "Données", f"Impossible d'ouvrir le dossier : {e}")


app = QApplication(sys.argv)
apply_theme(app)
window = SettingsWindow()
window.show()
sys.exit(app.exec())
