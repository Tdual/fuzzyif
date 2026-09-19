import pytest

from fuzzyif import _mock as m
from fuzzyif.errors import MockMissError


def test_inactive_by_default():
    assert m.current() is None


def test_float_value():
    with m.mock({"q": 0.9}):
        assert m.current().lookup("q", "anything") == 0.9
    assert m.current() is None


def test_dict_value():
    with m.mock({"q": {"a": 0.1, "b": 0.8}}):
        assert m.current().lookup("q", "a") == 0.1
        assert m.current().lookup("q", "b") == 0.8


def test_dict_miss_falls_to_default():
    with m.mock({"q": {"a": 0.1}}, default_prob=0.3):
        assert m.current().lookup("q", "zzz") == 0.3


def test_dict_miss_raises():
    with m.mock({"q": {"a": 0.1}}):
        with pytest.raises(MockMissError):
            m.current().lookup("q", "zzz")


def test_callable_value():
    with m.mock({"q": lambda t: 0.99 if "x" in t else 0.01}):
        assert m.current().lookup("q", "x!") == 0.99
        assert m.current().lookup("q", "y") == 0.01


def test_unknown_key_raises():
    with m.mock({"q": 0.5}):
        with pytest.raises(MockMissError):
            m.current().lookup("other", "t")


def test_unknown_key_default():
    with m.mock({}, default_prob=0.42):
        assert m.current().lookup("other", "t") == 0.42


def test_nested_restores_outer():
    with m.mock({"q": 0.1}):
        with m.mock({"q": 0.2}):
            assert m.current().lookup("q", "") == 0.2
        assert m.current().lookup("q", "") == 0.1
