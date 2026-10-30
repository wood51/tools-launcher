"""Canal outil → lanceur : un tube nommé local, un message JSON par ligne.

Côté lanceur : `ChannelServer` (Qt). Côté outil : `send_message` dans core/api.py
(stdlib seulement). Le lanceur ne fait confiance qu'au format : chaque champ est
vérifié, un message invalide est journalisé et ignoré.
"""

import json

from PySide6.QtCore import QLockFile, QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from core.api import log
from core.paths import CHANNEL_NAME, DATA_DIR

MAX_TEXT = 500
MAX_LINE = 4096
LEVELS = ("info", "warning", "error")
BADGES = ("blue", "red")


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("texte attendu")
    return value[:MAX_TEXT]


class ChannelServer(QObject):
    """Reçoit les messages des outils et les applique au lanceur (`host`, voir PluginHost)."""

    def __init__(self, host, on_restart=None) -> None:
        super().__init__()
        self._host = host
        self._on_restart = on_restart  # appelé pour la commande `restart` (fenêtre Paramètres)
        DATA_DIR.mkdir(exist_ok=True)
        self._lock = QLockFile(str(DATA_DIR / "launcher.lock"))  # le nom du tube seul ne suffit pas
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.UserAccessOption)  # l'utilisateur seul
        self._server.newConnection.connect(self._on_connection)

    def start(self) -> bool:
        """False si le nom est déjà pris : un autre lanceur tourne."""
        return self._lock.tryLock(0) and self._server.listen(CHANNEL_NAME)

    def _on_connection(self) -> None:
        while (socket := self._server.nextPendingConnection()) is not None:
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(socket.deleteLater)
            self._read(socket)

    def _read(self, socket: QLocalSocket) -> None:
        while socket.canReadLine():
            line = bytes(socket.readLine(MAX_LINE)).decode("utf-8", errors="replace")
            self._handle(line)
        if socket.bytesAvailable() > MAX_LINE:  # une ligne qui ne finit jamais
            socket.abort()

    def _handle(self, line: str) -> None:
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("objet JSON attendu")
            extension_id = _text(message.get("ext"))
            command = message.get("cmd")
            if command == "notify":
                level = message.get("level", "info")
                if level not in LEVELS:
                    raise ValueError(f"niveau inconnu : {level!r}")
                self._host.notify(
                    extension_id, _text(message.get("title")), _text(message.get("message")), level
                )
            elif command == "set_badge":
                level = message.get("level")
                if level is None:
                    self._host.badges.pop(extension_id, None)
                elif level in BADGES:
                    self._host.badges[extension_id] = level
                else:
                    raise ValueError(f"badge inconnu : {level!r}")
                self._host.refresh_icon()
            elif command == "restart" and self._on_restart is not None:
                self._on_restart()
            else:
                raise ValueError(f"commande inconnue : {command!r}")
        except ValueError as e:
            log("channel", f"message ignoré ({e}) : {line.strip()[:200]}")
