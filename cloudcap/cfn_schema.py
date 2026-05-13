import json
import os
import requests
from typing import Any

SCHEMA_URL = "https://schema.cloudformation.us-east-1.amazonaws.com/{filename}"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cfn_schema_cache")


def _type_to_filename(resource_type: str) -> str:
    return resource_type.replace("::", "-").lower() + ".json"


def _cache_path(resource_type: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, _type_to_filename(resource_type))


def fetch(resource_type: str) -> dict[str, Any]:
    path = _cache_path(resource_type)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)

    url = SCHEMA_URL.format(filename=_type_to_filename(resource_type))
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    with open(path, "w") as f:
        json.dump(data, f)

    return data


def summarize(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "typeName": schema.get("typeName"),
        "description": schema.get("description"),
        "properties": schema.get("properties", {}),
    }
