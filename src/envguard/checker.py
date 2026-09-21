"""Compare an env file with its example/schema and report issues."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import List, Optional

from .parser import EnvFile
from .schema import Schema, validate_value

ERROR = "error"
WARNING = "warning"

_PLACEHOLDER_RE = re.compile(
    r"^(changeme|change[-_ ]?me|todo|tbd|fixme|xxx+|placeholder|your[-_ ].*|<.*>|\.\.\.|replace[-_ ]?me)$",
    re.IGNORECASE,
)


@dataclass
class Issue:
    level: str       # "error" | "warning"
    code: str        # machine-readable, e.g. "missing"
    key: Optional[str]
    message: str
    file: str = ""
    line: Optional[int] = None

    def to_dict(self):
        return asdict(self)


def check(env: EnvFile, schema: Schema, *, strict: bool = False) -> List[Issue]:
    issues: List[Issue] = []

    for msg in schema.errors:
        issues.append(Issue(ERROR, "schema", None, msg))

    for key, rule in schema.rules.items():
        entry = env.entries.get(key)
        if entry is None:
            if rule.required:
                hint = f" (example: {rule.key}={rule.default})" if rule.default and not rule.secret else ""
                issues.append(Issue(ERROR, "missing", key, f"{key} is required but missing{hint}", env.path))
            continue

        value = entry.value
        if value == "":
            if rule.required and not rule.allow_empty:
                issues.append(Issue(ERROR, "empty", key, f"{key} is required but empty", env.path, entry.line))
            continue

        if _PLACEHOLDER_RE.match(value.strip()):
            issues.append(Issue(WARNING, "placeholder", key,
                                f"{key} still looks like a placeholder ('{value}')", env.path, entry.line))

        err = validate_value(rule, value)
        if err:
            shown = err if not rule.secret else err.split(", got")[0]
            issues.append(Issue(ERROR, "invalid", key, f"{key}: {shown}", env.path, entry.line))

    for key, entry in env.entries.items():
        if key not in schema.rules:
            issues.append(Issue(ERROR if strict else WARNING, "extra", key,
                                f"{key} is not declared in the example file", env.path, entry.line))

    for dup in env.duplicates:
        issues.append(Issue(WARNING, "duplicate", dup.key,
                            f"{dup.key} is defined more than once; the last definition wins", env.path, dup.line))

    issues.sort(key=lambda i: (i.level != ERROR, i.line or 0, i.key or ""))
    return issues
