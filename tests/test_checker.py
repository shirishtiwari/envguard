import unittest

from envguard.checker import check
from envguard.parser import parse_text
from envguard.schema import build_schema, validate_value, Rule

EXAMPLE = """\
# @type enum @choices dev,prod
APP_ENV=dev
# @type port
PORT=3000
# @type int @min 1 @max 8
WORKERS=2
# @optional @type url
SENTRY_DSN=
# @secret
# @pattern ^sk_
API_KEY=
"""


def codes(issues):
    return sorted((i.code, i.key) for i in issues)


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.schema = build_schema(parse_text(EXAMPLE, ".env.example"))

    def test_valid(self):
        env = parse_text("APP_ENV=prod\nPORT=8080\nWORKERS=4\nAPI_KEY=sk_abc\n")
        self.assertEqual(check(env, self.schema), [])

    def test_missing_empty_invalid_extra(self):
        env = parse_text("APP_ENV=qa\nWORKERS=99\nAPI_KEY=\nEXTRA=1\n")
        self.assertEqual(codes(check(env, self.schema)), [
            ("empty", "API_KEY"), ("extra", "EXTRA"), ("invalid", "APP_ENV"),
            ("invalid", "WORKERS"), ("missing", "PORT"),
        ])

    def test_optional_may_be_missing_but_is_validated_when_set(self):
        env = parse_text("APP_ENV=dev\nPORT=1\nWORKERS=1\nAPI_KEY=sk_x\nSENTRY_DSN=nope\n")
        self.assertEqual(codes(check(env, self.schema)), [("invalid", "SENTRY_DSN")])

    def test_strict_makes_extra_an_error(self):
        env = parse_text("APP_ENV=dev\nPORT=1\nWORKERS=1\nAPI_KEY=sk_x\nEXTRA=1\n")
        self.assertEqual(check(env, self.schema)[0].level, "warning")
        self.assertEqual(check(env, self.schema, strict=True)[0].level, "error")

    def test_secret_values_are_not_echoed(self):
        env = parse_text("APP_ENV=dev\nPORT=1\nWORKERS=1\nAPI_KEY=hunter2hunter2\n")
        msgs = " ".join(i.message for i in check(env, self.schema))
        self.assertNotIn("hunter2", msgs)

    def test_placeholder_warning(self):
        env2 = parse_text("APP_ENV=dev\nPORT=1\nWORKERS=1\nAPI_KEY=sk_x\nSENTRY_DSN=<your-dsn>\n")
        self.assertIn(("placeholder", "SENTRY_DSN"), codes(check(env2, self.schema)))

    def test_schema_errors_reported(self):
        schema = build_schema(parse_text("# @type banana\n# @bogus\nA=1\n"))
        self.assertEqual(len(schema.errors), 2)

    def test_type_validation(self):
        cases = {
            "int": (["0", "-5", "42"], ["4.2", "x", ""]),
            "float": (["1", "1.5", "-0.2"], ["abc"]),
            "bool": (["true", "0", "YES", "off"], ["maybe"]),
            "url": (["https://a.io/x?y=1", "redis://h:6379"], ["a.io", "http//x"]),
            "email": (["a@b.co"], ["a@b", "nope"]),
            "port": (["1", "65535"], ["0", "65536", "http"]),
            "json": (['{"a":1}', "[1,2]"], ["{a:1}"]),
        }
        for t, (good, bad) in cases.items():
            rule = Rule(key="K", type=t)
            for v in good:
                self.assertIsNone(validate_value(rule, v), f"{t} should accept {v!r}")
            for v in bad:
                self.assertIsNotNone(validate_value(rule, v), f"{t} should reject {v!r}")


if __name__ == "__main__":
    unittest.main()
