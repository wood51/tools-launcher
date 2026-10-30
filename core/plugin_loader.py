import importlib.util
import json
import sys

from core.config import get_section, set_section
from core.paths import LEGACY_PLUGINS_FILE
from core.plugin_api import PluginAPI, PluginHost, log_error
from core.registry import discover_extensions


def discover_plugins() -> list[dict]:
    """Les extensions qui ont un bloc `plugin`, avec `entry` et `folder`."""
    return [
        {
            "id": ext["id"],
            "name": ext["name"],
            "version": ext["version"],
            "tooltip": ext.get("tooltip", ""),
            "entry": ext["plugin"]["entry"],
            "folder": ext["folder"],
        }
        for ext in discover_extensions()
        if "plugin" in ext
    ]


def load_disabled() -> set[str]:
    """Plugins désactivés (config.json, section `plugins`). Reprend l'ancien plugins.json s'il reste."""
    section = get_section("plugins")
    if "disabled" not in section:
        try:
            legacy = json.loads(LEGACY_PLUGINS_FILE.read_text(encoding="utf-8-sig"))["disabled"]
            return {i for i in legacy if isinstance(i, str)}
        except (OSError, ValueError, KeyError, TypeError):
            return set()
    disabled = section["disabled"]
    return {i for i in disabled if isinstance(i, str)} if isinstance(disabled, list) else set()


def save_disabled(disabled: set[str]) -> None:
    set_section("plugins", {**get_section("plugins"), "disabled": sorted(disabled)})
    LEGACY_PLUGINS_FILE.unlink(missing_ok=True)  # migré : l'ancien fichier ne sert plus


def import_plugin(plugin: dict):
    """Charge `entry` comme un paquet : le plugin peut faire `from .autre_module import ...`."""
    name = f"plugin_{plugin['id']}"
    path = plugin["folder"] / plugin["entry"]
    spec = importlib.util.spec_from_file_location(
        name, path, submodule_search_locations=[str(plugin["folder"])]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_plugins(host: PluginHost) -> None:
    disabled = load_disabled()
    for plugin in discover_plugins():
        if plugin["id"] in disabled:
            continue
        try:
            module = import_plugin(plugin)
            module.register(PluginAPI(plugin["id"], host))
        except Exception as e:
            log_error(plugin["id"], e)
