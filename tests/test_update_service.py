import hashlib
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch


sys.modules.setdefault(
    "decky",
    types.SimpleNamespace(DECKY_USER_HOME="/home/deck", logger=Mock()),
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "py_modules"))

from lsfg_vk.update_service import UpdateService


def release(tag, asset="Jedi.LSFG-VK.zip", **changes):
    value = {
        "tag_name": tag,
        "draft": False,
        "prerelease": False,
        "body": f"Notes {tag}",
        "html_url": f"https://github.com/sauliiin/Jedi-LSFG-VK/releases/tag/{tag}",
        "assets": [{
            "name": asset,
            "browser_download_url": f"https://example.invalid/{tag}/{asset}",
            "size": 2968451,
            "digest": "sha256:" + "a" * 64,
        }],
    }
    value.update(changes)
    return value


class UpdateServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = UpdateService(logger=Mock())

    def test_latest_release_skips_drafts_prereleases_and_releases_without_zip(self):
        latest = UpdateService.latest_release([
            release("v1.0.2"),
            release("v1.3.0", draft=True),
            release("v1.2.0", prerelease=True),
            release("v1.1.5", asset="notes.txt"),
            release("v1.1.0"),
        ])

        self.assertEqual(latest["version"], "1.1.0")
        self.assertEqual(latest["url"], "https://example.invalid/v1.1.0/Jedi.LSFG-VK.zip")
        self.assertEqual(latest["sha256"], "a" * 64)

    def test_versions_compare_numerically(self):
        self.assertGreater(UpdateService.parse_version("v1.10.0"), UpdateService.parse_version("1.9.9"))
        self.assertEqual(UpdateService.parse_version("not a version"), ())

    def test_status_reports_newer_release(self):
        with patch.object(self.service, "installed_version", return_value="1.1.0"), \
                patch.object(self.service, "_fetch_releases", return_value=[release("v1.1.1")]):
            status = self.service.status()

        self.assertTrue(status["success"])
        self.assertTrue(status["update_available"])
        self.assertEqual(status["latest_version"], "1.1.1")
        self.assertEqual(status["url"], "https://example.invalid/v1.1.1/Jedi.LSFG-VK.zip")

    def test_status_is_current_when_installed_is_latest_and_caches_github(self):
        fetch = Mock(return_value=[release("v1.1.1")])
        with patch.object(self.service, "installed_version", return_value="1.1.1"), \
                patch.object(self.service, "_fetch_releases", fetch):
            self.assertFalse(self.service.status()["update_available"])
            self.service.status()
            self.service.status(force=True)

        self.assertEqual(fetch.call_count, 2)

    def test_network_failure_is_reported_without_raising(self):
        with patch.object(self.service, "_fetch_releases", side_effect=OSError("offline")):
            status = self.service.status()

        self.assertFalse(status["success"])
        self.assertFalse(status["update_available"])
        self.assertIn("offline", status["error"])



class ApplyReleaseTests(unittest.TestCase):
    """Writing a release ZIP over an installed plugin, the way Decky lays it out."""

    def setUp(self):
        self.service = UpdateService(logger=Mock())
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.plugin = self.tmp / "plugin"
        self.install({
            "plugin.json": b'{"name": "Jedi LSFG-VK"}',
            "main.py": b"old main",
            "package.json": b'{"version": "1.2.0"}',
            "dist/index.js": b"old ui",
            "py_modules/lsfg_vk/plugin.py": b"old plugin",
        })
        self.archive = self.tmp / "release.zip"
        self.sources = {}

    def install(self, files):
        for name, data in files.items():
            path = self.plugin / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def release(self, files):
        with zipfile.ZipFile(self.archive, "w") as zf:
            for name, data in files.items():
                zf.writestr(f"Jedi LSFG-VK/{name}", data)
        self.sources["https://example.invalid/plugin.zip"] = self.archive.read_bytes()
        return {"url": "https://example.invalid/plugin.zip", "sha256": hashlib.sha256(self.sources["https://example.invalid/plugin.zip"]).hexdigest()}

    def apply(self, release):
        def download(url, destination):
            destination.write_bytes(self.sources[url])
        with patch.object(self.service, "_download", side_effect=download):
            return self.service._apply_release(release, self.plugin)

    def test_writes_changed_files_with_python_last(self):
        release = self.release({
            "plugin.json": b'{"name": "Jedi LSFG-VK"}',
            "main.py": b"new main",
            "package.json": b'{"version": "1.2.1"}',
            "dist/index.js": b"new ui",
            "py_modules/lsfg_vk/plugin.py": b"new plugin",
            "i18n/template.json": b"{}",
        })
        order = []
        write_bytes = Path.write_bytes

        def record(path, data):
            if path.is_relative_to(self.plugin):
                order.append(str(path.relative_to(self.plugin)))
            return write_bytes(path, data)

        with patch.object(Path, "write_bytes", record):
            changed = self.apply(release)

        self.assertNotIn("plugin.json", changed)
        self.assertEqual(order[-2:], ["py_modules/lsfg_vk/plugin.py", "main.py"])
        self.assertEqual((self.plugin / "main.py").read_bytes(), b"new main")
        self.assertEqual((self.plugin / "dist/index.js").read_bytes(), b"new ui")
        self.assertEqual((self.plugin / "i18n/template.json").read_bytes(), b"{}")

    def test_checksum_mismatch_writes_nothing(self):
        release = self.release({"main.py": b"new main"})
        release["sha256"] = "0" * 64

        with self.assertRaisesRegex(OSError, "checksum"):
            self.apply(release)
        self.assertEqual((self.plugin / "main.py").read_bytes(), b"old main")

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root can write read-only files")
    def test_read_only_file_writes_nothing(self):
        release = self.release({"main.py": b"new main", "dist/index.js": b"new ui"})
        (self.plugin / "main.py").chmod(0o444)
        self.addCleanup((self.plugin / "main.py").chmod, 0o644)

        with self.assertRaisesRegex(OSError, "main.py"):
            self.apply(release)
        self.assertEqual((self.plugin / "dist/index.js").read_bytes(), b"old ui")

    def test_fetches_missing_remote_binaries_and_checks_them(self):
        good = b"renderer"
        self.sources["https://example.invalid/mako.tar.xz"] = good
        package = {"version": "1.2.1", "remote_binary": [{
            "name": "mako.tar.xz",
            "url": "https://example.invalid/mako.tar.xz",
            "sha256hash": hashlib.sha256(good).hexdigest(),
        }]}
        release = self.release({"package.json": json.dumps(package).encode(), "main.py": b"new main"})

        self.apply(release)
        self.assertEqual((self.plugin / "bin/mako.tar.xz").read_bytes(), good)

        self.sources["https://example.invalid/mako.tar.xz"] = b"tampered"
        (self.plugin / "bin/mako.tar.xz").unlink()
        self.install({"package.json": b'{"version": "1.2.0"}', "main.py": b"old main"})
        with self.assertRaisesRegex(OSError, "checksum"):
            self.apply(release)
        self.assertFalse((self.plugin / "bin/mako.tar.xz").exists())
        self.assertEqual((self.plugin / "main.py").read_bytes(), b"old main")

    def test_install_reports_failure_without_raising(self):
        status = {"success": True, "update_available": True, "installed_version": "1.2.0",
                  "latest_version": "1.2.1", "plugin_name": "Jedi LSFG-VK", "url": "u", "sha256": ""}
        with patch.object(self.service, "status", return_value=status):
            result = self.service.install()

        self.assertFalse(result["success"])
        self.assertIn("SHA-256", result["error"])


if __name__ == "__main__":
    unittest.main()
