"""Composants UI simples et cohérents pour les outils Tools Launcher."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFormLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget


def _api(name: str):
    try:
        from core.api import get_api
        return get_api(name)
    except ImportError:
        class LocalAPI:
            def __init__(self, extension_id: str):
                self.id = extension_id
                self.data_dir = Path(__file__).resolve().parent / "data"
                self.data_dir.mkdir(exist_ok=True)

            def load_json(self, filename: str):
                path = self.data_dir / filename
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except (FileNotFoundError, ValueError):
                    return None

            def save_json(self, filename: str, data):
                (self.data_dir / filename).write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                )

            def load_settings(self):
                data = self.load_json("settings.json")
                return data if isinstance(data, dict) else {}

            def save_settings(self, data):
                self.save_json("settings.json", data)

            def log(self, message):
                print(f"[{self.id}] {message}")

            def notify(self, title, message, level="info"):
                self.log(f"{level}: {title} - {message}")
                return False

            def set_badge(self, level):
                return False

            def launch_tool(self, extension_id):
                self.log(f"outil launcher indisponible en autonome : {extension_id}")

            def open_path(self, path):
                target = Path(path)
                if not target.exists():
                    self.log(f"chemin introuvable : {target}")
                    return False
                try:
                    os.startfile(str(target))
                    return True
                except OSError as error:
                    self.log(f"ouverture impossible : {error}")
                    return False

            def open_file(self, path):
                target = Path(path)
                return self.open_path(target) if target.is_file() else False

            def open_folder(self, path):
                target = Path(path)
                return self.open_path(target) if target.is_dir() else False

            def choose_file(self, parent=None, title="Choisir un fichier", filter="Tous les fichiers (*)"):
                from PySide6.QtWidgets import QFileDialog
                filename, _ = QFileDialog.getOpenFileName(parent, title, "", filter)
                return Path(filename) if filename else None

            def choose_folder(self, parent=None, title="Choisir un dossier"):
                from PySide6.QtWidgets import QFileDialog
                folder = QFileDialog.getExistingDirectory(parent, title)
                return Path(folder) if folder else None

            def confirm(self, parent, title, message):
                answer = QMessageBox.question(parent, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                return answer == QMessageBox.Yes

            def get_app_info(self):
                return {"id": self.id, "mode": "standalone"}

        return LocalAPI(name)


def create_app(name: str):
    app = QApplication.instance() or QApplication(sys.argv)
    api = _api(name)
    try:
        api.apply_theme(app)
    except AttributeError:
        app.setStyleSheet("QWidget { font-size: 10pt; }")
    return app, api


def window(title: str, width: int = 520, height: int = 360):
    root = QWidget()
    root.setObjectName("root")
    root.setWindowTitle(title)
    root.resize(width, height)
    return root, QVBoxLayout(root)


def button(text: str, callback=None, variant: str = "accent"):
    if variant not in {"accent", "neutral", "danger"}:
        raise ValueError(f"variante inconnue : {variant}")
    item = QPushButton(text)
    item.setObjectName({"accent": "primary", "danger": "danger", "neutral": ""}[variant])
    if callback:
        item.clicked.connect(callback)
    return item


def field(label: str, placeholder: str = ""):
    container = QWidget()
    layout = QFormLayout(container)
    item = QLineEdit()
    item.setPlaceholderText(placeholder)
    layout.addRow(QLabel(label), item)
    return container, item


def show_error(parent, title: str, message: str) -> None:
    QMessageBox.critical(parent, title, message)
