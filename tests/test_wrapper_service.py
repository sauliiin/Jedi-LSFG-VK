import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock


sys.modules.setdefault(
    "decky",
    types.SimpleNamespace(DECKY_USER_HOME="/home/deck", logger=Mock()),
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "py_modules"))

from lsfg_vk.wrapper_service import WrapperService


class WrapperServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.home = Path(self.tempdir.name) / "home" / "deck"
        self.home.mkdir(parents=True)
        self.service = WrapperService()
        self.service.user_home = self.home
        self.service.config_dir = self.home / ".config/jedi-lsfg-vk"
        self.service.config_file_path = self.service.config_dir / "conf.toml"
        self.service.sidecar_path = self.service.config_dir / "workarounds.json"
        self.service.wrapper_path = self.home / ".jedi-lsfg"
        # Stand-in for mako-launch: marks the environment, then runs the game.
        self.service.launcher_path = self.home / ".local/bin/mako-launch"
        self.service.launcher_path.parent.mkdir(parents=True)
        self.service.launcher_path.write_text(
            "#!/bin/sh\nVIA_MAKO_LAUNCH=1\nexport VIA_MAKO_LAUNCH\nexec \"$@\"\n",
            encoding="utf-8",
        )
        self.service.launcher_path.chmod(0o755)

    def tearDown(self):
        self.tempdir.cleanup()

    def _state(self, **changes):
        state = self.service.default_state()
        state.update(changes)
        return state

    def _run(self, appid, *args, env=None):
        process_env = {"PATH": "/usr/bin:/bin", "SteamAppId": str(appid)}
        if env:
            process_env.update(env)
        return subprocess.run(
            [str(self.service.wrapper_path), *args],
            env=process_env,
            capture_output=True,
            text=True,
            check=True,
        )

    def test_writes_owned_dispatcher_and_validates_shell(self):
        response = self.service.set("123", self._state(dxvkFrameRate=60, enableZink=True))
        self.assertTrue(response["success"])
        self.assertEqual(response["wrapper_path"], "~/.jedi-lsfg")
        self.assertTrue(response["wrapper_owned"])
        self.assertEqual(response["state"]["dxvkFrameRate"], 60)
        self.assertEqual(subprocess.run(["/bin/sh", "-n", str(self.service.wrapper_path)]).returncode, 0)
        self.assertIn(self.service.MARKER, self.service.wrapper_path.read_text(encoding="utf-8"))
        self.assertEqual(self.service.get("123")["state"], self._state(dxvkFrameRate=60, enableZink=True))

    def test_dispatch_selects_mako_profile_and_launches_through_mako(self):
        self.service.set(
            "123",
            self._state(dxvkFrameRate=30, disableSteamdeckMode=True, disableVkbasalt=True, enableZink=True),
        )
        result = self._run(
            123,
            "/usr/bin/env",
            env={
                "DXVK_CONFIG": "dxgi.syncInterval = 0",
                "MAKO_PROFILE_FALLBACK": "Default",
                "MAKO_ENV": "1",
                "MESA_LOADER_DRIVER_OVERRIDE": "llvmpipe",
                "MANGOHUD": "1",
            },
        )
        values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        self.assertEqual(values["VIA_MAKO_LAUNCH"], "1")
        self.assertEqual(values["SteamAppId"], "123")
        self.assertEqual(values["MAKO_CONFIG"], str(self.service.config_file_path))
        self.assertEqual(values["MAKO_PROFILE"], "app:123")
        self.assertEqual(values["SteamDeck"], "0")
        self.assertEqual(values["__GLX_VENDOR_LIBRARY_NAME"], "mesa")
        self.assertEqual(values["MESA_LOADER_DRIVER_OVERRIDE"], "zink")
        self.assertEqual(values["GALLIUM_DRIVER"], "zink")
        # MAKO's half-target base cap replaces the DXVK frame cap.
        self.assertEqual(values["DXVK_CONFIG"], "dxgi.syncInterval = 0")
        self.assertEqual(values["MANGOHUD"], "1")
        self.assertNotIn("MAKO_PROFILE_FALLBACK", values)
        self.assertNotIn("MAKO_ENV", values)

    def test_missing_renderer_still_starts_the_game(self):
        self.service.set("123", self._state())
        self.service.launcher_path.unlink()

        result = self._run(123, "/usr/bin/env")

        values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        self.assertNotIn("VIA_MAKO_LAUNCH", values)
        self.assertEqual(values["MAKO_PROFILE"], "app:123")

    def test_preserves_steamdeck_by_default_and_disables_when_requested(self):
        self.service.set("123", self._state())
        inherited = self._run(123, "/usr/bin/env", env={"SteamDeck": "1"})
        inherited_values = dict(line.split("=", 1) for line in inherited.stdout.splitlines() if "=" in line)
        self.assertEqual(inherited_values["SteamDeck"], "1")

        self.service.set("123", self._state(disableSteamdeckMode=True))
        disabled = self._run(123, "/usr/bin/env", env={"SteamDeck": "1"})
        disabled_values = dict(line.split("=", 1) for line in disabled.stdout.splitlines() if "=" in line)
        self.assertEqual(disabled_values["SteamDeck"], "0")

    def test_wrapper_is_transport_agnostic(self):
        self.service.set("123", self._state())
        fake = self.home / "target"
        fake.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
        fake.chmod(0o755)
        result = self._run(123, str(fake), "run", "org.example.Game")
        self.assertEqual(result.stdout.splitlines(), ["run", "org.example.Game"])
        content = self.service.wrapper_path.read_text(encoding="utf-8")
        self.assertNotIn("flatpakAppId", content)
        self.assertNotIn("shortcut_exe", content)
        self.assertNotIn("--filesystem", content)

    def test_appid_fallback_and_unmatched_passthrough(self):
        self.service.set("123", self._state(disableGamescopeWsi=False, disableHdr=False))
        self.service.set("456", self._state(disableSteamdeckMode=True))
        fallback = subprocess.run(
            [str(self.service.wrapper_path), "/usr/bin/env"],
            env={"PATH": "/usr/bin:/bin", "SteamAppId": "bad", "SteamGameId": "456"},
            capture_output=True,
            text=True,
            check=True,
        )
        fallback_values = dict(line.split("=", 1) for line in fallback.stdout.splitlines() if "=" in line)
        self.assertEqual(fallback_values["SteamDeck"], "0")
        self.assertEqual(fallback_values["SteamAppId"], "456")

        passthrough = subprocess.run(
            [str(self.service.wrapper_path), "/usr/bin/env"],
            env={"PATH": "/usr/bin:/bin", "SteamAppId": "999", "KEEP": "yes", "DXVK_HDR": "1"},
            capture_output=True,
            text=True,
            check=True,
        )
        passthrough_values = dict(line.split("=", 1) for line in passthrough.stdout.splitlines() if "=" in line)
        self.assertEqual(passthrough_values["KEEP"], "yes")
        self.assertEqual(passthrough_values["DXVK_HDR"], "1")
        self.assertNotIn("VIA_MAKO_LAUNCH", passthrough_values)
        self.assertNotIn("MAKO_PROFILE", passthrough_values)

    def test_invalid_state_and_foreign_wrapper_fail_closed(self):
        invalid = self.service.set("0", self.service.default_state())
        self.assertFalse(invalid["success"])
        invalid = self.service.set("123", {**self.service.default_state(), "dxvkFrameRate": 61})
        self.assertFalse(invalid["success"])

        self.service.wrapper_path.write_text("#!/bin/sh\necho foreign\n", encoding="utf-8")
        response = self.service.set("123", self.service.default_state())
        self.assertFalse(response["success"])
        self.assertIn("unowned", response["error"])
        self.assertEqual(self.service.wrapper_path.read_text(encoding="utf-8"), "#!/bin/sh\necho foreign\n")

    def test_remove_keeps_safe_passthrough_wrapper(self):
        self.service.set("123", self.service.default_state())
        response = self.service.remove("123")
        self.assertTrue(response["success"])
        self.assertIsNone(self.service.get("123")["state"])
        self.assertTrue(self.service.wrapper_path.exists())
        result = subprocess.run(
            [str(self.service.wrapper_path), "/usr/bin/printf", "ok"],
            env={"PATH": "/usr/bin:/bin", "SteamAppId": "123"},
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(result.stdout, "ok")

    def test_purge_removes_owned_wrapper_and_state(self):
        self.service.set("123", self._state(), non_steam=True)
        self.assertTrue(self.service.get("123")["non_steam"])
        self.assertEqual(self.service.list_apps()["apps"][0]["non_steam"], True)
        response = self.service.purge()
        self.assertTrue(response["success"])
        self.assertEqual(response["removed_files"], [str(self.service.wrapper_path), str(self.service.sidecar_path)])
        self.assertFalse(self.service.wrapper_path.exists())
        self.assertFalse(self.service.sidecar_path.exists())

    def test_purge_refuses_foreign_wrapper(self):
        self.service.wrapper_path.write_text("#!/bin/sh\necho foreign\n", encoding="utf-8")
        response = self.service.purge()
        self.assertFalse(response["success"])
        self.assertIn("unowned", response["error"])
        self.assertTrue(self.service.wrapper_path.exists())

    def test_purge_refuses_invalid_state(self):
        self.service.config_dir.mkdir(parents=True, exist_ok=True)
        self.service.sidecar_path.write_text("not json", encoding="utf-8")
        self.service.wrapper_path.write_text(
            f"#!/bin/sh\n{self.service.MARKER}\nexec \"$@\"\n",
            encoding="utf-8",
        )
        response = self.service.purge()
        self.assertFalse(response["success"])
        self.assertTrue(self.service.wrapper_path.exists())
        self.assertTrue(self.service.sidecar_path.exists())

    def test_neutralize_leaves_dependency_free_passthrough_wrapper(self):
        self.service.set("123", self._state())
        response = self.service.neutralize()
        self.assertTrue(response["success"])
        self.assertFalse(self.service.sidecar_path.exists())
        self.assertTrue(self.service.wrapper_path.exists())
        content = self.service.wrapper_path.read_text(encoding="utf-8")
        self.assertIn(self.service.MARKER, content)
        self.assertNotIn("MAKO_CONFIG", content)
        self.assertEqual(self._run(123, "/usr/bin/printf", "ok").stdout, "ok")

    def test_neutralize_refuses_foreign_wrapper(self):
        self.service.wrapper_path.write_text("#!/bin/sh\necho foreign\n", encoding="utf-8")
        response = self.service.neutralize()
        self.assertFalse(response["success"])
        self.assertIn("unowned", response["error"])
        self.assertEqual(self.service.wrapper_path.read_text(encoding="utf-8"), "#!/bin/sh\necho foreign\n")


if __name__ == "__main__":
    unittest.main()
