import subprocess
import tempfile
import unittest
from pathlib import Path

from envguard.secrets import is_env_file, is_example_env_file, scan

# Built by concatenation so this file doesn't trip envguard's own scan.
FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
FAKE_GH = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"


def git_available():
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


class SecretScanTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def test_file_name_classification(self):
        for n in [".env", ".env.local", ".env.production", "prod.env"]:
            self.assertTrue(is_env_file(n), n)
        for n in [".env.example", ".env.sample", ".env.template", "README.md"]:
            self.assertFalse(is_env_file(n), n)
        self.assertTrue(is_example_env_file(".env.example"))

    def test_detects_hardcoded_tokens(self):
        self.write("app/config.py", f'AWS = "{FAKE_AWS}"\nGH = "{FAKE_GH}"\nOK = "hello"\n')
        issues = scan(self.root)
        self.assertEqual([i.line for i in issues if i.code == "secret"], [1, 2])
        self.assertNotIn(FAKE_AWS, " ".join(i.message for i in issues))  # masked

    def test_ignore_marker(self):
        self.write("a.py", f'X = "{FAKE_AWS}"  # envguard:ignore\n')
        self.assertEqual(scan(self.root), [])

    def test_real_secret_in_example_file(self):
        self.write(".env.example", "API_KEY=q8Zr3LmX0pVt7WnB2cYd\nPORT=3000\nTOKEN=\n")
        issues = scan(self.root)
        self.assertEqual([(i.code, i.key) for i in issues], [("example-secret", "API_KEY")])

    def test_exclude(self):
        self.write("tests/fixture.py", f'X = "{FAKE_AWS}"\n')
        self.assertEqual(scan(self.root, exclude=["tests/*"]), [])

    @unittest.skipUnless(git_available(), "git not installed")
    def test_env_file_not_gitignored_is_error(self):
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.write(".env", "SECRET=1\n")
        issues = scan(self.root)
        self.assertEqual([(i.level, i.code) for i in issues], [("error", "env-file")])
        self.write(".gitignore", ".env\n")
        self.assertEqual(scan(self.root), [])


if __name__ == "__main__":
    unittest.main()
