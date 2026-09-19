import json as _json

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(request, monkeypatch, tmp_path):
    """Hide the real API key from unit tests. Integration tests opt out."""
    if "test_integration" in request.node.nodeid:
        yield
        return
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    yield


class FakeResponse:
    def __init__(self, status, body, headers=None):
        self.status = status
        self._body = body if isinstance(body, bytes) else body.encode()
        self._headers = headers or {}

    def read(self):
        return self._body

    def getheader(self, name, default=None):
        return self._headers.get(name, default)


class FakeConnection:
    """Stand-in for http.client.HTTPSConnection.

    scripted: one entry per getresponse() call, either
      ("ok", status, body_dict_or_str, headers) or ("raise", exception)
    """

    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.requests = []
        self.closed = 0

    def request(self, method, url, body=None, headers=None):
        self.requests.append((method, url, body, headers))

    def getresponse(self):
        kind, *rest = self.scripted.pop(0)
        if kind == "raise":
            raise rest[0]
        status, body, headers = rest
        if isinstance(body, dict):
            body = _json.dumps(body)
        return FakeResponse(status, body, headers)

    def close(self):
        self.closed += 1


@pytest.fixture
def fake_conn():
    """Return (factory_builder, holder). factory_builder(scripted) -> connection_factory."""
    holder = {}

    def build(scripted):
        conn = FakeConnection(scripted)
        holder["conn"] = conn
        return lambda host, timeout: conn

    return build, holder
