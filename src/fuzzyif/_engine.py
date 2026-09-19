"""Shared plumbing for the public functions: settings, cache, client, validation."""
from __future__ import annotations

import logging
import threading
from typing import Any, TypeVar

from . import config as _config
from .cache import LRUCache
from .client import JevClient
from .config import Settings
from .errors import APIError

log = logging.getLogger("fuzzyif")

_lock = threading.Lock()
_cache: LRUCache | None = None
_client: JevClient | None = None
client_override: Any = None  # tests set an object exposing ask(state, questions)

T = TypeVar("T")


def configure(**kwargs) -> Settings:
    """Override process-wide settings. Drops the cache and the HTTP client."""
    global _cache, _client
    with _lock:
        s = _config.update_settings(**kwargs)
        _cache = None
        _client = None
    return s


def reset_for_tests() -> None:
    global _cache, _client, client_override
    with _lock:
        _config.reset_settings()
        _cache = None
        _client = None
        client_override = None


def cache() -> LRUCache:
    global _cache
    c = _cache
    if c is None:
        with _lock:
            if _cache is None:
                _cache = LRUCache(_config.get_settings().cache_size)
            c = _cache
    return c


def client() -> Any:
    global _client
    if client_override is not None:
        return client_override
    c = _client
    if c is None:
        with _lock:
            if _client is None:
                _client = JevClient(_config.get_settings())
            c = _client
    return c


def cache_key(kind: str, question_key: str, text: str) -> tuple:
    return (kind, _config.get_settings().model, question_key, text)


def validate_text(text: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")


def as_float(value: Any, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise APIError(f"Jev API field {what!r} is not a number: {value!r}")
    return float(value)


def on_api_error(e: APIError, default: T | None) -> T:
    """Return `default` after logging, or re-raise when no default was given."""
    if default is None:
        raise e
    log.warning("fuzzyif: API call failed, returning default=%r: %s", default, e)
    return default
