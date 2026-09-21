# Contributing to envguard

Thanks for helping out! envguard is small on purpose, so please keep changes focused.

## Setup

```bash
git clone https://github.com/shirishtiwari/envguard && cd envguard
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m unittest discover -s tests -t .
```

## Ground rules

- **No runtime dependencies.** envguard should install in a second and run anywhere Python 3.9+ runs.
- **Never print secret values.** Mask anything that could be a credential.
- **Low false positives.** New secret patterns must be specific (a real prefix or format), with a test.
- Add tests for every bug fix and feature.

## Adding a secret pattern

Add a `(name, regex)` pair to `PATTERNS` in `src/envguard/secrets.py` and a test in
`tests/test_secrets.py`. Build fake tokens by string concatenation so the repo doesn't flag itself.
