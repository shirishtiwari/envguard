import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from envguard.cli import main


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self._cwd = os.getcwd()
        os.chdir(self.dir)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_check_default_command_and_exit_codes(self):
        Path(".env.example").write_text("# @type int\nA=1\nB=x\n")
        Path(".env").write_text("A=1\nB=y\n")
        self.assertEqual(self.run_cli()[0], 0)
        Path(".env").write_text("A=one\n")
        code, out, _ = self.run_cli("--no-color")
        self.assertEqual(code, 1)
        self.assertIn("B is required but missing", out)

    def test_json_output(self):
        Path(".env.example").write_text("A=\n")
        Path(".env").write_text("A=1\nZ=2\n")
        code, out, _ = self.run_cli("check", "--json")
        data = json.loads(out)
        self.assertEqual((code, data["ok"], data["warnings"]), (0, True, 1))
        self.assertEqual(self.run_cli("check", "--fail-on-warning")[0], 1)

    def test_missing_file_is_usage_error(self):
        code, _, err = self.run_cli("check")
        self.assertEqual(code, 2)
        self.assertIn("not found", err)

    def test_init_then_check_roundtrip(self):
        Path(".env").write_text("PORT=8080\nDEBUG=true\nAPI_KEY=supersecret\nNAME=my app\n")
        self.assertEqual(self.run_cli("init", "--keep-values")[0], 0)
        example = Path(".env.example").read_text()
        self.assertIn("# @type port\nPORT=8080", example)
        self.assertIn("API_KEY=\n", example)
        self.assertNotIn("supersecret", example)
        self.assertIn('NAME="my app"', example)
        self.assertEqual(self.run_cli("check")[0], 0)
        self.assertEqual(self.run_cli("init")[0], 2)  # refuses to overwrite

    def test_sync_appends_missing_keys(self):
        Path(".env.example").write_text("A=1\nB=2\nSECRET_TOKEN=abc\n")
        Path(".env").write_text("A=9")
        code, out, _ = self.run_cli("sync")
        self.assertEqual(code, 0)
        text = Path(".env").read_text()
        self.assertTrue(text.startswith("A=9\n"))
        self.assertIn("B=2\n", text)
        self.assertIn("SECRET_TOKEN=\n", text)
        self.assertEqual(self.run_cli("check")[0], 1)  # SECRET_TOKEN empty
        self.assertIn("already has every key", self.run_cli("sync")[1])


if __name__ == "__main__":
    unittest.main()
