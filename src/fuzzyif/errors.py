"""Exception types raised by fuzzyif."""
from __future__ import annotations


class FuzzyIfError(Exception):
    """Base class for every fuzzyif exception."""


class ConfigError(FuzzyIfError):
    """Configuration problem, such as a missing API key."""


class APIError(FuzzyIfError):
    """The Jev API call failed after retries."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
        attempts: int = 1,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.attempts = attempts


class MockMissError(FuzzyIfError):
    """A question was asked inside mock() that the mapping does not cover."""
