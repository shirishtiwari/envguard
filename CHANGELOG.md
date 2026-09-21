# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-09-21

First public release.

### Added
- `envguard check`: validates `.env` against `.env.example`. It catches missing, empty, wrongly typed and placeholder values, plus undeclared and duplicate keys.
- A schema written as annotations in `.env.example`: `@type`, `@choices`, `@pattern`, `@min`, `@max`, `@optional`, `@allow_empty`, `@secret`.
- `envguard scan`: finds `.env` files that aren't gitignored, real-looking secrets in example files, and hard-coded AWS, GitHub, GitLab, Slack, Stripe, Google, OpenAI and Anthropic keys, private keys and connection strings.
- `envguard init`: generates `.env.example` from `.env`, with types inferred.
- `envguard sync`: appends keys that are missing from `.env`.
- `--json` output, exit codes for CI, and pre-commit hooks.

[0.1.0]: https://github.com/shirishtiwari/envguard/releases/tag/v0.1.0
