"""Several Yes/No questions about one text in a single request."""
from __future__ import annotations

from . import _engine as eng
from . import _mock
from .errors import APIError


def fuzzy_batch(text: str, questions: list[str], *, default: float | None = None) -> list[float]:
    """Probabilities for each question, in order. Cached questions are not re-sent."""
    eng.validate_text(text)
    if not questions:
        return []
    st = _mock.current()
    if st is not None:
        return [float(st.lookup(q, text)) for q in questions]

    cache = eng.cache()
    keys = [eng.cache_key("noul", q, text) for q in questions]
    result: list[float | None] = [cache.get(k) for k in keys]
    missing = {f"q{i}": i for i, p in enumerate(result) if p is None}
    if missing:
        try:
            answers = eng.client().ask(
                text, {name: {"type": "noul", "instructions": questions[i]} for name, i in missing.items()}
            )
            for name, i in missing.items():
                p = eng.as_float(answers[name].get("noul"), "noul")
                cache.put(keys[i], p)
                result[i] = p
        except APIError as e:
            d = eng.on_api_error(e, default)
            return [d] * len(questions)
    return result  # type: ignore[return-value]
