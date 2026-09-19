import pytest

import fuzzyif
from fuzzyif import _engine as eng
from fuzzyif.errors import APIError


@pytest.fixture(autouse=True)
def _reset():
    eng.reset_for_tests()
    eng.configure(api_key="k")
    yield
    eng.reset_for_tests()


class Stub:
    def __init__(self, table):
        self.table, self.calls = table, []

    def ask(self, state, questions):
        self.calls.append((state, questions))
        return {n: {"noul": self.table[q["instructions"]]} for n, q in questions.items()}


class Boom:
    def ask(self, *a):
        raise APIError("x")


def test_single_request():
    stub = eng.client_override = Stub({"a": 0.1, "b": 0.9})
    assert fuzzyif.fuzzy_batch("t", ["a", "b"]) == [0.1, 0.9]
    assert len(stub.calls) == 1 and len(stub.calls[0][1]) == 2


def test_partial_cache():
    stub = eng.client_override = Stub({"a": 0.1, "b": 0.9, "c": 0.5})
    fuzzyif.prob("a", "t")
    assert fuzzyif.fuzzy_batch("t", ["a", "b", "c"]) == [0.1, 0.9, 0.5]
    assert len(stub.calls) == 2
    assert {q["instructions"] for q in stub.calls[1][1].values()} == {"b", "c"}


def test_all_cached_no_call():
    stub = eng.client_override = Stub({"a": 0.1})
    fuzzyif.prob("a", "t")
    assert fuzzyif.fuzzy_batch("t", ["a"]) == [0.1]
    assert len(stub.calls) == 1


def test_populates_cache_for_prob():
    stub = eng.client_override = Stub({"a": 0.1, "b": 0.9})
    fuzzyif.fuzzy_batch("t", ["a", "b"])
    assert fuzzyif.prob("b", "t") == 0.9
    assert len(stub.calls) == 1


def test_default_on_error():
    eng.client_override = Boom()
    assert fuzzyif.fuzzy_batch("t", ["a", "b"], default=0.0) == [0.0, 0.0]


def test_error_propagates():
    eng.client_override = Boom()
    with pytest.raises(APIError):
        fuzzyif.fuzzy_batch("t", ["a"])


def test_empty_questions():
    eng.client_override = Stub({})
    assert fuzzyif.fuzzy_batch("t", []) == []


def test_mock():
    with fuzzyif.mock({"a": 0.2, "b": 0.7}):
        assert fuzzyif.fuzzy_batch("t", ["a", "b"]) == [0.2, 0.7]


def test_empty_text():
    with pytest.raises(ValueError):
        fuzzyif.fuzzy_batch("", ["a"])
