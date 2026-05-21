from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tomllib as TOMLLIB
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    TOMLLIB = None  # type: ignore[assignment]


DEFAULT_CONFIG: dict[str, Any] = {
    "arxiv": {
        "base_url": "https://export.arxiv.org/api/query",
        "default_categories": ["quant-ph"],
        "max_results": 200,
        "page_size": 100,
        "sort_by": "submittedDate",
        "sort_order": "descending",
        "request_timeout_seconds": 30,
    },
    "paths": {
        "raw_arxiv_dir": "data/raw/arxiv",
        "reports_dir": "data/reports",
        "user_profile_dir": "user_profile",
    },
}


DEFAULT_CONFIG_PATH = Path("config/default.toml")
LOCAL_CONFIG_PATH = Path("config/local.toml")


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config = _deep_copy(DEFAULT_CONFIG)
    if path is None:
        path = DEFAULT_CONFIG_PATH if DEFAULT_CONFIG_PATH.exists() else None

    if path is None:
        return config

    if TOMLLIB is None:
        raise RuntimeError("Reading TOML config requires Python 3.11 or newer.")

    config_path = Path(path)
    _merge_toml_file(config, config_path)

    if config_path == DEFAULT_CONFIG_PATH and LOCAL_CONFIG_PATH.exists():
        _merge_toml_file(config, LOCAL_CONFIG_PATH)

    return config


def _merge_toml_file(config: dict[str, Any], config_path: Path) -> None:
    with config_path.open("rb") as file_handle:
        loaded = TOMLLIB.load(file_handle)
    _deep_merge(config, loaded)


def _deep_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _deep_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_deep_copy(item) for item in value]
    return value


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
