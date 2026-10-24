"""Plugin self-update: the newest GitHub release of this plugin.

The backend only finds the release. The frontend hands its ZIP to Decky's own
installer, which asks to confirm, verifies the SHA-256, installs it and
reloads the plugin.
"""

import json
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import decky

from .base_service import BaseService
from .constants import PLUGIN_RELEASE_ASSET_RE, PLUGIN_RELEASES_API


class UpdateService(BaseService):
    CACHE_SECONDS = 600
    REQUEST_TIMEOUT_SECONDS = 10

    def __init__(self, logger=None):
        super().__init__(logger)
        self._lock = threading.Lock()
        self._cache: Optional[Tuple[float, Optional[Dict[str, Any]]]] = None

    @staticmethod
    def parse_version(value: Any) -> Tuple[int, ...]:
        match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", str(value or "").strip())
        return tuple(int(part) for part in match.group(1).split(".")) if match else ()

    def installed_version(self) -> str:
        version = str(getattr(decky, "DECKY_PLUGIN_VERSION", "") or "").strip()
        if version:
            return version
        plugin_dir = getattr(decky, "DECKY_PLUGIN_DIR", "")
        try:
            return str(json.loads((Path(plugin_dir) / "package.json").read_text(encoding="utf-8")).get("version") or "")
        except (OSError, ValueError):
            return ""

    def _fetch_releases(self) -> Any:
        try:
            request = urllib.request.Request(
                PLUGIN_RELEASES_API,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "Jedi-LSFG-VK"},
            )
            with urllib.request.urlopen(request, timeout=self.REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as urllib_error:
            # Decky's bundled Python can lack system CA certificates.
            env = self._host_environment()
            curl = shutil.which("curl", path=env["PATH"])
            if curl is None:
                raise urllib_error
            result = subprocess.run(
                [curl, "-fsSL", "--max-time", str(self.REQUEST_TIMEOUT_SECONDS),
                 "-H", "Accept: application/vnd.github+json", PLUGIN_RELEASES_API],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or str(urllib_error))
            return json.loads(result.stdout)

    @classmethod
    def latest_release(cls, releases: Any) -> Optional[Dict[str, Any]]:
        """Newest published, non-prerelease release that carries the plugin ZIP."""
        best: Optional[Dict[str, Any]] = None
        for release in releases if isinstance(releases, list) else []:
            if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
                continue
            version = cls.parse_version(release.get("tag_name"))
            if not version or (best and version <= cls.parse_version(best["version"])):
                continue
            asset = next((
                item for item in release.get("assets") or []
                if isinstance(item, dict)
                and PLUGIN_RELEASE_ASSET_RE.fullmatch(str(item.get("name") or ""))
                and item.get("browser_download_url")
            ), None)
            if asset is None:
                continue
            digest = str(asset.get("digest") or "")
            best = {
                "version": ".".join(str(part) for part in version),
                "url": asset["browser_download_url"],
                "size": asset.get("size") or 0,
                "sha256": digest[7:] if digest.startswith("sha256:") else "",
                "notes": str(release.get("body") or "")[:1500],
                "release_url": release.get("html_url") or "",
            }
        return best

    def status(self, force: bool = False) -> Dict[str, Any]:
        installed = self.installed_version()
        try:
            with self._lock:
                if force or self._cache is None or time.time() - self._cache[0] >= self.CACHE_SECONDS:
                    self._cache = (time.time(), self.latest_release(self._fetch_releases()))
                latest = self._cache[1]
        except Exception as error:
            self.log.warning(f"Plugin update check failed: {error}")
            return {
                "success": False,
                "error": f"Could not reach GitHub: {error}",
                "installed_version": installed,
                "update_available": False,
            }
        installed_tuple = self.parse_version(installed)
        update_available = bool(
            latest and installed_tuple and self.parse_version(latest["version"]) > installed_tuple
        )
        return {
            "success": True,
            "error": None,
            "plugin_name": str(getattr(decky, "DECKY_PLUGIN_NAME", "") or "Jedi LSFG-VK"),
            "installed_version": installed,
            "latest_version": latest["version"] if latest else None,
            "update_available": update_available,
            **({key: latest[key] for key in ("url", "size", "sha256", "notes", "release_url")} if latest else {}),
        }
