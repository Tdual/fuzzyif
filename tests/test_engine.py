import logging

import pytest

from fuzzyif import _engine as eng
from fuzzyif.errors import APIError, ConfigError


@pytest.fixture(autouse=True)
def _reset():
    eng.reset_for_tests()
    yield
    eng.reset_for_tests()


def test_configure_updates_settings():
    s = eng.configure(api_key="k", model="jev-x")
    assert s.model == "jev-x"


def test_cache_key_includes_model():
    eng.configure(model="a")
    k1 = eng.cache_key("noul", "q", "t")
    eng.configure(model="b")
    k2 = eng.cache_key("noul", "q", "t")
    assert k1 != k2
    assert k1 == ("noul", "a", "q", "t")


def test_configure_drops_cache():
    eng.configure(api_key="k")
    eng.cache().put("x", 1)
    eng.configure(timeout=3)
    assert "x" not in eng.cache()


def test_cache_size_from_settings():
    eng.configure(cache_size=0)
    eng.cache().put("x", 1)
    assert "x" not in eng.cache()


def test_client_override():
    sentinel = object()
    eng.client_override = sentinel
    assert eng.client() is sentinel


def test_client_requires_key():
    eng.configure()
    with pytest.raises(ConfigError):
        eng.client()


def test_validate_text():
    with pytest.raises(ValueError):
        eng.validate_text("")
    with pytest.raises(ValueError):
        eng.validate_text("  \n")
    with pytest.raises(ValueError):
        eng.validate_text(None)  # type: ignore[arg-type]
    eng.validate_text("ok")


def test_as_float():
    assert eng.as_float(1, "x") == 1.0
    assert eng.as_float(0.5, "x") == 0.5
    with pytest.raises(APIError):
        eng.as_float(True, "x")
    with pytest.raises(APIError):
        eng.as_float("0.5", "x")
    with pytest.raises(APIError):
        eng.as_float(None, "x")


def test_on_api_error_returns_default_and_logs(caplog):
    with caplog.at_level(logging.WARNING, logger="fuzzyif"):
        assert eng.on_api_error(APIError("down"), False) is False
    assert "down" in caplog.text


def test_on_api_error_reraises():
    with pytest.raises(APIError):
        eng.on_api_error(APIError("down"), None)
