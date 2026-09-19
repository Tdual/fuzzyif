# Django's debug page: which settings are secrets?

When `DEBUG = True` and a view raises, Django renders a 500 page that lists every
setting, request header and cookie. `SafeExceptionReporterFilter` decides which
values to redact. The decision is a substring regex on the *name*:

```python
hidden_settings = re.compile("API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE", re.I)
```

A substring match cannot know that `DATABASE_URL` embeds a password, or that
`MONKEY_MODE` is not a key. This example replaces the regex with one question
to Jev, asked through fuzzyif. **Only the name is sent to the judge, never the
value.**

## The change

`django/views/debug.py`, class `SafeExceptionReporterFilter`:

```python
sensitive_key_question = (
    "Is this the name of a configuration setting, environment variable, HTTP header, "
    "or dictionary key whose VALUE is likely to be a secret or credential (password, API key, "
    "token, private key, signing secret, session cookie, connection string with credentials)? "
    "Judge by the name only. Names for usernames, logins, hosts, ports, paths, flags, and lists "
    "of apps are not secrets."
)

def is_sensitive_key(self, key):
    return isinstance(key, str) and bool(key.strip()) and fuzzy(self.sensitive_key_question, key)
```

and in `cleanse_setting`, `self.hidden_settings.search(key)` becomes
`self.is_sensitive_key(key)`. `patch_django.py` applies and reverts the edit.

## Regex vs. fuzzy on real-world names

`compare.py` output. "human" is the security-minded answer.

| name | human | regex | fuzzy (p) |
|---|---|---|---|
| `SECRET_KEY` | redact | redact | redact (0.98) |
| `PASSWORD` | redact | redact | redact (0.97) |
| `api_key` | redact | redact | redact (0.98) |
| `HTTP_AUTHORIZATION` | redact | redact | redact (0.96) |
| `HTTP_COOKIE` | redact | redact | redact (0.87) |
| `EMAIL_HOST_PASSWORD` | redact | redact | redact (0.98) |
| `DATABASE_URL` | redact | show ✗ | redact (0.92) |
| `SENTRY_DSN` | redact | show ✗ | redact (0.89) |
| `REDIS_URL` | redact | show ✗ | redact (0.77) |
| `GITHUB_PAT` | redact | show ✗ | redact (0.98) |
| `STRIPE_WEBHOOK_SECRET` | redact | redact | redact (0.99) |
| `SIGNED_COOKIE_LEGACY_SALT_FALLBACK` | redact | show ✗ | redact (0.80) |
| `MONKEY_MODE` | show | redact ✗ | show (0.09) |
| `PASSENGER_COUNT` | show | redact ✗ | show (0.02) |
| `TURKEY_SETTING` | show | redact ✗ | show (0.14) |
| `OAUTH_CLIENT_ID` | show | redact ✗ | show (0.19) |
| `API_URL` | show | redact ✗ | show (0.14) |
| `DEBUG` | show | show | show (0.04) |
| `ALLOWED_HOSTS` | show | show | show (0.03) |
| `login` | show | show | show (0.07) |
| `EMAIL_HOST_USER` | show | show | show (0.23) |
| `REMOTE_ADDR` | show | show | show (0.04) |
| `HTTP_USER_AGENT` | show | show | show (0.02) |

Regex agrees with the human answer on 13 of 23 names. Fuzzy agrees on 23 of 23.

## Django's own tests

Run against Django `main` (6.2.dev, 2026-09-18) with the patch applied:

```
tests/runtests.py view_tests.tests.test_debug.ExceptionReporterFilterTests \
    view_tests.tests.test_debug.NonHTMLResponseExceptionReporterFilter \
    view_tests.tests.test_debug.CustomExceptionReporterFilterTests
```

| | before | after |
|---|---|---|
| tests (3 filter classes) | 36 | 36 |
| passed | 36 | 35 |
| failed | 0 | 1 |

The whole `view_tests.tests.test_debug` module (110 tests, every debug-page
rendering path) shows the same single failure: 109 passed, 1 failed, 72 seconds.

The single failure is `test_request_meta_filtering` on the header `API_URL`.
Django's test asserts that anything containing `API` is redacted, so an API
*endpoint URL* must be hidden. Jev says an endpoint URL is not a credential
(p = 0.14). The disagreement is with the regex's over-approximation that the
test encodes, not with the intent of the feature. Whether `API_URL` deserves
redaction is a judgement call; the fuzzy version makes that judgement explicit
and adjustable by editing one sentence.

Every other assertion passes, including the ones the regex was written for
(`SECRET_KEY`, `PASSWORD`, `API_KEY`, `SOME_TOKEN`, `MY_AUTH`, nested dicts and
lists, session cookie, `secret-header`) and the subclass override test that
expects `database_url` to be redacted.

## Cost and speed

The first render of a 500 page asks about every setting and header name once
(around 200 names). With fuzzyif's keep-alive connection that takes a few
seconds; every later request is served from the LRU cache. The whole 36-test
run above took 70 seconds, almost all of it first-time judgements.

## Reproduce

```bash
git clone --depth 1 https://github.com/django/django
cd django && python -m venv .venv && .venv/bin/pip install -e . fuzzyif
python /path/to/fuzzyif/examples/django_cleanse_setting/patch_django.py .
cd tests && ../.venv/bin/python runtests.py view_tests.tests.test_debug.ExceptionReporterFilterTests --parallel 1
python /path/to/fuzzyif/examples/django_cleanse_setting/patch_django.py . --restore
```
