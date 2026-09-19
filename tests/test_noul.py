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
    def __init__(self, answers=None, exc=None):
        self.answers, self.exc, self.calls = answers, exc, []

    def ask(self, state, questions):
        self.calls.append((state, questions))
        if self.exc:
            raise self.exc
        return self.answers


def use(stub):
    eng.client_override = stub
    return stub


def test_prob_calls_api():
    stub = use(Stub({"q": {"noul": 0.8}}))
    assert fuzzyif.prob("urgent?", "server down") == 0.8
    assert stub.calls[0] == ("server down", {"q": {"type": "noul", "instructions": "urgent?"}})


def test_fuzzy_threshold_default_half():
    use(Stub({"q": {"noul": 0.5}}))
    assert fuzzyif.fuzzy("q", "t") is True
    use(Stub({"q": {"noul": 0.49}}))
    assert fuzzyif.fuzzy("q", "t2") is False


def test_fuzzy_threshold_override():
    use(Stub({"q": {"noul": 0.7}}))
    assert fuzzyif.fuzzy("q", "t", threshold=0.8) is False


def test_threshold_out_of_range():
    with pytest.raises(ValueError):
        fuzzyif.fuzzy("q", "t", threshold=1.5)
    with pytest.raises(ValueError):
        fuzzyif.fuzzy("q", "t", threshold=-0.1)


def test_empty_text_raises():
    with pytest.raises(ValueError):
        fuzzyif.prob("q", "")


def test_cache_hit_avoids_second_call():
    stub = use(Stub({"q": {"noul": 0.6}}))
    fuzzyif.prob("q", "t")
    fuzzyif.prob("q", "t")
    fuzzyif.fuzzy("q", "t", threshold=0.9)
    assert len(stub.calls) == 1


def test_api_error_propagates_by_default():
    use(Stub(exc=APIError("down")))
    with pytest.raises(APIError):
        fuzzyif.fuzzy("q", "t")


def test_fuzzy_default_on_error():
    use(Stub(exc=APIError("down")))
    assert fuzzyif.fuzzy("q", "t", default=False) is False


def test_prob_default_on_error():
    use(Stub(exc=APIError("down")))
    assert fuzzyif.prob("q", "t", default=0.0) == 0.0


def test_mock_bypasses_api_and_cache():
    stub = use(Stub({"q": {"noul": 0.6}}))
    with fuzzyif.mock({"q": 0.9}):
        assert fuzzyif.prob("q", "t") == 0.9
    assert stub.calls == []
    assert fuzzyif.prob("q", "t") == 0.6


def test_bad_response_shape():
    use(Stub({"q": {"noul": "nope"}}))
    with pytest.raises(APIError):
        fuzzyif.prob("q", "t")
