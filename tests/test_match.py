import pytest

import fuzzyif
from fuzzyif import _engine as eng
from fuzzyif.errors import APIError

CHOICES = {"bug": "a bug report", "howto": "a how-to question", "other": "anything else"}


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


def answer(choice, probs):
    return {"_match": {"choice": choice, "confidence": max(probs.values(), default=0), "probabilities": probs}}


def test_returns_choice():
    stub = eng.client_override = Stub(answer("bug", {"bug": 0.9, "howto": 0.1, "other": 0.0}))
    assert fuzzyif.fuzzy_match("blank screen after login", CHOICES) == "bug"
    q = stub.calls[0][1]["_match"]
    assert q["type"] == "choice" and q["criteria"] == CHOICES


def test_with_probs():
    eng.client_override = Stub(answer("bug", {"bug": 0.9, "howto": 0.1, "other": 0.0}))
    key, probs = fuzzyif.fuzzy_match("x", CHOICES, with_probs=True)
    assert key == "bug" and probs == {"bug": 0.9, "howto": 0.1, "other": 0.0}


def test_cached():
    stub = eng.client_override = Stub(answer("bug", {"bug": 1.0, "howto": 0.0, "other": 0.0}))
    fuzzyif.fuzzy_match("x", CHOICES)
    fuzzyif.fuzzy_match("x", CHOICES, with_probs=True)
    assert len(stub.calls) == 1


def test_requires_two_choices():
    with pytest.raises(ValueError):
        fuzzyif.fuzzy_match("x", {"only": "one"})


def test_default_must_be_a_choice():
    with pytest.raises(ValueError):
        fuzzyif.fuzzy_match("x", CHOICES, default="nope")


def test_default_on_error():
    eng.client_override = Boom()
    assert fuzzyif.fuzzy_match("x", CHOICES, default="other") == "other"
    assert fuzzyif.fuzzy_match("x", CHOICES, default="other", with_probs=True) == ("other", {})


def test_unknown_choice_in_response():
    eng.client_override = Stub(answer("zzz", {}))
    with pytest.raises(APIError):
        fuzzyif.fuzzy_match("x", CHOICES)


def test_mock_str():
    with fuzzyif.mock({"bug|howto|other": "howto"}):
        assert fuzzyif.fuzzy_match("x", CHOICES) == "howto"


def test_mock_callable_and_with_probs():
    with fuzzyif.mock({"bug|howto|other": lambda t: "bug" if "error" in t else "other"}):
        assert fuzzyif.fuzzy_match("an error", CHOICES) == "bug"
        assert fuzzyif.fuzzy_match("hello", CHOICES, with_probs=True) == ("other", {"bug": 0.0, "howto": 0.0, "other": 1.0})


def test_empty_text():
    with pytest.raises(ValueError):
        fuzzyif.fuzzy_match(" ", CHOICES)
