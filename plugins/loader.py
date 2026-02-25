import json
import os
import importlib
from pathlib import Path

PLUGINS_DIR = Path("plugins")
_loaded_plugins = {}
_disabled_plugins: set = set()


def get_plugin_manifest(plugin_name: str) -> dict | None:
    manifest_path = PLUGINS_DIR / plugin_name / "manifest.json"
    if not manifest_path.exists():
        return None
    with open(manifest_path) as f:
        return json.load(f)


def list_plugins() -> list[dict]:
    plugins = []
    if not PLUGINS_DIR.exists():
        return plugins
    for item in PLUGINS_DIR.iterdir():
        if item.is_dir() and (item / "manifest.json").exists():
            manifest = get_plugin_manifest(item.name)
            if manifest:
                manifest["name"] = item.name
                manifest["enabled"] = item.name in _loaded_plugins and item.name not in _disabled_plugins
                plugins.append(manifest)
    return plugins


def enable_plugin(plugin_name: str):
    _disabled_plugins.discard(plugin_name)


def disable_plugin(plugin_name: str):
    _disabled_plugins.add(plugin_name)


async def load_plugin(bot, plugin_name: str) -> bool:
    manifest = get_plugin_manifest(plugin_name)
    if not manifest:
        return False
    cog_file = manifest.get("cog", f"{plugin_name}.py")
    cog_path = f"plugins.{plugin_name}.{cog_file.replace('.py', '')}"
    try:
        await bot.load_extension(cog_path)
        _loaded_plugins[plugin_name] = manifest
        return True
    except Exception as e:
        print(f"Failed to load plugin {plugin_name}: {e}")
        return False


async def unload_plugin(bot, plugin_name: str) -> bool:
    if plugin_name not in _loaded_plugins:
        return False
    manifest = _loaded_plugins[plugin_name]
    cog_file = manifest.get("cog", f"{plugin_name}.py")
    cog_path = f"plugins.{plugin_name}.{cog_file.replace('.py', '')}"
    try:
        await bot.unload_extension(cog_path)
        del _loaded_plugins[plugin_name]
        return True
    except Exception as e:
        print(f"Failed to unload plugin {plugin_name}: {e}")
        return False