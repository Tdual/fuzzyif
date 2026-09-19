"""Settings and API key resolution."""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from .errors import ConfigError

ENV_VAR = "TYPESAFE_API_KEY"
KEY_FILE = Path("~/.config/typesafe/api_key")


@dataclass(frozen=True)
class Settings:
    api_key: str | None = None
    model: str = "jev-latest"
    timeout: float = 10.0
    cache_size: int = 1024
    base_url: str = "https://api.typesafe.ai"
    max_retries: int = 3


_settings = Settings()


def get_settings() -> Settings:
    return _settings


def set_settings(s: Settings) -> None:
    global _settings
    _settings = s


def reset_settings() -> None:
    set_settings(Settings())


def update_settings(**kwargs) -> Settings:
    """Return and store a copy of the current settings with kwargs applied."""
    s = replace(_settings, **kwargs)
    set_settings(s)
    return s


def resolve_api_key(explicit: str | None) -> str:
    """Look up the API key: explicit value, then env var, then key file."""
    if explicit:
        return explicit
    env = os.environ.get(ENV_VAR)
    if env and env.strip():
        return env.strip()
    path = KEY_FILE.expanduser()
    if path.is_file():
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        if lines and lines[0].strip():
            return lines[0].strip()
    raise ConfigError(
        f"TypeSafe API key not found. Set it via configure(api_key=...), "
        f"the {ENV_VAR} environment variable, or {KEY_FILE}."
    )
