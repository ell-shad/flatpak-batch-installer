"""Unit tests for flathub_gui.flatpak (pure helpers only, no live calls)."""

import unittest

from flathub_gui.flatpak import (
    build_install_cmd,
    diagnose_catalog_error,
    scope_args,
)


class ScopeTest(unittest.TestCase):
    def test_scopes(self):
        self.assertEqual(scope_args("user"), ["--user"])
        self.assertEqual(scope_args("system"), ["--system"])

    def test_invalid(self):
        with self.assertRaises(ValueError):
            scope_args("bogus")


class InstallCmdTest(unittest.TestCase):
    def test_dedupes_keeps_order(self):
        self.assertEqual(
            build_install_cmd("user", "flathub", ["b", "a", "b", ""]),
            ["flatpak", "--user", "install", "--assumeyes", "--noninteractive",
             "flathub", "b", "a"])

    def test_system_scope(self):
        cmd = build_install_cmd("system", "flathub", ["org.a.B"])
        self.assertEqual(cmd[:2], ["flatpak", "--system"])


class DiagnoseTest(unittest.TestCase):
    def test_missing_remote(self):
        msg = diagnose_catalog_error("error: remote flathub not found", "user")
        self.assertIn("remote-add", msg)
        self.assertIn("--user", msg)

    def test_multiple_installations(self):
        msg = diagnose_catalog_error(
            "Remote 'flathub' found in multiple installations:", "user")
        self.assertIn("explicit scope", msg)

    def test_permission(self):
        msg = diagnose_catalog_error("Permission denied", "system")
        self.assertIn("User", msg)

    def test_empty_stderr(self):
        self.assertIn("no error message", diagnose_catalog_error("", "user"))


if __name__ == "__main__":
    unittest.main()
