"""Rate a text on an ordered scale (Jev score question)."""
from __future__ import annotations

import json

from . import _engine as eng
from . import _mock
from .errors import APIError


def fuzzy_score(text: str, question: str, levels: list[str], *, default: float | None = None) -> float:
    """Expected level index (0 = first level) for `question` about `text`."""
    eng.validate_text(text)
    if len(levels) < 2:
        raise ValueError("levels needs at least two entries")
    st = _mock.current()
    if st is not None:
        return float(st.lookup(question, text))
    cache = eng.cache()
    key = eng.cache_key("score", json.dumps([question, levels], ensure_ascii=False), text)
    hit = cache.get(key)
    if hit is not None:
        return hit
    try:
        answers = eng.client().ask(text, {"_score": {"type": "score", "instructions": question, "criteria": levels}})
        s = eng.as_float(answers["_score"].get("score"), "score")
    except APIError as e:
        return eng.on_api_error(e, default)
    cache.put(key, s)
    return s
