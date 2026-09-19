"""Side by side: Django's substring regex vs. one fuzzyif question, on setting/header names.

Run with a TypeSafe API key configured. Prints a markdown table.
"""
import re
from concurrent.futures import ThreadPoolExecutor

import fuzzyif

REGEX = re.compile("API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE", re.I)
QUESTION = (
    "Is this the name of a configuration setting, environment variable, HTTP header, "
    "or dictionary key whose VALUE is likely to be a secret or credential (password, API key, "
    "token, private key, signing secret, session cookie, connection string with credentials)? "
    "Judge by the name only. Names for usernames, logins, hosts, ports, paths, flags, and lists "
    "of apps are not secrets."
)

# (name, should it be redacted?) - "expected" is the security-minded human answer
NAMES = [
    ("SECRET_KEY", True), ("PASSWORD", True), ("api_key", True), ("HTTP_AUTHORIZATION", True),
    ("HTTP_COOKIE", True), ("EMAIL_HOST_PASSWORD", True),
    # the regex misses these
    ("DATABASE_URL", True), ("SENTRY_DSN", True), ("REDIS_URL", True), ("GITHUB_PAT", True),
    ("STRIPE_WEBHOOK_SECRET", True), ("SIGNED_COOKIE_LEGACY_SALT_FALLBACK", True),
    # the regex redacts these by accident
    ("MONKEY_MODE", False), ("PASSENGER_COUNT", False), ("TURKEY_SETTING", False),
    ("OAUTH_CLIENT_ID", False), ("API_URL", False),
    # plain settings
    ("DEBUG", False), ("ALLOWED_HOSTS", False), ("login", False), ("EMAIL_HOST_USER", False),
    ("REMOTE_ADDR", False), ("HTTP_USER_AGENT", False),
]


def main() -> None:
    with ThreadPoolExecutor(8) as ex:
        probs = list(ex.map(lambda n: fuzzyif.prob(QUESTION, n[0]), NAMES))
    print("| name | human | regex | fuzzy (p) |")
    print("|---|---|---|---|")
    rx_ok = fz_ok = 0
    for (name, want), p in zip(NAMES, probs):
        rx = bool(REGEX.search(name))
        fz = p >= 0.5
        rx_ok += rx == want
        fz_ok += fz == want
        mark = lambda b, w: ("redact" if b else "show") + ("" if b == w else " ✗")
        print(f"| `{name}` | {'redact' if want else 'show'} | {mark(rx, want)} | {mark(fz, want)} ({p:.2f}) |")
    print(f"\nregex agrees with human: {rx_ok}/{len(NAMES)}   fuzzy agrees with human: {fz_ok}/{len(NAMES)}")


if __name__ == "__main__":
    main()
