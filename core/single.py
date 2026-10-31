"""Une seule fenêtre par outil : relancer un outil déjà ouvert ramène sa fenêtre au premier plan.

Chaque outil écoute sur un tube nommé local (`tools-launcher-tool-<id>`). Une seconde instance
s'y connecte, demande de passer au premier plan, puis s'arrête. Le lanceur peut aussi y écrire `quit`
(`request_quit`) pour fermer la fenêtre d'un outil quand il quitte lui-même. Appelé par `core.theme.set_tool_identity`
(donc par tout outil lancé par le lanceur) ; un outil qui veut plusieurs fenêtres le déclare
dans son manifeste : `"tool": { "multiple": true }`.
"""

import sys

from PySide6.QtCore import QObject, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

NAME_PREFIX = "tools-launcher-tool-"


def raise_windows(app) -> None:
    for window in app.topLevelWidgets():
        if window.isVisible() and window.parent() is None:
            if window.isMinimized():
                window.showNormal()
            window.raise_()
            window.activateWindow()


class _Listener(QObject):
    def __init__(self, app, name: str) -> None:
        super().__init__(app)
        self._app = app
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.UserAccessOption)
        self._server.newConnection.connect(self._on_connection)
        self.listening = self._server.listen(name)

    def _on_connection(self) -> None:
        while (socket := self._server.nextPendingConnection()) is not None:
            socket.setProperty("quit", False)
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(lambda s=socket: self._finished(s))

    def _read(self, socket: QLocalSocket) -> None:
        if bytes(socket.readAll()).strip() == b"quit":
            socket.setProperty("quit", True)
            QTimer.singleShot(0, self._app.quit)

    def _finished(self, socket: QLocalSocket) -> None:
        self._read(socket)
        if not socket.property("quit"):  # simple connexion d'une seconde instance : montrer la fenêtre
            QTimer.singleShot(0, lambda: raise_windows(self._app))
        socket.deleteLater()


def request_quit(extension_id: str, timeout_ms: int = 300) -> bool:
    """Demande à l'outil `extension_id` de se fermer. False s'il ne tourne pas."""
    socket = QLocalSocket()
    socket.connectToServer(NAME_PREFIX + extension_id)
    if not socket.waitForConnected(timeout_ms):
        return False
    socket.write(b"quit\n")
    socket.waitForBytesWritten(timeout_ms)
    socket.disconnectFromServer()
    if socket.state() != QLocalSocket.UnconnectedState:
        socket.waitForDisconnected(timeout_ms)
    return True


def ensure_single_instance(app, extension_id: str) -> None:
    """Quitte le processus si l'outil tourne déjà (après avoir demandé à son instance de se montrer)."""
    name = NAME_PREFIX + extension_id
    probe = QLocalSocket()
    probe.connectToServer(name)
    if probe.waitForConnected(500):
        try:  # l'instance existante pourra alors prendre le premier plan
            import ctypes

            ctypes.windll.user32.AllowSetForegroundWindow(-1)
        except (AttributeError, OSError):
            pass
        probe.disconnectFromServer()
        probe.waitForDisconnected(500)
        sys.exit(0)
    app._single_listener = _Listener(app, name)  # garde la référence
