"""Replace Django's secret-name regex in SafeExceptionReporterFilter with a fuzzyif question.

Django decides which settings / headers / cookies to redact on the debug 500 page with

    hidden_settings = re.compile("API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE", re.I)

That substring match misses DATABASE_URL, SENTRY_DSN or GITHUB_PAT and redacts MONKEY_MODE,
PASSENGER_COUNT or OAUTH_CLIENT_ID. This script swaps it for one natural-language question.
Only the key *name* is sent to the judge, never the value.

Usage:
    python patch_django.py <path/to/django/repo>            # apply
    python patch_django.py <path/to/django/repo> --restore  # undo
"""
import shutil
import sys
from pathlib import Path

OLD_ATTR = '''    cleansed_substitute = "********************"
    hidden_settings = _lazy_re_compile(
        "API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE", flags=re.I
    )
'''

NEW_ATTR = '''    cleansed_substitute = "********************"
    # --- fuzzyif demo override ---
    # The regex "API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE" is replaced
    # by asking Jev whether the key *name* denotes a secret. Only the name is sent.
    sensitive_key_question = (
        "Is this the name of a configuration setting, environment variable, HTTP header, "
        "or dictionary key whose VALUE is likely to be a secret or credential (password, API key, "
        "token, private key, signing secret, session cookie, connection string with credentials)? "
        "Judge by the name only. Names for usernames, logins, hosts, ports, paths, flags, and lists "
        "of apps are not secrets."
    )

    def is_sensitive_key(self, key):
        from fuzzyif import fuzzy

        return isinstance(key, str) and bool(key.strip()) and fuzzy(self.sensitive_key_question, key)
'''

OLD_BODY = '''        if key == settings.SESSION_COOKIE_NAME:
            is_sensitive = True
        else:
            try:
                is_sensitive = self.hidden_settings.search(key)
            except TypeError:
                is_sensitive = False
'''

NEW_BODY = '''        if key == settings.SESSION_COOKIE_NAME:
            is_sensitive = True
        else:
            is_sensitive = self.is_sensitive_key(key)
'''


def main() -> None:
    repo = Path(sys.argv[1])
    target = repo / "django" / "views" / "debug.py"
    backup = target.with_suffix(".py.orig")
    if "--restore" in sys.argv:
        if backup.exists():
            shutil.move(backup, target)
            print("restored", target)
        return
    src = target.read_text(encoding="utf-8")
    if "fuzzyif demo override" in src:
        print("already patched")
        return
    if OLD_ATTR not in src or OLD_BODY not in src:
        sys.exit("debug.py does not look like the expected Django version; aborting")
    shutil.copy(target, backup)
    target.write_text(src.replace(OLD_ATTR, NEW_ATTR).replace(OLD_BODY, NEW_BODY), encoding="utf-8")
    print("patched", target)


if __name__ == "__main__":
    main()
