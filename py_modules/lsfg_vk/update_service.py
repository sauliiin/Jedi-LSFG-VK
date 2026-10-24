"""Plugin self-update: the newest GitHub release of this plugin.

The backend finds the release and writes its ZIP over the plugin; the frontend
then asks Decky to reload it. Decky's own install prompt opens in the main
window and never showed from the Quick Access menu.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import decky

from .base_service import BaseService
from .constants import PLUGIN_RELEASE_ASSET_RE, PLUGIN_RELEASES_API


class UpdateService(BaseService):
    CACHE_SECONDS = 600
    REQUEST_TIMEOUT_SECONDS = 10
    DOWNLOAD_TIMEOUT_SECONDS = 600

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

    def install(self) -> Dict[str, Any]:
        """Install the newest release over this plugin; Decky reloads it afterwards."""
        status = self.status(force=True)
        if not status.get("success"):
            return status
        if not status.get("update_available"):
            return {"success": False, "error": "No newer release to install."}
        try:
            changed = self._apply_release(status, Path(getattr(decky, "DECKY_PLUGIN_DIR", "")))
        except Exception as error:
            self.log.error(f"Plugin update failed: {error}")
            return {"success": False, "error": str(error)}
        self.log.info(f"Plugin updated {status['installed_version']} -> {status['latest_version']}: {changed}")
        return {
            "success": True,
            "error": None,
            "plugin_name": status["plugin_name"],
            "version": status["latest_version"],
        }

    def _apply_release(self, release: Dict[str, Any], plugin_dir: Path) -> list:
        """Write the release ZIP over the plugin. Decky owns the plugin folder itself (only files already
        in it can be replaced), so nothing is written until every changed file is known to be writable,
        the ZIP matches GitHub's SHA-256 and the new package.json's remote binaries are in bin/."""
        if not release.get("sha256"):
            raise OSError("GitHub gave no SHA-256 for the release ZIP")
        if not (plugin_dir / "plugin.json").is_file():
            raise OSError(f"Plugin folder not found: {plugin_dir}")
        with tempfile.TemporaryDirectory(prefix="jedi-lsfg-update-") as staging:
            archive = Path(staging) / "plugin.zip"
            self._download(release["url"], archive)
            if self._sha256(archive) != release["sha256"]:
                raise OSError("Downloaded plugin ZIP failed checksum verification")
            files: Dict[Path, bytes] = {}
            with zipfile.ZipFile(archive) as zf:
                for info in zf.infolist():
                    parts = Path(info.filename).parts[1:]  # drop the ZIP's top folder
                    if info.is_dir() or not parts:
                        continue
                    if ".." in parts or Path(info.filename).is_absolute():
                        raise OSError(f"Unsafe path in the plugin ZIP: {info.filename}")
                    data = zf.read(info)
                    target = plugin_dir.joinpath(*parts)
                    if target.is_file() and self._sha256(target) == hashlib.sha256(data).hexdigest():
                        continue
                    files[target] = data
        blocked = [
            str(path.relative_to(plugin_dir)) for path in files
            if not os.access(path if path.exists() else self._existing_parent(path), os.W_OK)
        ]
        if blocked:
            raise OSError(f"Cannot write {', '.join(blocked)}. Install the ZIP from Decky's settings instead.")
        package = json.loads(files.get(plugin_dir / "package.json") or (plugin_dir / "package.json").read_bytes())
        self._fetch_remote_binaries(plugin_dir / "bin", package.get("remote_binary") or [])
        # Python last, main.py after its package: if anything fails first, the old plugin still runs.
        for path in sorted(files, key=lambda item: (item.suffix == ".py", item == plugin_dir / "main.py")):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(files[path])
        return [str(path.relative_to(plugin_dir)) for path in files]

    @staticmethod
    def _existing_parent(path: Path) -> Path:
        while not path.exists():
            path = path.parent
        return path

    def _fetch_remote_binaries(self, bin_dir: Path, binaries: list) -> None:
        """What Decky's installer does after unzipping: every remote binary in bin/, checked against its SHA-256."""
        bin_dir.mkdir(parents=True, exist_ok=True)
        for binary in binaries:
            target = bin_dir / binary["name"]
            if target.is_file() and self._sha256(target) == binary["sha256hash"]:
                continue
            partial = target.with_name(target.name + ".part")
            try:
                self._download(binary["url"], partial)
                if self._sha256(partial) != binary["sha256hash"]:
                    raise OSError(f"{binary['name']} failed checksum verification")
                os.replace(partial, target)
            finally:
                partial.unlink(missing_ok=True)

    def _download(self, url: str, destination: Path) -> None:
        env = self._host_environment()
        curl = shutil.which("curl", path=env["PATH"])
        if curl is None:
            raise FileNotFoundError("curl is required to download the update")
        result = subprocess.run(
            [curl, "-fsSL", "--retry", "3", "-o", str(destination), url],
            env=env,
            capture_output=True,
            text=True,
            timeout=self.DOWNLOAD_TIMEOUT_SECONDS,
            check=False,
        )
        if result.returncode != 0:
            raise OSError(result.stderr.strip() or f"Could not download {url}")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
