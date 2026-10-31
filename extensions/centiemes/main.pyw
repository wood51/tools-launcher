import sys
from fractions import Fraction
from pathlib import Path

try:
    from core.api import get_api
except ImportError:  # lancé hors du lanceur
    import ctypes

    ctypes.windll.user32.MessageBoxW(0, "Cet outil se lance depuis le lanceur Tools Launcher (menu Outils).", "Centièmes ↔ heures", 0x10)
    raise SystemExit(1)

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conversion as conv  # noqa: E402

FIELDS = (
    ("clock", "Heures : minutes", "1:30 ou 1h30", conv.parse_clock, conv.to_clock),
    ("minutes", "Minutes", "90", lambda text: conv.parse_number(text) / 60, conv.to_minutes),
    ("decimal", "Heures décimales", "1,5", conv.parse_number, conv.to_decimal_hours),
    ("centiemes", "Centièmes d'heure", "150", lambda text: conv.parse_number(text) / 100, conv.to_centiemes),
)


def card(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 12, 16, 14)
    layout.setSpacing(8)
    heading = QLabel(title)
    heading.setObjectName("section")
    layout.addWidget(heading)
    return frame, layout


def muted(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(True)
    return label


class Converter(QWidget):
    def __init__(self, api) -> None:
        super().__init__()
        self.api = api
        self.current: Fraction | None = None
        self.entries: list[Fraction] = []
        self.setObjectName("root")
        self.setWindowTitle("Centièmes ↔ heures")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(self.build_conversion())
        layout.addWidget(self.build_cumul())
        self.setMinimumWidth(500)
        self.load_entries()
        self.update_total()

    #### Conversion ####

    def build_conversion(self) -> QFrame:
        frame, layout = card("Conversion")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)
        self.edits: dict[str, QLineEdit] = {}
        for row, (key, label, example, _parse, _format) in enumerate(FIELDS):
            edit = QLineEdit()
            edit.setPlaceholderText(example)
            edit.textEdited.connect(lambda text, k=key: self.edited(k, text))
            edit.returnPressed.connect(self.add_entry)
            copy = QPushButton("Copier")
            copy.clicked.connect(lambda checked=False, e=edit: QApplication.clipboard().setText(e.text()))
            self.edits[key] = edit
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(edit, row, 1)
            grid.addWidget(copy, row, 2)
        layout.addLayout(grid)
        self.status = muted()
        layout.addWidget(self.status)
        layout.addWidget(muted("1 heure = 100 centièmes ; 1 centième = 0,6 minute = 36 secondes. Entrée ajoute la valeur au cumul."))
        return frame

    def edited(self, key: str, text: str) -> None:
        field = next(f for f in FIELDS if f[0] == key)
        edit = self.edits[key]
        if not text.strip():
            self.current = None
            for other in self.edits.values():
                other.clear()
                self.mark(other, False)
            self.status.setText("")
            return
        try:
            hours = field[3](text)
        except conv.ParseError as error:
            self.mark(edit, True)
            self.status.setText(str(error))
            return
        self.mark(edit, False)
        self.current = hours
        for other_key, _label, _example, _parse, fmt in FIELDS:
            if other_key != key:
                self.edits[other_key].setText(fmt(hours))
                self.mark(self.edits[other_key], False)
        self.status.setText(f"Exactement : {conv.exact(hours)}")

    @staticmethod
    def mark(edit: QLineEdit, invalid: bool) -> None:
        edit.setProperty("invalid", invalid)
        edit.style().unpolish(edit)
        edit.style().polish(edit)

    #### Cumul ####

    def build_cumul(self) -> QFrame:
        frame, layout = card("Cumul")
        self.list = QListWidget()
        self.list.setFixedHeight(130)
        layout.addWidget(self.list)
        buttons = QHBoxLayout()
        add = QPushButton("Ajouter")
        add.setObjectName("primary")
        add.clicked.connect(self.add_entry)
        remove = QPushButton("Retirer")
        remove.clicked.connect(self.remove_entry)
        clear = QPushButton("Tout effacer")
        clear.clicked.connect(self.clear_entries)
        for button in (add, remove, clear):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        QShortcut(QKeySequence(Qt.Key_Delete), self.list, activated=self.remove_entry)

        self.total_label = QLabel()
        self.total_label.setObjectName("total")
        layout.addWidget(self.total_label)
        self.total_detail = muted()
        layout.addWidget(self.total_detail)
        copies = QHBoxLayout()
        for text, fmt in (("Copier le total H:MM", conv.to_clock), ("Copier le total en centièmes", conv.to_centiemes)):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, f=fmt: QApplication.clipboard().setText(f(conv.total(self.entries))))
            copies.addWidget(button)
        copies.addStretch(1)
        layout.addLayout(copies)
        return frame

    def add_entry(self) -> None:
        if self.current is None:
            self.status.setText("Rien à ajouter : saisissez d'abord une durée.")
            return
        self.entries.append(self.current)
        self.list.addItem(self.entry_item(self.current))
        self.list.scrollToBottom()
        self.update_total()
        self.save_entries()

    def entry_item(self, hours: Fraction) -> QListWidgetItem:
        return QListWidgetItem(f"{conv.to_clock(hours)}   ·   {conv.to_centiemes(hours)} centièmes")

    def remove_entry(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            del self.entries[row]
            self.list.takeItem(row)
            self.update_total()
            self.save_entries()

    def clear_entries(self) -> None:
        self.entries.clear()
        self.list.clear()
        self.update_total()
        self.save_entries()

    def update_total(self) -> None:
        hours = conv.total(self.entries)
        count = len(self.entries)
        self.total_label.setText(f"Total : {conv.to_clock(hours)}   ·   {conv.to_centiemes(hours)} centièmes")
        self.total_detail.setText(
            f"{count} durée{'s' if count > 1 else ''} · {conv.to_decimal_hours(hours)} h · {conv.to_minutes(hours)} min · {conv.exact(hours)}"
            if count
            else "Aucune durée dans le cumul."
        )

    def load_entries(self) -> None:
        saved = self.api.load_settings().get("cumul", [])
        for text in saved if isinstance(saved, list) else []:
            hours = conv.load(text) if isinstance(text, str) else None
            if hours is not None:
                self.entries.append(hours)
                self.list.addItem(self.entry_item(hours))

    def save_entries(self) -> None:
        self.api.save_settings({"cumul": [conv.dump(hours) for hours in self.entries]})


def main() -> int:
    api = get_api()
    app = QApplication(sys.argv)
    api.apply_theme(app)
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "icon.svg")))
    window = Converter(api)
    window.show()
    window.edits["clock"].setFocus()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
