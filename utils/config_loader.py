import yaml
import os
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


class Config:
    def __init__(self, path: str = None):
        path = path or os.environ.get("WX_REPLY_CONFIG", str(DEFAULT_CONFIG_PATH))
        with open(path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f)

    def get(self, *keys: str):
        node = self._data
        for k in keys:
            if isinstance(node, dict):
                node = node.get(k)
            else:
                return None
        return node

    @property
    def wechat(self) -> dict:
        return self._data.get("wechat", {})

    @property
    def ai(self) -> dict:
        return self._data.get("ai", {})

    @property
    def human(self) -> dict:
        return self._data.get("human", {})

    @property
    def schedule(self) -> dict:
        return self._data.get("schedule", {})

    @property
    def filters(self) -> dict:
        return self._data.get("filters", {})


_config_instance: "Config | None" = None


def load_config(path: str = None) -> Config:
    global _config_instance
    _config_instance = Config(path)
    return _config_instance


def get_config() -> Config:
    if _config_instance is None:
        return load_config()
    return _config_instance
