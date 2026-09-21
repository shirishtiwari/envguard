import unittest

from envguard.parser import ParseError, parse_text


class ParserTests(unittest.TestCase):
    def test_basic_and_export(self):
        env = parse_text("A=1\nexport B=two\n")
        self.assertEqual(env.get("A"), "1")
        self.assertEqual(env.get("B"), "two")

    def test_inline_comment_and_hash_in_value(self):
        env = parse_text("A=hello # comment\nB=abc#def\n")
        self.assertEqual(env.get("A"), "hello")
        self.assertEqual(env.get("B"), "abc#def")

    def test_quotes(self):
        env = parse_text('A="line1\\nline2"\nB=\'raw\\n\'\nC="has # hash" # c\n')
        self.assertEqual(env.get("A"), "line1\nline2")
        self.assertEqual(env.get("B"), "raw\\n")
        self.assertEqual(env.get("C"), "has # hash")

    def test_multiline_quoted(self):
        env = parse_text('KEY="-----BEGIN-----\nabc\n-----END-----"\nNEXT=1\n')
        self.assertEqual(env.get("KEY"), "-----BEGIN-----\nabc\n-----END-----")
        self.assertEqual(env.get("NEXT"), "1")

    def test_comments_attach_to_next_key_only(self):
        env = parse_text("# about A\n# @type int\nA=1\n\n# orphan\n\nB=2\n")
        self.assertEqual(env.entries["A"].comments, ["about A", "@type int"])
        self.assertEqual(env.entries["B"].comments, [])

    def test_duplicates_last_wins(self):
        env = parse_text("A=1\nA=2\n")
        self.assertEqual(env.get("A"), "2")
        self.assertEqual(len(env.duplicates), 1)

    def test_empty_value(self):
        self.assertEqual(parse_text("A=\n").get("A"), "")

    def test_errors(self):
        with self.assertRaises(ParseError):
            parse_text("not a valid line\n")
        with self.assertRaises(ParseError):
            parse_text('A="unterminated\n')


if __name__ == "__main__":
    unittest.main()
