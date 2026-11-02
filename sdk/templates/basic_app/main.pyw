import sys

from ui import button, create_app, window


def main() -> int:
    app, api = create_app("mon_outil")
    root, layout = window("Mon outil")
    layout.addWidget(button("Tester", lambda: print("Le bouton fonctionne")))
    root.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
