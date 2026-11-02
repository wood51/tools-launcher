"""Traductions Qt communes aux fenêtres et dialogues natifs."""

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator


def install_french_qt(app) -> bool:
    """Traduit les boutons standard Qt et conserve le traducteur tant que l'app vit."""
    QLocale.setDefault(QLocale(QLocale.Language.French, QLocale.Country.France))
    existing = getattr(app, "_tools_launcher_translators", None)
    if existing is not None:
        return bool(existing)
    translator = QTranslator(app)
    translations = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    loaded = translator.load("qtbase_fr", translations)
    app._tools_launcher_translators = [translator] if loaded else []
    if loaded:
        app.installTranslator(translator)
    return loaded
