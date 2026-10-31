import os
import platform
import subprocess
import sys

import PySide6
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
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
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core import shortcuts, startup, tools_menu
from core.api import send_message
from core.config import get_section, set_section
from core.paths import DATA_DIR, ICONS_DIR, LOG_FILE, launcher_version
from core.plugin_loader import discover_plugins, load_disabled, save_disabled
from core.registry import discover_tools
from core.theme import apply_theme

TOOL_ROW_HEIGHT = 56

NOTIFY_MODES = (
    ("toast", "Notification du lanceur", "Petite fenêtre en bas à droite, aux couleurs du thème."),
    ("windows", "Notification Windows", "Centre de notifications de Windows, au nom de l'outil. Peut être bloquée par l'entreprise."),
)


class ElidedLabel(QLabel):
    """Texte sur une ligne, terminé par « … » quand la place manque (l'infobulle donne le texte complet)."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self._full = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # ne force jamais la largeur de la liste
        self.setToolTip(text)
        self.setText(self.fontMetrics().elidedText(text, Qt.ElideRight, 400))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.setText(self.fontMetrics().elidedText(self._full, Qt.ElideRight, max(self.width(), 20)))


def group_title(text: str) -> QLabel:
    """Petit titre de groupe à l'intérieur d'un onglet."""
    label = QLabel(text)
    label.setObjectName("rowtitle")
    return label


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
        self.heading = QLabel(title)
        self.heading.setObjectName("section")
        layout.addWidget(self.heading)
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
        outer.setContentsMargins(16, 14, 16, 16)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("settingsTabs")
        self.tab_pages: list[QWidget] = []
        outer.addWidget(self.tabs)
        self.tabs.currentChanged.connect(lambda _index: QTimer.singleShot(0, self.relayout_tool_list))

        self.build_general()
        self.build_tools()
        self.build_plugins()
        self.build_notifications()
        self.resize(660, 100)
        self.fit_size()

    def relayout_tool_list(self) -> None:
        """Les widgets des lignes d'outils gardent une largeur périmée tant que la liste n'est pas remise en page."""
        if hasattr(self, "tool_list"):
            self.tool_list.doItemsLayout()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.relayout_tool_list)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self.relayout_tool_list)

    def add_tab(self, label: str, section: "Section") -> None:
        """Un onglet par sujet : la carte perd son cadre et son titre (l'onglet les remplace)."""
        section.setObjectName("page")
        section.heading.hide()
        section.layout().setContentsMargins(0, 0, 0, 0)
        page = QWidget()
        page.setObjectName("root")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.addWidget(section)
        layout.addStretch(1)
        scroll = QScrollArea()  # filet de sécurité : l'ascenseur n'apparaît que si l'écran est trop petit
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        self.tabs.addTab(scroll, label)
        self.tab_pages.append(page)

    def fit_size(self) -> None:
        """La fenêtre épouse l'onglet le plus haut (sans ascenseur) ; plafonnée à la hauteur de l'écran."""
        width = 660
        available = QGuiApplication.primaryScreen().availableGeometry().height()
        tallest = max(page.layout().totalHeightForWidth(width - 32 - 4) for page in self.tab_pages)
        height = tallest + self.tabs.tabBar().sizeHint().height() + 14 + 16 + 8
        self.resize(width, min(height, int(available * 0.92)))

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
        self.add_tab("Plugins", section)

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
        self.fit_size()

    def restart_launcher(self) -> None:
        if send_message({"cmd": "restart", "ext": "settings"}):
            self.restart_label.setText("Redémarrage du lanceur…")
            QApplication.instance().quit()  # la fenêtre se ferme avec le redémarrage
        else:
            QMessageBox.information(self, "Paramètres", "Le lanceur ne tourne pas : lancez bootstrap.pyw pour le démarrer.")

    #### Outils ####

    def build_tools(self) -> None:
        section = Section("Outils", "★ met un outil en favori, en haut du menu de l'icône. S'applique à la prochaine ouverture du menu.")
        self.tools = sorted(discover_tools(), key=lambda t: t["name"].lower())
        self.tool_settings = tools_menu.load_settings()
        self.favorite_boxes: dict[str, QToolButton] = {}
        self.category_boxes: dict[str, QComboBox] = {}
        self.tool_rows: dict[str, QListWidgetItem] = {}
        if not self.tools:
            section.body.addWidget(muted("Aucun outil installé."))
            self.add_tab("Outils", section)
            return
        self.tool_filter = QLineEdit()
        self.tool_filter.setPlaceholderText("Filtrer les outils…")
        self.tool_filter.setClearButtonEnabled(True)
        self.tool_filter.textChanged.connect(self.filter_tools)
        section.body.addWidget(self.tool_filter)

        self.tool_list = QListWidget()
        self.tool_list.setSelectionMode(QListWidget.NoSelection)
        self.tool_list.setFocusPolicy(Qt.NoFocus)
        self.tool_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        categories = tools_menu.known_categories(self.tools, self.tool_settings)
        for tool in self.tools:
            item = QListWidgetItem()
            row = self.make_tool_row(tool, categories)
            row.setMinimumHeight(TOOL_ROW_HEIGHT)  # le sizeHint d'un widget pas encore stylé est trop petit
            item.setSizeHint(QSize(0, TOOL_ROW_HEIGHT))  # largeur : celle de la liste
            self.tool_list.addItem(item)
            self.tool_list.setItemWidget(item, row)
            self.tool_rows[tool["id"]] = item
        self.tool_list.setFixedHeight(min(6, len(self.tools)) * TOOL_ROW_HEIGHT + 14)  # épouse peu d'outils, défile au-delà
        section.body.addWidget(self.tool_list)
        self.tool_empty = muted("Aucun outil ne correspond.")
        self.tool_empty.setVisible(False)
        section.body.addWidget(self.tool_empty)

        self.group_box = QCheckBox("Regrouper les outils par catégorie (sous-menus)")
        self.group_box.setChecked(self.tool_settings["group"])
        self.group_box.toggled.connect(self.save_tool_settings)
        section.body.addWidget(self.group_box)
        self.add_tab("Outils", section)

    def make_tool_row(self, tool: dict, categories: list[str]) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 6, 6, 6)
        layout.setSpacing(12)

        star = QToolButton()
        star.setObjectName("star")
        star.setCheckable(True)
        star.setCursor(Qt.PointingHandCursor)
        star.setChecked(tool["id"] in self.tool_settings["favorites"])
        star.toggled.connect(lambda checked, b=star: self.star_toggled(b, checked))
        self.star_toggled(star, star.isChecked(), save=False)
        layout.addWidget(star)

        icon = QLabel()
        icon_file = tool["folder"] / tool["icon"] if tool.get("icon") else None
        qicon = QIcon(str(icon_file)) if icon_file and icon_file.is_file() else QIcon(str(ICONS_DIR / "tool.svg"))
        icon.setPixmap(qicon.pixmap(24, 24))
        icon.setFixedSize(24, 24)
        layout.addWidget(icon)

        text = QVBoxLayout()
        text.setSpacing(3)
        name = QLabel(tool["name"])
        name.setObjectName("rowtitle")
        text.addWidget(name)
        if tool.get("tooltip"):
            hint = ElidedLabel(tool["tooltip"])
            hint.setObjectName("muted")
            text.addWidget(hint)
        layout.addLayout(text, 1)

        combo = QComboBox()
        combo.setEditable(True)
        combo.setFixedWidth(160)
        combo.addItem("")
        combo.addItems(categories)
        combo.setCurrentText(tools_menu.effective_category(tool, self.tool_settings))
        combo.lineEdit().setPlaceholderText("Catégorie")
        combo.setToolTip("Catégorie dans le menu Outils (tapez un nom pour en créer une)")
        combo.activated.connect(self.save_tool_settings)
        combo.lineEdit().editingFinished.connect(self.save_tool_settings)
        layout.addWidget(combo)
        self.favorite_boxes[tool["id"]] = star
        self.category_boxes[tool["id"]] = combo
        return row

    def star_toggled(self, star: QToolButton, checked: bool, save: bool = True) -> None:
        star.setText("★" if checked else "☆")
        star.setToolTip("Retirer des favoris" if checked else "Ajouter aux favoris")
        if save:
            self.save_tool_settings()

    def filter_tools(self, text: str) -> None:
        needle = text.strip().lower()
        for tool in self.tools:
            haystack = f"{tool['name']} {tool.get('tooltip', '')} {tools_menu.effective_category(tool, self.tool_settings)}".lower()
            self.tool_rows[tool["id"]].setHidden(bool(needle) and needle not in haystack)
        self.tool_empty.setVisible(all(item.isHidden() for item in self.tool_rows.values()))

    def save_tool_settings(self, *_args) -> None:
        """Enregistre favoris, catégories et regroupement. Les réglages d'outils absents (extension en cours de mise
        à jour, par exemple) sont conservés."""
        known = {tool["id"] for tool in self.tools}
        favorites = [i for i in self.tool_settings["favorites"] if i not in known]
        favorites += [i for i, box in self.favorite_boxes.items() if box.isChecked()]
        categories = {k: v for k, v in self.tool_settings["categories"].items() if k not in known}
        for tool in self.tools:
            chosen = tools_menu.clean_category(self.category_boxes[tool["id"]].currentText())
            if chosen != tools_menu.clean_category(tool.get("category", "")):
                categories[tool["id"]] = chosen  # vide : rangé à la racine malgré la catégorie de l'auteur
        group = self.group_box.isChecked() if hasattr(self, "group_box") else self.tool_settings["group"]
        self.tool_settings = {"favorites": favorites, "categories": categories, "group": group}
        tools_menu.save_settings(self.tool_settings)

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
        self.add_tab("Notifications", section)

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
        section.body.addWidget(group_title("Démarrage et raccourcis"))
        self.startup = QCheckBox("Démarrer avec Windows")
        self.startup.setChecked(startup.is_enabled())
        self.startup.toggled.connect(self.toggle_startup)
        section.body.addWidget(self.startup)
        self.shortcut_boxes = {}
        for location, text in (("desktop", "Raccourci sur le bureau"),):
            box = QCheckBox(text)
            box.setChecked(shortcuts.is_enabled(location))
            box.toggled.connect(lambda enabled, loc=location: self.toggle_shortcut(loc, enabled))
            self.shortcut_boxes[location] = box
            section.body.addWidget(box)

        section.body.addSpacing(10)
        section.body.addWidget(group_title("Données"))
        section.body.addWidget(muted("Le journal des erreurs et les réglages sont dans le dossier des données du lanceur."))
        row = QHBoxLayout()
        for text, slot in (("Ouvrir le journal", self.open_log), ("Dossier des données", self.open_data_dir)):
            button = QPushButton(text)
            button.clicked.connect(slot)
            row.addWidget(button)
        row.addStretch(1)
        section.body.addLayout(row)
        section.body.addSpacing(10)
        section.body.addWidget(group_title("À propos"))
        section.body.addWidget(
            muted(f"Tools Launcher {launcher_version()} · Python {platform.python_version()} · PySide6 {PySide6.__version__}")
        )
        self.add_tab("Général", section)

    def toggle_startup(self, enabled: bool) -> None:
        try:
            startup.enable() if enabled else startup.disable()
        except (OSError, subprocess.SubprocessError) as e:
            QMessageBox.warning(self, "Démarrage avec Windows", f"Impossible de modifier le démarrage automatique :\n{e}")
            self.startup.blockSignals(True)  # remet la case dans l'état réel
            self.startup.setChecked(startup.is_enabled())
            self.startup.blockSignals(False)

    def toggle_shortcut(self, location: str, enabled: bool) -> None:
        try:
            shortcuts.enable(location) if enabled else shortcuts.disable(location)
        except (OSError, subprocess.SubprocessError) as e:
            QMessageBox.warning(self, "Raccourci", f"Impossible de modifier le raccourci :\n{e}")
            box = self.shortcut_boxes[location]
            box.blockSignals(True)  # remet la case dans l'état réel
            box.setChecked(shortcuts.is_enabled(location))
            box.blockSignals(False)

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
