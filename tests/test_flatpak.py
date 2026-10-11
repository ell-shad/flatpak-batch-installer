"""Unit tests for flatpak_batch_installer.flatpak (pure helpers only, no live calls)."""

import unittest
from unittest.mock import patch, MagicMock
import subprocess

from flatpak_batch_installer.flatpak import (
    build_install_cmd,
    build_uninstall_cmd,
    diagnose_catalog_error,
    get_installed_details,
    run_update_all,
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


class GetInstalledDetailsTest(unittest.TestCase):
    def test_parse(self):
        """get_installed_details parses tab-separated output correctly."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "app.A\tApp A\t1.0\tflathub\n"
        mock_result.stderr = ""
        with patch("flatpak_batch_installer.flatpak.run_flatpak",
                   return_value=mock_result):
            rows, err = get_installed_details("user")
        self.assertIsNone(err)
        self.assertEqual(rows, [
            {"app_id": "app.A", "name": "App A", "version": "1.0",
             "origin": "flathub"}
        ])

    def test_error_returned(self):
        """get_installed_details returns ([], error) on nonzero exit."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "some error"
        with patch("flatpak_batch_installer.flatpak.run_flatpak",
                   return_value=mock_result):
            rows, err = get_installed_details("user")
        self.assertEqual(rows, [])
        self.assertIsNotNone(err)
        self.assertIn("some error", err)


class BuildUninstallCmdTest(unittest.TestCase):
    def test_user_scope(self):
        cmd = build_uninstall_cmd("user", ["org.a.B"])
        self.assertEqual(cmd, ["flatpak", "--user", "uninstall",
                                "--assumeyes", "--noninteractive", "org.a.B"])

    def test_system_scope(self):
        cmd = build_uninstall_cmd("system", ["org.a.B"])
        self.assertEqual(cmd[:2], ["flatpak", "--system"])

    def test_deduplicates(self):
        cmd = build_uninstall_cmd("user", ["org.a.B", "org.a.B", "org.c.D"])
        # org.a.B should appear only once
        self.assertEqual(cmd.count("org.a.B"), 1)
        self.assertIn("org.c.D", cmd)

    def test_drops_empty(self):
        cmd = build_uninstall_cmd("user", ["org.a.B", "", "org.c.D"])
        self.assertNotIn("", cmd)


class RunUpdateAllTest(unittest.TestCase):
    def test_calls_stream_command_with_correct_args(self):
        """run_update_all calls stream_command with the right flatpak command."""
        with patch("flatpak_batch_installer.installer.stream_command",
                   return_value=0) as mock_sc:
            result = run_update_all("user", lambda line: None)
        self.assertEqual(result, 0)
        mock_sc.assert_called_once()
        called_cmd = mock_sc.call_args[0][0]
        self.assertIn("flatpak", called_cmd)
        self.assertIn("--user", called_cmd)
        self.assertIn("update", called_cmd)
        self.assertIn("--noninteractive", called_cmd)
        self.assertIn("--assumeyes", called_cmd)


if __name__ == "__main__":
    unittest.main()
