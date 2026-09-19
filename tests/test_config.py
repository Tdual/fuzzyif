import pytest

from fuzzyif import config
from fuzzyif.errors import ConfigError


@pytest.fixture(autouse=True)
def _reset():
    config.reset_settings()
    yield
    config.reset_settings()


def test_defaults():
    s = config.get_settings()
    assert s.model == "jev-latest"
    assert s.timeout == 10.0
    assert s.cache_size == 1024
    assert s.base_url == "https://api.typesafe.ai"
    assert s.max_retries == 3
    assert s.api_key is None


def test_resolve_explicit_wins(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "from-env")
    assert config.resolve_api_key("explicit") == "explicit"


def test_resolve_env(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "from-env")
    assert config.resolve_api_key(None) == "from-env"


def test_resolve_file(tmp_path):
    d = tmp_path / ".config" / "typesafe"
    d.mkdir(parents=True)
    (d / "api_key").write_text("  from-file \n\nsecond line\n")
    assert config.resolve_api_key(None) == "from-file"


def test_resolve_env_beats_file(monkeypatch, tmp_path):
    d = tmp_path / ".config" / "typesafe"
    d.mkdir(parents=True)
    (d / "api_key").write_text("from-file")
    monkeypatch.setenv("TYPESAFE_API_KEY", "from-env")
    assert config.resolve_api_key(None) == "from-env"


def test_resolve_missing_raises():
    with pytest.raises(ConfigError):
        config.resolve_api_key(None)


def test_update_and_get():
    config.update_settings(model="jev-x", timeout=1.5)
    assert config.get_settings().model == "jev-x"
    assert config.get_settings().timeout == 1.5
