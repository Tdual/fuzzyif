"""Pick one of several labelled choices for a text (Jev choice question)."""
from __future__ import annotations

import json

from . import _engine as eng
from . import _mock
from .errors import APIError

MATCH_INSTRUCTIONS = "Which of the following options best describes this text?"


def mock_key(choices: dict[str, str]) -> str:
    return "|".join(sorted(choices))


def fuzzy_match(
    text: str,
    choices: dict[str, str],
    *,
    default: str | None = None,
    with_probs: bool = False,
) -> str | tuple[str, dict[str, float]]:
    """Return the key from `choices` (key -> description) that best fits `text`."""
    eng.validate_text(text)
    if len(choices) < 2:
        raise ValueError("choices needs at least two entries")
    if default is not None and default not in choices:
        raise ValueError(f"default={default!r} is not one of the choices")

    st = _mock.current()
    if st is not None:
        chosen = st.lookup(mock_key(choices), text)
        if chosen not in choices:
            raise ValueError(f"mock value {chosen!r} is not one of the choices")
        return (chosen, {k: float(k == chosen) for k in choices}) if with_probs else chosen

    cache = eng.cache()
    key = eng.cache_key("choice", json.dumps(choices, ensure_ascii=False, sort_keys=True), text)
    hit = cache.get(key)
    if hit is None:
        try:
            answers = eng.client().ask(
                text, {"_match": {"type": "choice", "instructions": MATCH_INSTRUCTIONS, "criteria": choices}}
            )
            a = answers["_match"]
            chosen = a.get("choice")
            if chosen not in choices:
                raise APIError(f"Jev API returned choice={chosen!r}, not one of the choices")
            raw = a.get("probabilities") or {}
            probs = {k: eng.as_float(raw.get(k, 0.0), "probabilities") for k in choices}
        except APIError as e:
            d = eng.on_api_error(e, default)
            return (d, {}) if with_probs else d
        hit = (chosen, probs)
        cache.put(key, hit)
    chosen, probs = hit
    return (chosen, dict(probs)) if with_probs else chosen
