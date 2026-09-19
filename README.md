# fuzzyif

Natural-language conditions in Python `if` statements, judged by [Jev](https://docs.typesafe.ai), TypeSafe AI's System One model. Jev does not generate text; it returns probabilities and choices, so calls are fast and cheap.

```python
from fuzzyif import fuzzy, fuzzy_match

msg = "After I enter my password the screen goes blank."

if fuzzy("Is this message urgent?", msg):
    notify_oncall(msg)

kind = fuzzy_match(msg, {
    "bug":   "a bug report",
    "howto": "a how-to question",
    "other": "anything else",
})
```

## Install

```bash
pip install -e .
```

No runtime dependencies; standard library only. Python 3.10+.

## API key

Resolved in this order:

1. `fuzzyif.configure(api_key="...")`
2. Environment variable `TYPESAFE_API_KEY`
3. File `~/.config/typesafe/api_key`

## Functions

| Function | Question type | Returns |
|---|---|---|
| `fuzzy(question, text, threshold=0.5)` | yes/no | `bool` |
| `prob(question, text)` | yes/no | `float` in 0..1 |
| `fuzzy_batch(text, [q1, q2, ...])` | several yes/no in one request | `list[float]` |
| `fuzzy_match(text, {key: description})` | pick one | chosen `key` (or `(key, probs)` with `with_probs=True`) |
| `fuzzy_score(text, question, [level0, level1, ...])` | ordered scale | expected index as `float` |

### fuzzy vs fuzzy_match

`fuzzy()` answers each question independently. Stacking several `fuzzy()` calls in `if / elif` is not exclusive: when two questions both cross the threshold, the first branch wins even if the second is more likely. When you want exactly one of several labels, use `fuzzy_match()`; it compares all options in one request.

### Errors

API failures raise `APIError` by default. Pass `default=` to return a fallback instead:

```python
if fuzzy("Is this spam?", msg, default=False):
    ...
```

Be careful with negations: `if not fuzzy(..., default=False)` lets everything through during an outage.

Empty text and out-of-range thresholds raise `ValueError`.

### Testing

`mock()` answers from a mapping instead of the API. Values can be a number, a `{text: value}` dict, or a callable.

```python
import fuzzyif

with fuzzyif.mock({
    "Is this message urgent?": {"server down": 0.95, "team dinner": 0.1},
    "bug|howto|other": lambda t: "bug" if "error" in t else "other",
}):
    ...
```

The mock key for `fuzzy_match` is the sorted choice keys joined with `|`.

## Performance

- One keep-alive HTTPS connection per thread.
- LRU cache in front of every call (`cache_size`, default 1024). The same question and text never hit the API twice.
- `fuzzy_batch` and `fuzzy_match` send one request for several judgements.
- Retries with backoff on 429 and 5xx (`max_retries`, default 3); `Retry-After` is honoured.

## Configuration

```python
fuzzyif.configure(model="jev-latest", timeout=10.0, cache_size=1024, max_retries=3)
```

`configure()` clears the cache.
