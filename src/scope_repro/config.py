from __future__ import annotations

import json
from pathlib import Path


def load_config(path: str | Path) -> dict:
    """Load JSON-compatible YAML configuration.

    The repository keeps `.yaml` files valid as JSON so the core scripts can run
    even when PyYAML is not installed. Standard YAML parsers can also read them.
    """
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, data: dict) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
