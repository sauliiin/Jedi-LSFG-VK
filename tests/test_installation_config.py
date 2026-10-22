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

from lsfg_vk.config_schema import ConfigurationManager, UnsupportedConfigurationVersion
from lsfg_vk.installation import InstallationService


class InstallationConfigTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.home = Path(self.tempdir.name) / "home" / "deck"
        self.home.mkdir(parents=True)
        self.steam = Mock()
        self.steam.find_lossless_dll.return_value = None
        with patch("lsfg_vk.base_service.decky", types.SimpleNamespace(DECKY_USER_HOME=str(self.home), logger=Mock())):
            self.service = InstallationService(
                logger=Mock(),
                runtime_service=Mock(),
                steam_service=self.steam,
            )

    def tearDown(self):
        self.tempdir.cleanup()

    def _write_config(self, dll=""):
        self.service.config_dir.mkdir(parents=True, exist_ok=True)
        self.service.config_file_path.write_text(
            ConfigurationManager.generate_toml_content_multi_profile({
                "profiles": {"app:123": {"target_fps": 90}},
                "global_config": {"dll": dll, "no_fp16": False},
            }),
            encoding="utf-8",
        )

    def _mark_installed(self):
        for path in (*self.service._renderer_files(), self.service.config_file_path):
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("installed", encoding="utf-8")

    def test_installation_removes_v1_profiles_instead_of_migrating_them(self):
        self.service.config_dir.mkdir(parents=True)
        self.service.config_file_path.write_text(
            'version = 1\n\n[[profile]]\nname = "Old Game"\n',
            encoding="utf-8",
        )

        data = self.service._prepare_config()

        self.assertEqual(data["profiles"], {})
        self.assertEqual(data["global_config"], {"dll": "", "no_fp16": False})
        self.assertFalse(self.service.config_file_path.exists())
        self.service.log.warning.assert_called_once()

    def test_installation_does_not_overwrite_a_future_config_version(self):
        self.service.config_dir.mkdir(parents=True)
        original = "version = 3\n\n[global]\nallow_fp16 = true\n"
        self.service.config_file_path.write_text(original, encoding="utf-8")

        with self.assertRaises(UnsupportedConfigurationVersion):
            self.service._prepare_config()

        self.assertEqual(self.service.config_file_path.read_text(encoding="utf-8"), original)

    def test_check_installation_repairs_dll_path_once_lossless_dll_is_available(self):
        dll_path = self.home / "steamapps/common/Lossless Scaling/Lossless.dll"
        dll_path.parent.mkdir(parents=True)
        dll_path.write_text("dll", encoding="utf-8")
        self.steam.find_lossless_dll.return_value = str(dll_path)
        self.service.runtime_service.check_lossless_scaling.return_value = {
            "installed": True,
            "status": "Lossless Scaling detected",
        }
        self._write_config()
        self._mark_installed()

        result = self.service.check_installation()

        self.assertTrue(result["installed"])
        self.assertTrue(result["lossless_scaling_installed"])
        data = ConfigurationManager.parse_toml_content_multi_profile(
            self.service.config_file_path.read_text(encoding="utf-8")
        )
        self.assertEqual(data["global_config"]["dll"], str(dll_path))
        self.assertEqual(data["profiles"]["app:123"]["target_fps"], 90)
        self.service.runtime_service.validate_config_content.assert_called_once()

    def test_check_installation_does_not_write_dll_path_when_dll_is_missing(self):
        self.service.runtime_service.check_lossless_scaling.return_value = {
            "installed": False,
            "status": "Lossless Scaling's Lossless.dll was not found",
        }
        self._write_config()
        self._mark_installed()

        result = self.service.check_installation()

        self.assertTrue(result["installed"])
        self.assertFalse(result["lossless_scaling_installed"])
        data = ConfigurationManager.parse_toml_content_multi_profile(
            self.service.config_file_path.read_text(encoding="utf-8")
        )
        self.assertEqual(data["global_config"]["dll"], "")
        self.service.runtime_service.validate_config_content.assert_not_called()

    def test_install_does_not_claim_a_preexisting_renderer(self):
        self.service.archive_path = self.home / "renderer.tar.xz"
        self.service.archive_path.write_text("archive", encoding="utf-8")
        self._mark_installed()
        self.service.config_file_path.unlink()

        with patch.object(self.service, "_install_renderer"):
            result = self.service.install()

        self.assertTrue(result["success"], result)
        self.assertFalse(self.service._installed_by_plugin())
        self.assertTrue(self.service.config_file_path.is_file())

    def test_install_claims_a_new_renderer(self):
        self.service.archive_path = self.home / "renderer.tar.xz"
        self.service.archive_path.write_text("archive", encoding="utf-8")

        with patch.object(self.service, "_install_renderer"):
            result = self.service.install()

        self.assertTrue(result["success"], result)
        self.assertTrue(self.service._installed_by_plugin())

    def test_archive_with_link_or_parent_path_is_rejected(self):
        import io
        import tarfile

        for name, kind in (("../escape", tarfile.REGTYPE), ("link", tarfile.SYMTYPE)):
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w") as archive:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.linkname = "/etc/passwd" if kind == tarfile.SYMTYPE else ""
                archive.addfile(member, io.BytesIO(b""))
            buffer.seek(0)
            with self.subTest(name=name), tarfile.open(fileobj=buffer) as archive:
                with self.assertRaises(ValueError):
                    InstallationService._safe_members(archive)


if __name__ == "__main__":
    unittest.main()
