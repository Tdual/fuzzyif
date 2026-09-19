import pytest

import fuzzyif
from fuzzyif import _engine as eng
from fuzzyif.errors import APIError

LEVELS = ["calm", "annoyed", "furious"]


@pytest.fixture(autouse=True)
def _reset():
    eng.reset_for_tests()
    eng.configure(api_key="k")
    yield
    eng.reset_for_tests()


class Stub:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def ask(self, state, questions):
        self.calls.append((state, questions))
        return self.answer


class Boom:
    def ask(self, *a):
        raise APIError("x")


def test_returns_expected_value():
    stub = eng.client_override = Stub({"_score": {"score": 1.7, "confidence": 0.8}})
    assert fuzzyif.fuzzy_score("worst service ever", "How angry is the customer?", LEVELS) == 1.7
    q = stub.calls[0][1]["_score"]
    assert q == {"type": "score", "instructions": "How angry is the customer?", "criteria": LEVELS}


def test_requires_two_levels():
    with pytest.raises(ValueError):
        fuzzyif.fuzzy_score("x", "q", ["one"])


def test_cached():
    stub = eng.client_override = Stub({"_score": {"score": 1.0}})
    fuzzyif.fuzzy_score("x", "q", LEVELS)
    fuzzyif.fuzzy_score("x", "q", LEVELS)
    assert len(stub.calls) == 1


def test_default_on_error():
    eng.client_override = Boom()
    assert fuzzyif.fuzzy_score("x", "q", LEVELS, default=0.0) == 0.0


def test_mock():
    with fuzzyif.mock({"q": 2.0}):
        assert fuzzyif.fuzzy_score("x", "q", LEVELS) == 2.0


def test_bad_response():
    eng.client_override = Stub({"_score": {"score": None}})
    with pytest.raises(APIError):
        fuzzyif.fuzzy_score("x", "q", LEVELS)
