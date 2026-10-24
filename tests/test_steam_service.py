import sys
import tempfile
import types
import unittest
import zlib
from pathlib import Path
from unittest.mock import Mock


sys.modules.setdefault(
    "decky",
    types.SimpleNamespace(DECKY_USER_HOME="/home/deck", logger=Mock()),
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "py_modules"))

from lsfg_vk.steam_service import SteamService


class SteamShortcutTests(unittest.TestCase):
    def test_direct_flatpak_shortcut_is_marked(self):
        game = SteamService._shortcut_game(
            {
                "appid": 123456,
                "AppName": "PCSX2 shortcut",
                "Exe": "/usr/bin/flatpak",
                "LaunchOptions": "run net.pcsx2.PCSX2 --fullscreen",
                "StartDir": "/home/deck/Games",
            }
        )

        self.assertEqual(game, {
            "appid": "123456",
            "name": "PCSX2 shortcut",
            "nonSteam": True,
            "isFlatpakShortcut": True,
        })

    def test_bare_flatpak_shortcut_is_marked(self):
        game = SteamService._shortcut_game(
            {
                "appid": 654321,
                "AppName": "Faugus shortcut",
                "Exe": '"flatpak"',
                "LaunchOptions": "run io.github.Faugus.faugus-launcher --game elliot",
            }
        )

        self.assertEqual(game, {
            "appid": "654321",
            "name": "Faugus shortcut",
            "nonSteam": True,
            "isFlatpakShortcut": True,
        })

    def test_emudeck_launcher_is_ordinary_non_steam_metadata(self):
        game = SteamService._shortcut_game(
            {
                "appid": 987654,
                "AppName": "1080 Snowboarding",
                "Exe": '"/home/deck/Emulation/tools/launchers/retroarch.sh" -L core rom.z64',
                "LaunchOptions": "",
            }
        )

        self.assertEqual(game, {
            "appid": "987654",
            "name": "1080 Snowboarding",
            "nonSteam": True,
        })

    def test_shortcut_rejects_invalid_identity(self):
        self.assertIsNone(SteamService._shortcut_game({"appid": 0, "AppName": "Bad"}))
        self.assertIsNone(SteamService._shortcut_game({"appid": 1, "AppName": ""}))
        self.assertIsNone(SteamService._shortcut_game("bad"))

    def test_shortcut_keys_are_case_insensitive(self):
        game = SteamService._shortcut_game({"AppId": -559038737, "appname": "Tool Game", "exe": "game"})

        self.assertEqual(game, {"appid": "3735928559", "name": "Tool Game", "nonSteam": True})

    def test_shortcut_without_appid_uses_steam_derived_appid(self):
        exe = '"/home/deck/Games/Game/Game.exe"'
        game = SteamService._shortcut_game({"AppName": "Game", "Exe": exe})

        expected = (zlib.crc32((exe + "Game").encode("utf-8")) & 0xFFFFFFFF) | 0x80000000
        self.assertEqual(game["appid"], str(expected))
        self.assertIsNone(SteamService._shortcut_game({"AppName": "No identity"}))

    def test_unterminated_shortcuts_file_keeps_the_entries_read(self):
        def string(key, value):
            return b"\x01" + key.encode() + b"\0" + value.encode() + b"\0"

        def int32(key, value):
            return b"\x02" + key.encode() + b"\0" + value.to_bytes(4, "little", signed=True)

        entry = b"\x00" + b"0\0" + int32("appid", -559038737) + string("AppName", "Game") + b"\x08"
        # No closing markers for the shortcuts map or the root.
        data = b"\x00shortcuts\0" + entry

        shortcuts = SteamService._read_shortcuts(data)["shortcuts"]

        self.assertEqual(SteamService._shortcut_game(shortcuts["0"])["appid"], "3735928559")


class LosslessScalingBranchTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.home = Path(self.tempdir.name) / "home" / "deck"
        self.steamapps = self.home / ".local/share/Steam/steamapps"
        (self.steamapps / "common/Lossless Scaling").mkdir(parents=True)
        self.service = SteamService(logger=Mock())
        self.service.user_home = self.home

    def tearDown(self):
        self.tempdir.cleanup()

    def _manifest(self, beta_key=None):
        user_config = f'\t\t"BetaKey"\t\t"{beta_key}"\n' if beta_key else ""
        (self.steamapps / "appmanifest_993090.acf").write_text(
            '"AppState"\n{\n\t"name"\t\t"Lossless Scaling"\n'
            f'\t"UserConfig"\n\t{{\n{user_config}\t}}\n}}\n',
            encoding="utf-8",
        )

    def _install_dll(self):
        (self.steamapps / "common/Lossless Scaling/Lossless.dll").write_text("dll", encoding="utf-8")

    def test_public_branch_with_dll_needs_no_switch(self):
        self._manifest()
        self._install_dll()

        status = self.service.get_branch_status()

        self.assertTrue(status["installed"])
        self.assertEqual(status["selected_branch"], "public")
        self.assertFalse(status["needs_switch"])

    def test_lsfg_vk_branch_with_dll_needs_no_switch(self):
        self._manifest("lsfg-vk")
        self._install_dll()

        status = self.service.get_branch_status()

        self.assertEqual(status["selected_branch"], "lsfg-vk")
        self.assertFalse(status["needs_switch"])

    def test_branch_without_dll_must_switch(self):
        self._manifest("lsfg-vk")

        status = self.service.get_branch_status()

        self.assertTrue(status["needs_switch"])
        self.assertEqual(status["target_branch"], "public")

    def test_finds_lossless_dll(self):
        self.assertIsNone(self.service.find_lossless_dll())
        dll = self.steamapps / "common/Lossless Scaling/Lossless.dll"
        dll.write_text("dll", encoding="utf-8")

        self.assertEqual(self.service.find_lossless_dll(), str(dll))


if __name__ == "__main__":
    unittest.main()
