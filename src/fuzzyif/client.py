"""Jev API client with keep-alive and retry."""
from __future__ import annotations

import http.client
import json
import logging
import ssl
import threading
import time
from typing import Any, Callable
from urllib.parse import urlparse

from .config import Settings, resolve_api_key
from .errors import APIError

log = logging.getLogger("fuzzyif")

_PATH = "/v1/systemone"
_RECONNECT = (http.client.BadStatusLine, http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError)
_RETRY = (TimeoutError, ConnectionRefusedError, OSError)
_BACKOFF = (0.5, 1.0, 2.0)


def _default_factory(host: str, timeout: float) -> http.client.HTTPSConnection:
    return http.client.HTTPSConnection(host, timeout=timeout, context=ssl.create_default_context())


class JevClient:
    """One keep-alive HTTPS connection per thread; retries on 429/5xx/network errors."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.host = urlparse(settings.base_url).netloc
        self._headers = {
            "Authorization": f"Bearer {resolve_api_key(settings.api_key)}",
            "Content-Type": "application/json",
        }
        self.connection_factory: Callable[[str, float], Any] = _default_factory
        self.sleep: Callable[[float], None] = time.sleep
        self._local = threading.local()

    # connection lifecycle

    def _conn(self) -> Any:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self.connection_factory(self.host, self.settings.timeout)
            self._local.conn = conn
        return conn

    def _drop(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 - closing is best effort
                pass
            self._local.conn = None

    # one round trip

    def _send(self, body: str) -> tuple[int, str, str | None]:
        conn = self._conn()
        conn.request("POST", _PATH, body=body, headers=self._headers)
        resp = conn.getresponse()
        data = resp.read().decode("utf-8", errors="replace")
        return resp.status, data, resp.getheader("Retry-After")

    def _send_reconnecting(self, body: str) -> tuple[int, str, str | None]:
        try:
            return self._send(body)
        except _RECONNECT:
            log.debug("fuzzyif: connection dropped, reconnecting once")
            self._drop()
            return self._send(body)

    # public

    def ask(self, state: str, questions: dict[str, dict]) -> dict[str, dict]:
        """POST the questions about `state` and return Jev's `answers` dict."""
        body = json.dumps({"state": state, "model": self.settings.model, "questions": questions}, ensure_ascii=False)
        max_attempts = max(1, self.settings.max_retries)
        attempts = 0
        while True:
            attempts += 1
            try:
                status, data, retry_after = self._send_reconnecting(body)
            except _RETRY as e:
                if attempts >= max_attempts:
                    raise APIError(f"Jev API unreachable: {e!r}", body=repr(e), attempts=attempts) from e
                self._backoff(attempts, None)
                continue
            if status == 200:
                return self._parse(data, questions, attempts)
            if status == 429 or status >= 500:
                if attempts >= max_attempts:
                    raise APIError(f"Jev API error {status}", status_code=status, body=data, attempts=attempts)
                self._backoff(attempts, retry_after)
                continue
            raise APIError(f"Jev API error {status}", status_code=status, body=data, attempts=attempts)

    def _backoff(self, attempts: int, retry_after: str | None) -> None:
        if retry_after:
            try:
                self.sleep(float(retry_after))
                return
            except ValueError:
                pass
        self.sleep(_BACKOFF[min(attempts - 1, len(_BACKOFF) - 1)])

    @staticmethod
    def _parse(data: str, questions: dict, attempts: int) -> dict[str, dict]:
        try:
            obj = json.loads(data)
        except json.JSONDecodeError as e:
            raise APIError("Jev API response is not JSON", body=data, attempts=attempts) from e
        answers = obj.get("answers") if isinstance(obj, dict) else None
        if not isinstance(answers, dict):
            raise APIError("Jev API response has no 'answers'", body=data, attempts=attempts)
        missing = [n for n in questions if n not in answers]
        if missing:
            raise APIError(f"Jev API response lacks answers for {missing}", body=data, attempts=attempts)
        return answers
