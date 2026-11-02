def register(api) -> None:
    api.add_action("Tester", lambda: api.notify("Mon plugin", "Le plugin fonctionne."))


def build_menu(menu) -> None:
    menu.addAction("Action exemple")
