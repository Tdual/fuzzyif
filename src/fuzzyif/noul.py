"""Yes/No questions: prob() returns the probability, fuzzy() applies a threshold."""
from __future__ import annotations

from . import _engine as eng
from . import _mock
from .errors import APIError


def prob(question: str, text: str, *, default: float | None = None) -> float:
    """Probability (0..1) that `text` answers `question` with yes."""
    eng.validate_text(text)
    st = _mock.current()
    if st is not None:
        return float(st.lookup(question, text))
    cache = eng.cache()
    key = eng.cache_key("noul", question, text)
    hit = cache.get(key)
    if hit is not None:
        return hit
    try:
        answers = eng.client().ask(text, {"q": {"type": "noul", "instructions": question}})
        p = eng.as_float(answers["q"].get("noul"), "noul")
    except APIError as e:
        return eng.on_api_error(e, default)
    cache.put(key, p)
    return p


def fuzzy(question: str, text: str, *, threshold: float = 0.5, default: bool | None = None) -> bool:
    """Use inside an if statement: True when prob(question, text) >= threshold."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0.0 and 1.0")
    try:
        return prob(question, text) >= threshold
    except APIError as e:
        return eng.on_api_error(e, default)
