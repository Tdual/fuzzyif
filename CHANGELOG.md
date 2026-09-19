# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `examples/ansible_distribution`: Ansible's distribution detection replaced by two `fuzzy_match` calls, scored with Ansible's own 90 fixtures.
- GitHub Actions: tests on 3.10-3.13, PyPI Trusted Publishing on `v*` tags.

### Fixed

- Request bodies are sent as UTF-8 bytes; non-latin-1 text no longer fails in `http.client`.

## [0.2.0] - 2026-09-19

First public release.

### Added

- `fuzzy(question, text, threshold=0.5)`: yes/no judgement for `if` statements.
- `prob(question, text)`: the raw probability behind `fuzzy`.
- `fuzzy_batch(text, questions)`: several yes/no questions in one request.
- `fuzzy_match(text, choices)`: pick one labelled option (Jev `choice`).
- `fuzzy_score(text, question, levels)`: rate on an ordered scale (Jev `score`).
- `configure(...)`: model, timeout, cache size, retries, base URL, API key.
- `mock(...)`: answer from a mapping in tests without touching the API.
- Keep-alive HTTPS connection per thread, retry with backoff on 429/5xx,
  `Retry-After` support, thread-safe LRU cache keyed by model.
- API key resolution: `configure(api_key=)`, `TYPESAFE_API_KEY`, or
  `~/.config/typesafe/api_key`.

[Unreleased]: https://github.com/Tdual/fuzzyif/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Tdual/fuzzyif/releases/tag/v0.2.0
