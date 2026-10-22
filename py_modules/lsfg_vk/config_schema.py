"""Adapter between the plugin's profile model and MAKO Renderer's v2 conf.toml.

The plugin exposes a single frame generation control, the target FPS. Every
other Adaptive Frame Generation setting is derived from it so profiles always
use the same policy:

* the real (base) framerate is capped at half of the target, so the game
  renders at most target/2 frames and the GPU keeps headroom for generation;
* Fractional Adaptive fills the gap to the target with a changing mix of real
  and generated frames, so the effective multiplier moves smoothly through
  2.1x, 2.2x, 2.3x... instead of jumping between integer rungs;
* generation never exceeds 4x.
"""

import json
import tomllib
from typing import Any, Dict, TypedDict

ConfigurationData = Dict[str, Any]


class ProfileData(TypedDict):
    profiles: Dict[str, Dict[str, Any]]
    global_config: Dict[str, Any]


class UnsupportedConfigurationVersion(ValueError):
    def __init__(self, version: Any):
        self.version = version
        super().__init__("unsupported configuration version")


TARGET_FPS_MIN = 30
TARGET_FPS_MAX = 240
ADAPTIVE_MAX_MULTIPLIER = 4

PROFILE_DEFAULTS: Dict[str, Any] = {
    "target_fps": 60,
    "flow_scale": 0.8,
    # The lighter model is the cheaper choice on handhelds; it stays a
    # per-profile toggle for games where quality matters more.
    "performance_mode": True,
    "preserve_swapchain_image_count": False,
}
GLOBAL_DEFAULTS: Dict[str, Any] = {"dll": "", "no_fp16": False}


def base_fps_cap(target_fps: int) -> int:
    """Real-frame cap for a target: half of it, rounded down.

    Rounding down keeps 2x generation at or below the target, so a game that
    reaches its cap never forces Adaptive below its 2x floor.
    """
    return target_fps // 2


def adaptive_settings(target_fps: int) -> Dict[str, Any]:
    """Fixed MAKO Adaptive policy derived from the target FPS."""
    return {
        "frame_generation_provisioned": True,
        "frame_generation_enabled": True,
        "adaptive": True,
        "target_fps": target_fps,
        "base_fps_cap": base_fps_cap(target_fps),
        "adaptive_max_multiplier": ADAPTIVE_MAX_MULTIPLIER,
        # Off selects Fractional Adaptive; the manual base cap above provides
        # the half-target base without Steady's integer-only rungs.
        "adaptive_auto_base_fps_cap": False,
        "adaptive_fractional_real_frame_priority": "auto",
        # Smooth Cadence can hold an integer multiplier and documents extra
        # input lag; the fractional ramp is the requested behaviour.
        "adaptive_stable_cadence": False,
        "adaptive_target_refresh_rate": False,
        # Cadence probes temporarily drop generated frames and can hitch.
        "dynamic_cadence_recovery": False,
        "gpu_headroom_percent": 0,
    }


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        return json.dumps(value)
    return str(value)


class ConfigurationManager:
    @staticmethod
    def is_discardable_legacy_version(version: Any) -> bool:
        return version is None or version == "1" or (
            isinstance(version, (int, float))
            and not isinstance(version, bool)
            and version < 2
        )

    @staticmethod
    def get_defaults() -> Dict[str, Any]:
        return {**GLOBAL_DEFAULTS, **PROFILE_DEFAULTS}

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
        result = {**PROFILE_DEFAULTS, **GLOBAL_DEFAULTS}
        result.update({key: value for key, value in config.items() if key in result})
        target_fps = result["target_fps"]
        if isinstance(target_fps, bool):
            raise ValueError("target_fps must be an integer")
        result["target_fps"] = int(target_fps)
        if not TARGET_FPS_MIN <= result["target_fps"] <= TARGET_FPS_MAX:
            raise ValueError(f"target_fps must be between {TARGET_FPS_MIN} and {TARGET_FPS_MAX}")
        result["flow_scale"] = round(float(result["flow_scale"]), 2)
        if not 0.25 <= result["flow_scale"] <= 1.0:
            raise ValueError("flow_scale must be between 0.25 and 1.0")
        for name in ("no_fp16", "performance_mode", "preserve_swapchain_image_count"):
            result[name] = bool(result[name])
        result["dll"] = str(result["dll"] or "")
        return result

    @staticmethod
    def generate_toml_content_multi_profile(profile_data: ProfileData) -> str:
        global_config = {**GLOBAL_DEFAULTS, **profile_data.get("global_config", {})}
        lines = ["version = 2", "", "[global]"]
        if global_config["dll"]:
            lines.append(f"dll = {_toml_value(global_config['dll'])}")
        lines.append(f"allow_fp16 = {_toml_value(not bool(global_config['no_fp16']))}")
        for name, raw in sorted(profile_data["profiles"].items()):
            config = ConfigurationManager.validate_config({**raw, **global_config})
            lines.extend(["", "[[profile]]", f"name = {_toml_value(name)}"])
            lines.extend(
                f"{key} = {_toml_value(value)}"
                for key, value in adaptive_settings(config["target_fps"]).items()
            )
            lines.extend([
                f"flow_scale = {config['flow_scale']}",
                f"performance_mode = {_toml_value(config['performance_mode'])}",
                "swapchain_image_count_compatibility = "
                + _toml_value(config["preserve_swapchain_image_count"]),
            ])
        return "\n".join(lines) + "\n"

    @staticmethod
    def parse_toml_content_multi_profile(content: str) -> ProfileData:
        data = tomllib.loads(content)
        version = data.get("version")
        if version != 2:
            raise UnsupportedConfigurationVersion(version)
        raw_global = data.get("global", {})
        global_config = {
            "dll": str(raw_global.get("dll", "") or ""),
            "no_fp16": not bool(raw_global.get("allow_fp16", True)),
        }
        profiles: Dict[str, Dict[str, Any]] = {}
        for profile in data.get("profile", []):
            name = str(profile.get("name", ""))
            if not name:
                continue
            raw = {
                key: profile[key]
                for key in ("target_fps", "flow_scale", "performance_mode")
                if key in profile
            }
            if "swapchain_image_count_compatibility" in profile:
                raw["preserve_swapchain_image_count"] = profile["swapchain_image_count_compatibility"]
            profiles[name] = ConfigurationManager.validate_config({**raw, **global_config})
        return {"profiles": profiles, "global_config": global_config}
