import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


sys.modules.setdefault(
    "decky",
    types.SimpleNamespace(DECKY_USER_HOME="/home/deck", logger=Mock()),
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "py_modules"))

from lsfg_vk.installation import InstallationService


class InstallationCleanupTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        home = Path(self.tempdir.name) / "home" / "deck"
        home.mkdir(parents=True)
        with patch("lsfg_vk.base_service.decky", types.SimpleNamespace(DECKY_USER_HOME=str(home), logger=Mock())):
            self.service = InstallationService(logger=Mock(), runtime_service=Mock(), steam_service=Mock())
        self.home = home
        self.service.config_dir.mkdir(parents=True)
        self.service.config_file_path.write_text("version = 2\n", encoding="utf-8")
        self.service.installer_state_path.parent.mkdir(parents=True)
        self.service.installer_state_path.write_text("state", encoding="utf-8")
        self.service.installed_installer_path.parent.mkdir(parents=True)
        self.service.installed_installer_path.write_text("#!/bin/sh\n", encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def _set_ownership(self, installed_renderer):
        self.service.ownership_path.write_text(
            json.dumps({"version": 1, "installed_renderer": installed_renderer}),
            encoding="utf-8",
        )

    def test_uninstall_removes_renderer_installed_by_plugin(self):
        self._set_ownership(True)
        unrelated = self.home / ".local/bin/keep-me"
        unrelated.write_text("user file", encoding="utf-8")

        with patch.object(self.service, "_run_installer") as run_installer:
            result = self.service.uninstall()

        self.assertTrue(result["success"])
        run_installer.assert_called_once_with(self.service.installed_installer_path, "--uninstall")
        self.assertFalse(self.service.config_file_path.exists())
        self.assertFalse(self.service.ownership_path.exists())
        self.assertFalse(self.service.config_dir.exists())
        self.assertTrue(unrelated.exists())

    def test_uninstall_keeps_shared_renderer(self):
        self._set_ownership(False)

        with patch.object(self.service, "_run_installer") as run_installer:
            result = self.service.uninstall()

        self.assertTrue(result["success"])
        run_installer.assert_not_called()
        self.assertFalse(self.service.config_file_path.exists())
        self.assertTrue(self.service.installer_state_path.exists())


if __name__ == "__main__":
    unittest.main()
