import io
import json
import sys
import tarfile
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

from lsfg_vk.flatpak_service import FlatpakService


class FlatpakServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.home = Path(self.tempdir.name) / "home" / "deck"
        self.home.mkdir(parents=True)
        self.service = FlatpakService()
        self.service.user_home = self.home
        self.service.config_dir = self.home / ".config/jedi-lsfg-vk"
        self.service.config_file_path = self.service.config_dir / "conf.toml"
        self.service.ownership_path.parent.mkdir(parents=True, exist_ok=True)
        self.bundle_archive = self.home / "bundles.tar"
        with tarfile.open(self.bundle_archive, "w") as archive:
            for branch in FlatpakService.SUPPORTED_RUNTIMES:
                data = f"bundle {branch}".encode()
                member = tarfile.TarInfo(f"./{FlatpakService.EXTENSION_ID}-{branch}.flatpak")
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        self.service._bundle_archive = Mock(return_value=self.bundle_archive)
        self.service.check_flatpak_available = Mock(return_value=True)
        self.service._run_flatpak_command = Mock(side_effect=self._run_flatpak_command)
        self.runtime_ref = "org.freedesktop.Platform/x86_64/24.08"
        self.runtime_metadata = ""
        self.user_branches = set()
        self.system_branches = set()
        self.apps = {"com.example.Game": "Example Game"}
        self.dll_dir = self.home / ".local/share/Steam/steamapps/common/Lossless Scaling"
        self.service._dll_directory = Mock(return_value=self.dll_dir)

    def tearDown(self):
        self.tempdir.cleanup()

    @staticmethod
    def _result(stdout="", returncode=0, stderr=""):
        return types.SimpleNamespace(stdout=stdout, returncode=returncode, stderr=stderr)

    @staticmethod
    def _extension_line(branch):
        return f"org.freedesktop.Platform.VulkanLayer.makorender\tx86_64\t{branch}\n"

    @staticmethod
    def _parse_override(content):
        section = None
        filesystems = []
        unset_environment = []
        environment = {}
        other = []
        for raw in content.splitlines():
            line = raw.strip()
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                continue
            key, separator, value = line.partition("=")
            if not separator:
                continue
            if section == "Context" and key == "filesystems":
                filesystems.extend(item for item in value.split(";") if item)
            elif section == "Context" and key == "unset-environment":
                unset_environment.extend(item for item in value.split(";") if item)
            elif section == "Environment":
                environment[key] = value
            else:
                other.append((section, key, value))
        return filesystems, unset_environment, environment, other

    @staticmethod
    def _serialize_override(filesystems, unset_environment, environment):
        lines = ["[Context]"]
        if filesystems:
            lines.append("filesystems=" + ";".join(filesystems) + ";")
        if unset_environment:
            lines.append("unset-environment=" + ";".join(unset_environment) + ";")
        if environment:
            lines.append("")
            lines.append("[Environment]")
            lines.extend(f"{key}={value}" for key, value in environment.items())
        return "\n".join(lines) + "\n"

    def _apply_override(self, args):
        app_id = args[-1]
        path = self.service._override_path(app_id)
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        filesystems, unset_environment, environment, _ = self._parse_override(content)
        for arg in args[2:-1]:
            if arg.startswith("--filesystem="):
                value = arg.split("=", 1)[1]
                if value not in filesystems:
                    filesystems.append(value)
            elif arg.startswith("--env="):
                key, value = arg.split("=", 1)[1].split("=", 1)
                environment[key] = value
                if key in unset_environment:
                    unset_environment.remove(key)
            elif arg.startswith("--unset-env="):
                key = arg.split("=", 1)[1]
                environment.pop(key, None)
                if key not in unset_environment:
                    unset_environment.append(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            self._serialize_override(filesystems, unset_environment, environment),
            encoding="utf-8",
        )
        return self._result()

    def _run_flatpak_command(self, args, **_kwargs):
        if args[:2] == ["info", "--show-runtime"]:
            return self._result(self.runtime_ref + "\n")
        if args[:2] == ["info", "--show-metadata"]:
            return self._result(self.runtime_metadata)
        if args[:2] == ["list", "--app"]:
            return self._result("".join(f"{name}\t{app_id}\n" for app_id, name in self.apps.items()))
        if args[0] == "list":
            branches = self.user_branches if "--user" in args else self.system_branches
            return self._result("".join(self._extension_line(branch) for branch in sorted(branches)))
        if args[0] == "install":
            bundle = Path(args[-1])
            self.assertTrue(bundle.read_text(encoding="utf-8").startswith("bundle "))
            self.user_branches.add(bundle.name.removesuffix(".flatpak").rsplit("-", 1)[-1])
            return self._result()
        if args[0] == "uninstall":
            self.user_branches.discard(args[-1].rsplit("/", 1)[-1])
            return self._result()
        if args[:3] == ["override", "--user", "--show"]:
            path = self.service._override_path(args[-1])
            return self._result(path.read_text(encoding="utf-8") if path.exists() else "")
        if args[:3] == ["override", "--user", "--reset"]:
            self.service._override_path(args[-1]).unlink(missing_ok=True)
            return self._result()
        if args[:2] == ["override", "--user"]:
            return self._apply_override(args)
        raise AssertionError(f"Unexpected Flatpak command: {args}")

    def test_resolves_freedesktop_and_derived_runtimes(self):
        runtime, branch = self.service._resolve_runtime("com.example.Game")
        self.assertEqual(runtime, self.runtime_ref)
        self.assertEqual(branch, "24.08")

        self.runtime_ref = "org.kde.Platform/x86_64/6.10"
        self.runtime_metadata = "[Extension org.freedesktop.Platform.VulkanLayer]\nversion=25.08\n"
        runtime, branch = self.service._resolve_runtime("com.example.Game")
        self.assertEqual(runtime, self.runtime_ref)
        self.assertEqual(branch, "25.08")

    def test_clean_env_targets_deck_user_session_bus(self):
        env = self.service._clean_env()
        user_id = self.home.stat().st_uid
        self.assertEqual(env["XDG_RUNTIME_DIR"], f"/run/user/{user_id}")
        self.assertEqual(env["DBUS_SESSION_BUS_ADDRESS"], f"unix:path=/run/user/{user_id}/bus")

    def test_prepare_app_installs_runtime_and_persists_narrow_override(self):
        response = self.service.prepare_app("com.example.Game")

        self.assertTrue(response["success"])
        self.assertTrue(response["prepared"])
        self.assertTrue(response["owned"])
        self.assertEqual(response["runtime_branch"], "24.08")
        self.assertEqual(self.user_branches, {"24.08"})
        install_calls = [
            call.args[0]
            for call in self.service._run_flatpak_command.call_args_list
            if call.args[0][0] == "install"
        ]
        self.assertEqual(len(install_calls), 1)
        self.assertEqual(install_calls[0][:3], ["install", "--user", "--noninteractive"])
        self.assertTrue(install_calls[0][-1].endswith("org.freedesktop.Platform.VulkanLayer.makorender-24.08.flatpak"))
        status = self.service._app_override_status("com.example.Game")
        self.assertTrue(status["prepared"])
        _, unset_environment, environment, _ = self._parse_override(
            self.service._override_path("com.example.Game").read_text(encoding="utf-8")
        )
        content = self.service._override_path("com.example.Game").read_text(encoding="utf-8")
        self.assertIn(str(self.service.config_dir) + ":rw", content)
        self.assertIn(str(self.dll_dir) + ":ro", content)
        self.assertEqual(environment["MAKO_CONFIG"], str(self.service.config_file_path))
        self.assertEqual(environment["ENABLE_MAKO"], "1")
        self.assertEqual(environment["DISABLE_LSFG"], "1")
        self.assertEqual(environment["DISABLE_LSFGVK"], "1")
        self.assertEqual(environment["DISABLE_GAMESCOPE_WSI"], "1")
        self.assertEqual(environment["VK_IMPLICIT_LAYER_PATH"], FlatpakService.IMPLICIT_LAYER_DIR)
        self.assertIn("ENABLE_GAMESCOPE_WSI", unset_environment)
        self.assertIn("VK_ADD_IMPLICIT_LAYER_PATH", unset_environment)
        state = json.loads(self.service.ownership_path.read_text(encoding="utf-8"))
        self.assertEqual(state["plugin_owned_branches"], ["24.08"])
        self.assertEqual(state["prepared_apps"]["com.example.Game"], {})

    def test_prepare_is_idempotent(self):
        first = self.service.prepare_app("com.example.Game")
        first_content = self.service._override_path("com.example.Game").read_bytes()
        second = self.service.prepare_app("com.example.Game")

        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(first_content, self.service._override_path("com.example.Game").read_bytes())
        install_calls = [call for call in self.service._run_flatpak_command.call_args_list if call.args[0][0] == "install"]
        self.assertEqual(len(install_calls), 1)

    def test_user_extension_from_mako_decky_is_used_but_not_owned(self):
        self.user_branches = {"24.08"}

        response = self.service.install_extension("24.08")

        self.assertTrue(response["success"])
        commands = [call.args[0][0] for call in self.service._run_flatpak_command.call_args_list]
        self.assertNotIn("install", commands)
        self.assertNotIn("uninstall", commands)
        self.assertFalse(self.service.ownership_path.exists())

    def test_owned_extension_is_not_reinstalled_in_a_new_session(self):
        self.assertTrue(self.service.install_extension("24.08")["success"])
        self.service._verified_branches.clear()

        response = self.service.install_extension("24.08")

        self.assertTrue(response["success"])
        installs = [call for call in self.service._run_flatpak_command.call_args_list if call.args[0][0] == "install"]
        self.assertEqual(len(installs), 1)
        state = json.loads(self.service.ownership_path.read_text(encoding="utf-8"))
        self.assertEqual(state["plugin_owned_branches"], ["24.08"])

    def test_bundle_download_failure_leaves_no_partial_file(self):
        service = FlatpakService()
        service.user_home = self.home
        archive = service.bundle_cache_dir / "MAKO-Renderer-v4.6.0-flatpaks.tar.xz"
        archive.parent.mkdir(parents=True)
        archive.write_text("corrupt", encoding="utf-8")
        failed = types.SimpleNamespace(returncode=22, stdout="", stderr="curl: (22) 404")

        with patch("lsfg_vk.flatpak_service.subprocess.run", return_value=failed):
            with self.assertRaises(OSError):
                service._bundle_archive()

        self.assertFalse(archive.with_name(archive.name + ".part").exists())

    def test_preinstalled_runtime_is_not_owned(self):
        self.system_branches = {"24.08"}
        response = self.service.prepare_app("com.example.Game")

        self.assertTrue(response["success"])
        state = json.loads(self.service.ownership_path.read_text(encoding="utf-8"))
        self.assertEqual(state["plugin_owned_branches"], [])
        self.assertIn("com.example.Game", state["prepared_apps"])

    def test_prepare_resets_existing_override(self):
        self.system_branches = {"24.08"}
        path = self.service._override_path("com.example.Game")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[Context]\nfilesystems=~/Documents;\n\n[Environment]\nFOO=bar\n", encoding="utf-8")

        response = self.service.prepare_app("com.example.Game")
        content = path.read_text(encoding="utf-8")

        self.assertTrue(response["success"])
        self.assertTrue(response["owned"])
        self.assertNotIn("~/Documents", content)
        self.assertNotIn("FOO=bar", content)
        self.assertIn("MAKO_CONFIG=", content)

    def test_remove_deletes_override_created_by_plugin(self):
        self.system_branches = {"24.08"}
        self.assertTrue(self.service.prepare_app("com.example.Game")["success"])
        path = self.service._override_path("com.example.Game")
        self.assertTrue(path.exists())

        response = self.service.remove_app_override("com.example.Game")

        self.assertTrue(response["success"])
        self.assertFalse(path.exists())
        self.assertFalse(self.service.ownership_path.exists())

    def test_remove_resets_external_changes(self):
        self.system_branches = {"24.08"}
        self.assertTrue(self.service.prepare_app("com.example.Game")["success"])
        path = self.service._override_path("com.example.Game")
        with path.open("a", encoding="utf-8") as handle:
            handle.write("EXTERNAL=1\n")

        response = self.service.remove_app_override("com.example.Game")

        self.assertTrue(response["success"])
        self.assertFalse(path.exists())
        self.assertFalse(self.service.ownership_path.exists())

    def test_legacy_ownership_fields_are_accepted(self):
        self.service.ownership_path.write_text(
            json.dumps({
                "version": 2,
                "plugin_owned_branches": [],
                "prepared_apps": {"com.example.Game": {"override_existed": True, "managed_sha256": "old"}},
            }),
            encoding="utf-8",
        )

        self.assertIn("com.example.Game", self.service._read_state()["prepared_apps"])

    def test_full_cleanup_removes_only_owned_state(self):
        self.system_branches = {"23.08"}
        self.assertTrue(self.service.prepare_app("com.example.Game")["success"])
        self.assertEqual(self.user_branches, {"24.08"})

        response = self.service.remove_plugin_owned_environment()

        self.assertTrue(response["success"])
        self.assertEqual(response["removed_apps"], ["com.example.Game"])
        self.assertEqual(response["removed_branches"], ["24.08"])
        self.assertEqual(self.user_branches, set())
        self.assertEqual(self.system_branches, {"23.08"})
        self.assertFalse(self.service.ownership_path.exists())

    def test_corrupt_ownership_metadata_fails_closed(self):
        self.service.ownership_path.write_text("{not-json", encoding="utf-8")

        response = self.service.remove_plugin_owned_environment()

        self.assertFalse(response["success"])
        self.assertEqual(self.service._run_flatpak_command.call_count, 0)


if __name__ == "__main__":
    unittest.main()
