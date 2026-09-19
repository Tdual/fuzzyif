from http.client import RemoteDisconnected

import pytest

from fuzzyif.client import JevClient
from fuzzyif.config import Settings
from fuzzyif.errors import APIError

Q = {"q": {"type": "noul", "instructions": "urgent?"}}
OK = {"model": "jev-1.13.0", "answers": {"q": {"type": "noul", "noul": 0.9}}, "usage": {}}


def make_client(factory, max_retries=3):
    c = JevClient(Settings(api_key="k", max_retries=max_retries))
    c.connection_factory = factory
    c.sleep = lambda _: None
    return c


def test_success(fake_conn):
    build, h = fake_conn
    c = make_client(build([("ok", 200, OK, {})]))
    assert c.ask("text", Q)["q"]["noul"] == 0.9
    method, url, body, headers = h["conn"].requests[0]
    assert method == "POST" and url == "/v1/systemone"
    assert headers["Authorization"] == "Bearer k"
    assert isinstance(body, bytes)
    assert b'"state": "text"' in body


def test_non_ascii_state_is_sent_as_utf8(fake_conn):
    build, h = fake_conn
    c = make_client(build([("ok", 200, OK, {})]))
    c.ask("\u30b5\u30fc\u30d0\u30fc\u304c\u843d\u3061\u305f \u12a0\u1295\u12f5", Q)  # Japanese + Amharic
    body = h["conn"].requests[0][2]
    assert isinstance(body, bytes)
    assert "\u30b5\u30fc\u30d0\u30fc" in body.decode("utf-8")


def test_reuses_connection(fake_conn):
    build, h = fake_conn
    c = make_client(build([("ok", 200, OK, {}), ("ok", 200, OK, {})]))
    c.ask("a", Q)
    c.ask("b", Q)
    assert len(h["conn"].requests) == 2


def test_4xx_no_retry(fake_conn):
    build, h = fake_conn
    c = make_client(build([("ok", 401, {"detail": "bad key"}, {})]))
    with pytest.raises(APIError) as ei:
        c.ask("a", Q)
    assert ei.value.status_code == 401
    assert ei.value.attempts == 1
    assert "bad key" in ei.value.body


def test_5xx_retries_then_succeeds(fake_conn):
    build, h = fake_conn
    c = make_client(build([("ok", 503, "down", {}), ("ok", 503, "down", {}), ("ok", 200, OK, {})]))
    assert c.ask("a", Q)["q"]["noul"] == 0.9
    assert len(h["conn"].requests) == 3


def test_5xx_exhausts(fake_conn):
    build, h = fake_conn
    c = make_client(build([("ok", 500, "x", {})] * 3), max_retries=3)
    with pytest.raises(APIError) as ei:
        c.ask("a", Q)
    assert ei.value.attempts == 3
    assert ei.value.status_code == 500


def test_429_honors_retry_after(fake_conn):
    build, h = fake_conn
    c = make_client(build([("ok", 429, "slow", {"Retry-After": "2"}), ("ok", 200, OK, {})]))
    waited = []
    c.sleep = waited.append
    c.ask("a", Q)
    assert waited == [2.0]


def test_backoff_sequence(fake_conn):
    build, h = fake_conn
    c = make_client(build([("ok", 500, "x", {}), ("ok", 500, "x", {}), ("ok", 200, OK, {})]))
    waited = []
    c.sleep = waited.append
    c.ask("a", Q)
    assert waited == [0.5, 1.0]


def test_remote_disconnected_reconnects_once_not_counted(fake_conn):
    build, h = fake_conn
    c = make_client(build([("raise", RemoteDisconnected()), ("ok", 200, OK, {})]))
    c.ask("a", Q)
    assert h["conn"].closed == 1
    assert len(h["conn"].requests) == 2


def test_timeout_retries(fake_conn):
    build, h = fake_conn
    c = make_client(build([("raise", TimeoutError()), ("ok", 200, OK, {})]))
    c.ask("a", Q)
    assert len(h["conn"].requests) == 2


def test_bad_json(fake_conn):
    build, h = fake_conn
    c = make_client(build([("ok", 200, "not json", {})]))
    with pytest.raises(APIError):
        c.ask("a", Q)


def test_missing_answers(fake_conn):
    build, h = fake_conn
    c = make_client(build([("ok", 200, {"model": "x"}, {})]))
    with pytest.raises(APIError):
        c.ask("a", Q)
