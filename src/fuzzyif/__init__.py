"""fuzzyif: natural-language conditions for Python if statements."""
from ._engine import configure
from .batch import fuzzy_batch
from .errors import APIError, ConfigError, FuzzyIfError, MockMissError
from .match import fuzzy_match
from ._mock import mock
from .noul import fuzzy, prob
from .score import fuzzy_score

__version__ = "0.2.0"
__all__ = [
    "fuzzy", "prob", "fuzzy_batch", "fuzzy_match", "fuzzy_score", "configure", "mock",
    "FuzzyIfError", "ConfigError", "APIError", "MockMissError",
]
