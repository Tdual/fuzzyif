"""Test double: answer questions from a mapping instead of the API."""
from __future__ import annotations

import contextlib
import threading
from typing import Any, Iterator

from .errors import MockMissError

_tls = threading.local()


class MockState:
    """Mapping from question key to a value, a {text: value} dict, or a callable(text)."""

    def __init__(self, mapping: dict[str, Any], default_prob: float | None) -> None:
        self.mapping = mapping
        self.default_prob = default_prob

    def lookup(self, key: str, text: str) -> Any:
        if key in self.mapping:
            v = self.mapping[key]
            if isinstance(v, dict):
                if text in v:
                    return v[text]
            elif callable(v):
                return v(text)
            else:
                return v
        if self.default_prob is not None:
            return self.default_prob
        raise MockMissError(f"mock has no value for key={key!r} text={text!r}")


def current() -> MockState | None:
    stack = getattr(_tls, "stack", None)
    return stack[-1] if stack else None


@contextlib.contextmanager
def mock(mapping: dict[str, Any] | None = None, *, default_prob: float | None = None) -> Iterator[MockState]:
    """Answer from `mapping` instead of calling the API. The cache is bypassed while active."""
    state = MockState(mapping or {}, default_prob)
    stack = getattr(_tls, "stack", None)
    if stack is None:
        stack = _tls.stack = []
    stack.append(state)
    try:
        yield state
    finally:
        stack.pop()
