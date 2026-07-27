"""Configuration loading for local simulator and fog runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as config_file:
        config = json.load(config_file)
    if not isinstance(config, dict) or "domains" not in config or "fog" not in config:
        raise ValueError("configuration must define fog and domains")
    return config