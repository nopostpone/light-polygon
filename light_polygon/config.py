from __future__ import annotations

import os
import tomllib
from pathlib import Path

import tomli_w

DEFAULT_DATA_DIR = Path.home() / ".light-polygon"


def default_config() -> dict:
    return {
        "data_dir": str(DEFAULT_DATA_DIR),
    }


class Config:
    def __init__(self) -> None:
        self._config_path = Path.home() / ".light-polygon" / "config.toml"
        self._data: dict = {}
        self._load()
        # Environment variable overrides config file
        if env_dir := os.environ.get("LIGHT_POLYGON_DATA_DIR"):
            self._data["data_dir"] = env_dir

    def _load(self) -> None:
        if self._config_path.exists():
            with open(self._config_path, "rb") as f:
                self._data = tomllib.load(f)
        else:
            self._data = default_config()

    def save(self) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "wb") as f:
            tomli_w.dump(self._data, f)

    @property
    def data_dir(self) -> Path:
        path = Path(self._data.get("data_dir", str(DEFAULT_DATA_DIR)))
        path.mkdir(parents=True, exist_ok=True)
        return path

    @data_dir.setter
    def data_dir(self, value: str | Path) -> None:
        self._data["data_dir"] = str(value)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "light-polygon.db"

    @property
    def problems_dir(self) -> Path:
        p = self.data_dir / "problems"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
