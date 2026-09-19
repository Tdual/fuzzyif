from fuzzyif.errors import APIError, ConfigError, FuzzyIfError, MockMissError


def test_hierarchy():
    assert issubclass(ConfigError, FuzzyIfError)
    assert issubclass(APIError, FuzzyIfError)
    assert issubclass(MockMissError, FuzzyIfError)
    assert issubclass(FuzzyIfError, Exception)


def test_api_error_attributes():
    e = APIError("boom", status_code=503, body='{"x":1}', attempts=3)
    assert e.status_code == 503
    assert e.body == '{"x":1}'
    assert e.attempts == 3
    assert "boom" in str(e)


def test_api_error_defaults():
    e = APIError("x")
    assert e.status_code is None
    assert e.body is None
    assert e.attempts == 1
