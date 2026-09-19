"""Hits the real Jev API. Skipped unless a key is available."""
import os
import time
from pathlib import Path

import pytest

import fuzzyif
from fuzzyif import _engine as eng

_HAS_KEY = bool(os.environ.get("TYPESAFE_API_KEY")) or Path.home().joinpath(".config/typesafe/api_key").is_file()
pytestmark = pytest.mark.skipif(not _HAS_KEY, reason="no API key")


@pytest.fixture(autouse=True)
def _real():
    eng.reset_for_tests()
    eng.configure()
    yield
    eng.reset_for_tests()


def test_fuzzy_urgent():
    assert fuzzyif.fuzzy("Is this message urgent?", "The server is down. Please fix it immediately.")
    assert not fuzzyif.fuzzy("Is this message urgent?", "Let's pick a venue for next month's team dinner.")


def test_match_support_ticket():
    kind = fuzzyif.fuzzy_match(
        "After I enter my password the screen goes blank.",
        {"bug": "a bug report", "howto": "a how-to question", "billing": "a billing question"},
    )
    assert kind == "bug"


def test_batch_and_score():
    text = "I have asked three times and nobody answers. What is going on?"
    p = fuzzyif.fuzzy_batch(text, ["Is the writer angry?", "Is the writer grateful?"])
    assert p[0] > p[1]
    s = fuzzyif.fuzzy_score(text, "How angry is the writer?", ["calm", "annoyed", "furious"])
    assert 1.0 <= s <= 2.0


def test_keep_alive_is_faster_than_cold():
    """Second call reuses the connection: it must not be slower than the first by more than noise."""
    t0 = time.perf_counter()
    fuzzyif.prob("Is this a question?", "What time is it?")
    cold = time.perf_counter() - t0
    t0 = time.perf_counter()
    fuzzyif.prob("Is this a question?", "It is noon.")
    warm = time.perf_counter() - t0
    print(f"\ncold={cold:.3f}s warm={warm:.3f}s")
    assert warm <= cold * 1.2


def test_cache_hit_is_instant():
    fuzzyif.prob("Is this a greeting?", "Hello there")
    t0 = time.perf_counter()
    for _ in range(1000):
        fuzzyif.prob("Is this a greeting?", "Hello there")
    assert time.perf_counter() - t0 < 0.05
