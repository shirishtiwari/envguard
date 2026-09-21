"""A small, dependency-free .env parser.

Supports:
  KEY=value
  export KEY=value
  KEY="double quoted, with \\n escapes"
  KEY='single quoted, taken literally'
  KEY=value  # inline comment (unquoted values only)
  multi-line double/single quoted values

Comment lines directly above a key are kept, because envguard reads
schema annotations (``# @type int``) from them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

_KEY_RE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_.\-]*)\s*=\s*(.*)$")
_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\", "$": "$"}


class ParseError(ValueError):
    def __init__(self, path: str, line: int, message: str):
        super().__init__(f"{path}:{line}: {message}")
        self.path = path
        self.line = line


@dataclass
class Entry:
    key: str
    value: str
    line: int
    comments: List[str] = field(default_factory=list)


@dataclass
class EnvFile:
    path: str
    entries: Dict[str, Entry] = field(default_factory=dict)
    duplicates: List[Entry] = field(default_factory=list)

    def get(self, key: str) -> Optional[str]:
        e = self.entries.get(key)
        return e.value if e else None

    def keys(self) -> List[str]:
        return list(self.entries.keys())


def _unescape_double(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] in _ESCAPES:
            out.append(_ESCAPES[s[i + 1]])
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _find_closing(s: str, quote: str) -> int:
    """Index of the closing quote in s (which starts after the opening quote), or -1."""
    i = 0
    while i < len(s):
        if s[i] == "\\" and quote == '"':
            i += 2
            continue
        if s[i] == quote:
            return i
        i += 1
    return -1


def parse_text(text: str, path: str = "<string>") -> EnvFile:
    env = EnvFile(path=path)
    lines = text.splitlines()
    pending_comments: List[str] = []
    i = 0
    while i < len(lines):
        lineno = i + 1
        raw = lines[i]
        stripped = raw.strip()
        i += 1

        if not stripped:
            pending_comments = []
            continue
        if stripped.startswith("#"):
            pending_comments.append(stripped[1:].strip())
            continue

        m = _KEY_RE.match(stripped)
        if not m:
            raise ParseError(path, lineno, f"cannot parse line: {raw!r}")
        key, rest = m.group(1), m.group(2)

        if rest[:1] in ('"', "'"):
            quote = rest[0]
            body = rest[1:]
            end = _find_closing(body, quote)
            # multi-line quoted value
            while end == -1:
                if i >= len(lines):
                    raise ParseError(path, lineno, f"unterminated {quote} quote for {key}")
                body += "\n" + lines[i]
                i += 1
                end = _find_closing(body, quote)
            value = body[:end]
            trailing = body[end + 1 :].strip()
            if trailing and not trailing.startswith("#"):
                raise ParseError(path, lineno, f"unexpected text after closing quote for {key}")
            if quote == '"':
                value = _unescape_double(value)
        else:
            # unquoted: strip inline comment (a '#' preceded by whitespace)
            value = re.split(r"\s+#", rest, maxsplit=1)[0].strip()

        entry = Entry(key=key, value=value, line=lineno, comments=pending_comments)
        pending_comments = []
        if key in env.entries:
            env.duplicates.append(env.entries[key])
        env.entries[key] = entry  # last one wins, like most dotenv loaders
    return env


def parse_file(path) -> EnvFile:
    p = Path(path)
    return parse_text(p.read_text(encoding="utf-8"), str(p))
