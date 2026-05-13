import os
from cloudcap.plugins import Plugin
from cloudcap.plugin_validator import load

CACHE_DIR = os.path.join(os.path.dirname(__file__), "plugins", "generated")


def _type_to_filename(resource_type: str) -> str:
    return resource_type.replace("::", "_").replace(" ", "") + ".py"


def save(resource_type: str, code: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, _type_to_filename(resource_type))
    with open(path, "w") as f:
        f.write(f"# Generated plugin for {resource_type}\n")
        f.write(code)
    return path


def load_all() -> list[type[Plugin]]:
    if not os.path.exists(CACHE_DIR):
        return []
    plugins = []
    for filename in os.listdir(CACHE_DIR):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(CACHE_DIR, filename)
        with open(path, "r") as f:
            code = f.read()
        try:
            plugins.append(load(code))
        except Exception as e:
            print(f"Warning: failed to load cached plugin {filename}: {e}")
    return plugins


def is_cached(resource_type: str) -> bool:
    path = os.path.join(CACHE_DIR, _type_to_filename(resource_type))
    return os.path.exists(path)
