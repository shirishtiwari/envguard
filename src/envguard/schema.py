"""Schema rules, read from annotation comments in .env.example.

Annotate a key with comment lines directly above it:

    # Port the HTTP server listens on
    # @type port
    PORT=3000

    # @type enum @choices development,staging,production
    APP_ENV=development

    # @optional
    # @type url
    SENTRY_DSN=

Keys listed in the example are required unless marked ``@optional``.
Any comment line that is not an annotation is kept as the key's description.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .parser import EnvFile

TYPES = ("str", "int", "float", "bool", "url", "email", "port", "json", "enum")
_TYPE_ALIASES = {"string": "str", "integer": "int", "number": "float", "boolean": "bool"}
_ANNOT_RE = re.compile(r"@(\w+)(?:[ \t:=]+([^@]*))?")

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
_URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s/?#]+[^\s]*$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Rule:
    key: str
    type: str = "str"
    required: bool = True
    allow_empty: bool = False
    choices: Optional[List[str]] = None
    pattern: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    secret: bool = False
    default: str = ""
    description: str = ""
    line: int = 0


@dataclass
class Schema:
    rules: Dict[str, Rule] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)  # problems in the annotations themselves


def _parse_annotations(comments: List[str]):
    annots, desc = {}, []
    for c in comments:
        if not c.startswith("@"):
            desc.append(c)
            continue
        # @pattern takes the whole rest of the line (regexes may contain '@')
        if c.startswith("@pattern"):
            annots["pattern"] = c[len("@pattern"):].lstrip(" \t:=").strip()
            continue
        for name, arg in _ANNOT_RE.findall(c):
            annots[name.lower()] = (arg or "").strip()
    return annots, " ".join(desc).strip()


def build_schema(example: EnvFile) -> Schema:
    schema = Schema()
    for key, entry in example.entries.items():
        annots, desc = _parse_annotations(entry.comments)
        rule = Rule(key=key, default=entry.value, description=desc, line=entry.line)
        where = f"{example.path}:{entry.line}"

        t = annots.pop("type", "str").lower() or "str"
        t = _TYPE_ALIASES.get(t, t)
        if t not in TYPES:
            schema.errors.append(f"{where}: unknown @type '{t}' for {key} (expected one of {', '.join(TYPES)})")
            t = "str"
        rule.type = t

        if "optional" in annots:
            rule.required = False
            annots.pop("optional")
        if "required" in annots:
            rule.required = True
            annots.pop("required")
        if "allow_empty" in annots or "allowempty" in annots:
            rule.allow_empty = True
            annots.pop("allow_empty", None)
            annots.pop("allowempty", None)
        if "secret" in annots:
            rule.secret = True
            annots.pop("secret")

        if "choices" in annots:
            rule.choices = [c.strip() for c in annots.pop("choices").split(",") if c.strip()]
            if rule.type == "str":
                rule.type = "enum"
        if rule.type == "enum" and not rule.choices:
            schema.errors.append(f"{where}: {key} is @type enum but has no @choices")

        if "pattern" in annots:
            rule.pattern = annots.pop("pattern")
            try:
                re.compile(rule.pattern)
            except re.error as exc:
                schema.errors.append(f"{where}: invalid @pattern for {key}: {exc}")
                rule.pattern = None

        for bound in ("min", "max"):
            if bound in annots:
                raw = annots.pop(bound)
                try:
                    setattr(rule, bound, float(raw))
                except ValueError:
                    schema.errors.append(f"{where}: @{bound} for {key} must be a number, got '{raw}'")

        annots.pop("description", None)
        for unknown in annots:
            schema.errors.append(f"{where}: unknown annotation @{unknown} on {key}")

        schema.rules[key] = rule
    return schema


def validate_value(rule: Rule, value: str) -> Optional[str]:
    """Return an error message, or None if the value satisfies the rule."""
    t = rule.type
    num: Optional[float] = None

    if t == "int":
        if not re.fullmatch(r"[+-]?\d+", value):
            return f"expected an integer, got '{value}'"
        num = float(int(value))
    elif t == "float":
        try:
            num = float(value)
        except ValueError:
            return f"expected a number, got '{value}'"
    elif t == "port":
        if not value.isdigit() or not (1 <= int(value) <= 65535):
            return f"expected a port number (1-65535), got '{value}'"
        num = float(int(value))
    elif t == "bool":
        if value.lower() not in TRUE_VALUES | FALSE_VALUES:
            return f"expected a boolean (true/false/1/0/yes/no/on/off), got '{value}'"
    elif t == "url":
        if not _URL_RE.match(value):
            return f"expected a URL like https://example.com, got '{value}'"
    elif t == "email":
        if not _EMAIL_RE.match(value):
            return f"expected an email address, got '{value}'"
    elif t == "json":
        try:
            json.loads(value)
        except ValueError as exc:
            return f"expected valid JSON ({exc.msg})"

    if rule.choices is not None and value not in rule.choices:
        return f"must be one of {', '.join(rule.choices)}; got '{value}'"
    if num is not None:
        if rule.min is not None and num < rule.min:
            return f"must be >= {_fmt(rule.min)}, got {value}"
        if rule.max is not None and num > rule.max:
            return f"must be <= {_fmt(rule.max)}, got {value}"
    if rule.pattern and not re.search(rule.pattern, value):
        return f"does not match pattern /{rule.pattern}/"
    return None


def infer_type(value: str) -> str:
    v = value.strip()
    if not v:
        return "str"
    if v.lower() in ("true", "false", "yes", "no", "on", "off"):
        return "bool"
    if re.fullmatch(r"[+-]?\d+", v):
        return "int"
    if re.fullmatch(r"[+-]?\d*\.\d+", v):
        return "float"
    if _URL_RE.match(v):
        return "url"
    if _EMAIL_RE.match(v):
        return "email"
    if v[:1] in "[{":
        try:
            json.loads(v)
            return "json"
        except ValueError:
            pass
    return "str"


def _fmt(n: float) -> str:
    return str(int(n)) if n == int(n) else str(n)
