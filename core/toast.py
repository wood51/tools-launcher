from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.theme import discover_themes, get_theme

LEVEL_COLORS = {"warning": "#e0a030", "error": "#e5484d"}  # "info" prend l'accent du thème
MARGIN = 12
SPACING = 8


class Toast(QWidget):
    """Petite notification sans bordure, aux couleurs du thème. Un clic la ferme."""

    def __init__(self, title: str, message: str, level: str, on_click: Callable | None) -> None:
        super().__init__(
            None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedWidth(320)
        self._on_click = on_click

        theme = discover_themes().get(get_theme())
        colors = theme["colors"] if theme else {}
        accent = LEVEL_COLORS.get(level) or colors.get("ACCENT", "#4d85f2")
        self.setObjectName("toast")
        self.setStyleSheet(
            f"#toast {{ background: {colors.get('SURFACE', '#1c2029')};"
            f" border: 1px solid {colors.get('BORDER', '#323a4a')};"
            f" border-left: 4px solid {accent}; }}"
            f" QLabel {{ color: {colors.get('TEXT', '#e6e9f0')}; background: transparent; }}"
        )

        layout = QVBoxLayout(self)
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setTextFormat(Qt.RichText)
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(message_label)

    def mousePressEvent(self, event) -> None:
        if self._on_click:
            self._on_click()
        self.close()


class ToastManager:
    """Empile les notifications en bas à droite de l'écran, les plus récentes en bas."""

    def __init__(self) -> None:
        self._toasts: list[Toast] = []

    def show(
        self,
        title: str,
        message: str,
        level: str = "info",
        on_click: Callable | None = None,
        duration: int = 5000,
    ) -> None:
        toast = Toast(title, message, level, on_click)
        self._toasts.append(toast)
        toast.destroyed.connect(lambda *_: self._forget(toast))
        toast.show()
        self._layout()
        QTimer.singleShot(duration, toast.close)

    def _forget(self, toast: Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._layout()

    def _layout(self) -> None:
        area = QGuiApplication.primaryScreen().availableGeometry()
        y = area.bottom() - MARGIN
        for toast in reversed(self._toasts):
            toast.adjustSize()
            y -= toast.height()
            toast.move(area.right() - MARGIN - toast.width(), y)
            y -= SPACING
