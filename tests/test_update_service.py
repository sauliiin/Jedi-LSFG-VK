import sys
import types
import unittest
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


if __name__ == "__main__":
    unittest.main()
