"""Assemble uniquement les fichiers publics du site et le guide canonique."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
SITE_FILES = (
    "index.html", "styles.css", "main.js", "assets/launcher.png",
    "assets/menu.png", "assets/launcher-menu.png", "assets/settings.png",
    "assets/catalog.png", "assets/game-radar.png",
)


def build(destination=None):
    destination = Path(destination) if destination else ROOT / "dist/site"
    sources = [(ROOT / "site" / name, name) for name in SITE_FILES]
    sources += [(ROOT / "docs/installation" / name, name) for name in (
        "Guide-installation-Windows.pdf", "LIRE-MOI.txt")]
    for source, name in sources:
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"Fichier public manquant ou lien interdit : {name}")
    # La destination dédiée n'est jamais nettoyée récursivement.
    for source, name in sources:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    unexpected = [p for p in destination.rglob("*") if p.is_file()
                  and p.relative_to(destination).as_posix() not in {n for _, n in sources}]
    if unexpected:
        raise ValueError(f"Fichiers inattendus dans le site : {unexpected}")
    print(destination)
    return destination


if __name__ == "__main__":
    build()
