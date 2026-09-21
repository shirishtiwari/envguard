# envguard

[![PyPI](https://img.shields.io/pypi/v/envguard-cli)](https://pypi.org/project/envguard-cli/)
[![Python](https://img.shields.io/pypi/pyversions/envguard-cli)](https://pypi.org/project/envguard-cli/)
[![CI](https://github.com/shirishtiwari/envguard/actions/workflows/ci.yml/badge.svg)](https://github.com/shirishtiwari/envguard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Keep your `.env` files honest.** envguard checks your `.env` against `.env.example`, catches missing or malformed config before your app crashes at 2am, and stops secrets from sneaking into git.

- Zero dependencies — pure Python 3.9+, installs in a second
- Works with any stack (Node, Python, Go, Ruby, Docker…) — it only reads `.env` files
- CI-friendly exit codes and `--json` output
- Never prints your secret values

```text
$ envguard
error   .env:1  APP_ENV: must be one of development, staging, production; got 'prod'
error   .env:2  PORT: expected a port number (1-65535), got '80800'
error   .env:3  DATABASE_URL: expected a URL like https://example.com, got 'localhost:5432'
error   .env:6  STRIPE_SECRET_KEY: does not match pattern /^sk_(test|live)_/
warning .env:6  STRIPE_SECRET_KEY still looks like a placeholder ('changeme')
warning .env:7  LEGACY_FLAG is not declared in the example file

4 error(s), 2 warning(s)
```

## Install

```bash
pipx install envguard-cli    # recommended
# or
pip install envguard-cli
```

The package is called `envguard-cli` on PyPI; the command it installs is `envguard`.

## Quick start

```bash
envguard init       # create .env.example from your .env (values cleared, types inferred)
envguard            # check .env against .env.example
envguard sync       # add any keys a teammate added to .env.example into your .env
envguard scan       # find committed .env files and hard-coded secrets
```

## Describe your config in `.env.example`

Your `.env.example` is the schema. Add annotations in comments above each key — it stays a normal, readable dotenv file.

```dotenv
# Which environment the app runs in
# @type enum @choices development,staging,production
APP_ENV=development

# @type port
PORT=3000

# @type url
DATABASE_URL=postgres://localhost:5432/myapp

# @type int @min 1 @max 64
WORKERS=4

# @secret
# @pattern ^sk_(test|live)_
STRIPE_SECRET_KEY=

# @optional @type url
SENTRY_DSN=
```

| Annotation | Meaning |
|---|---|
| `@type T` | `str` (default), `int`, `float`, `bool`, `url`, `email`, `port`, `json`, `enum` |
| `@choices a,b,c` | value must be one of these (implies `enum`) |
| `@pattern REGEX` | value must match the regex |
| `@min N` / `@max N` | numeric bounds for `int`, `float`, `port` |
| `@optional` | key may be missing (still validated when set) |
| `@allow_empty` | required, but an empty value is fine |
| `@secret` | never echo this value in messages |

Every key in the example is **required** unless marked `@optional`.

## Commands

### `envguard check` (default)

| Flag | |
|---|---|
| `-e, --env FILE` | env file to check, repeatable (default `.env`) |
| `-x, --example FILE` | example/schema file (default `.env.example`) |
| `--strict` | keys not in the example are errors, not warnings |
| `--json` | machine-readable output |
| `--fail-on-warning` | exit 1 on warnings too |
| `-q, --quiet` | only print errors |

It reports missing keys, empty values, wrong types, values outside `@choices`/`@min`/`@max`/`@pattern`, leftover placeholders (`changeme`, `<your-key>`, `TODO`…), undeclared keys and duplicates.

### `envguard scan [paths…]`

Inside a git repo it scans everything git would commit and flags:

- real env files (`.env`, `.env.local`, `prod.env`…) that aren't gitignored
- real-looking secrets pasted into `.env.example`
- hard-coded AWS, GitHub, GitLab, Slack, Stripe live, Google, OpenAI and Anthropic keys, private keys and connection strings with passwords

Silence a false positive with an `envguard:ignore` comment on that line, or skip paths with `--exclude "tests/*"`.

### `envguard init`

Generates `.env.example` from `.env`. Values are cleared by default; `--keep-values` keeps non-secret ones as defaults. `@type` annotations are inferred for you.

### `envguard sync`

Appends keys that exist in `.env.example` but not in your `.env`, using the example's defaults (secret-looking keys are left blank). Use `--dry-run` to preview.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | all good (warnings allowed unless `--fail-on-warning`) |
| `1` | problems found |
| `2` | usage error — file not found or unparseable |

## Use it in CI

**GitHub Actions**

```yaml
- run: pipx install envguard-cli
- run: envguard check -e .env.ci --strict
- run: envguard scan
```

**pre-commit**

```yaml
repos:
  - repo: https://github.com/shirishtiwari/envguard
    rev: v0.1.0
    hooks:
      - id: envguard-scan
      - id: envguard-check
```

## Roadmap

- [x] Publish to PyPI
- [ ] Homebrew formula
- [ ] `envguard diff .env.staging .env.production`
- [ ] Config file support (`pyproject.toml` / `envguard.toml`)
- [ ] More secret patterns (Azure, Twilio, SendGrid…)
- [ ] Load-time library API: `envguard.load()` returns typed values

## Contributing

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
