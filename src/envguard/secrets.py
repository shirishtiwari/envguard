"""Find secrets that are about to be (or already are) committed."""

from __future__ import annotations

import fnmatch
import math
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional

from .checker import ERROR, WARNING, Issue
from .parser import ParseError, parse_file

IGNORE_MARKER = "envguard:ignore"
MAX_FILE_BYTES = 1_000_000
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
             ".tox", ".mypy_cache", ".pytest_cache", ".next", "target", "vendor"}
EXAMPLE_SUFFIXES = (".example", ".sample", ".template", ".dist", ".defaults")

# (name, regex). Kept deliberately specific to avoid noisy false positives.
PATTERNS = [
    ("AWS access key ID", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b")),
    ("GitLab token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b")),
    ("Stripe live key", re.compile(r"\b(sk|rk)_live_[A-Za-z0-9]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("OpenAI API key", re.compile(r"\bsk-(proj-)?[A-Za-z0-9_\-]{32,}\b")),
    ("Private key", re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY( BLOCK)?-----")),
    ("Connection string with password", re.compile(r"\b[a-z][a-z0-9+]*://[^\s:/@]+:[^\s:/@]{6,}@[^\s]+", re.I)),
]

SECRET_KEY_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|PASSWD|PWD|API_?KEY|PRIVATE|CREDENTIAL|AUTH)", re.I)


def is_env_file(name: str) -> bool:
    """True for real env files like .env, .env.local, prod.env; False for examples."""
    n = name.lower()
    if n.endswith(EXAMPLE_SUFFIXES):
        return False
    return n == ".env" or n.startswith(".env.") or n.endswith(".env")


def is_example_env_file(name: str) -> bool:
    n = name.lower()
    return (n.startswith(".env") or n.endswith(".env") or ".env." in n) and n.endswith(EXAMPLE_SUFFIXES)


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {c: s.count(c) for c in set(s)}
    return -sum((n / len(s)) * math.log2(n / len(s)) for n in counts.values())


def looks_like_real_secret(value: str) -> bool:
    v = value.strip()
    return len(v) >= 16 and " " not in v and shannon_entropy(v) >= 3.5


def git_tracked_files(root: Path) -> Optional[List[Path]]:
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             cwd=root, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return [root / p for p in out.stdout.decode("utf-8", "replace").split("\0") if p]


def walk_files(root: Path) -> List[Path]:
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        files.extend(Path(dirpath) / f for f in filenames)
    return files


def _mask(s: str) -> str:
    return s[:4] + "…" + s[-2:] if len(s) > 8 else "****"


def _scan_text(path: Path, rel: str) -> List[Issue]:
    issues = []
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return issues
        data = path.read_bytes()
    except OSError:
        return issues
    if b"\0" in data[:8192]:
        return issues  # binary
    text = data.decode("utf-8", "replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        if IGNORE_MARKER in line:
            continue
        for name, rx in PATTERNS:
            m = rx.search(line)
            if m:
                issues.append(Issue(ERROR, "secret", None,
                                    f"possible {name} ({_mask(m.group(0))})", rel, lineno))
                break
    return issues


def scan(root: Path, paths: Optional[Iterable[Path]] = None,
         exclude: Iterable[str] = ()) -> List[Issue]:
    """Scan files for committed env files and hard-coded secrets.

    If ``paths`` is None and ``root`` is a git repository, scans files git
    would commit (tracked + untracked-but-not-ignored). Otherwise walks ``root``.
    ``exclude`` is a list of glob patterns matched against root-relative paths.
    """
    root = root.resolve()
    in_git = False
    explicit = paths is not None  # e.g. files handed over by a pre-commit hook
    if paths is None:
        tracked = git_tracked_files(root)
        in_git = tracked is not None
        paths = tracked if in_git else walk_files(root)

    issues: List[Issue] = []
    for p in paths:
        p = Path(p)
        if not p.is_file() or any(part in SKIP_DIRS for part in p.parts):
            continue
        try:
            rel = p.resolve().relative_to(root).as_posix()
        except ValueError:
            rel = p.as_posix()
        if any(fnmatch.fnmatch(rel, pat) for pat in exclude):
            continue

        if is_env_file(p.name):
            if in_git or explicit:
                msg, level = f"{rel} would be committed; add it to .gitignore", ERROR
            else:
                msg, level = f"{rel} is a real env file; make sure it is in .gitignore", WARNING
            issues.append(Issue(level, "env-file", None, msg, rel))
            continue  # its contents are expected to be secret

        if is_example_env_file(p.name):
            try:
                ex = parse_file(p)
            except (ParseError, UnicodeDecodeError):
                ex = None
            if ex:
                for key, e in ex.entries.items():
                    if IGNORE_MARKER in " ".join(e.comments):
                        continue
                    if SECRET_KEY_RE.search(key) and looks_like_real_secret(e.value):
                        issues.append(Issue(ERROR, "example-secret", key,
                                            f"{key} in {rel} looks like a real secret ({_mask(e.value)}); "
                                            f"example files should only hold placeholders", rel, e.line))

        issues.extend(_scan_text(p, rel))
    return issues
