"""
config.py — Configuration loader and validator for hid-daemon.

Reads mapping and settings from YAML, applying overrides from environment variables.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any


class BindingConfig:
    """Configuration for a specific key binding."""

    def __init__(
        self, mode: str, press_command: str | None, release_command: str | None
    ):
        if mode not in ("TOGGLE", "PTT"):
            raise ValueError(
                f"Invalid binding mode: '{mode}'. Must be 'TOGGLE' or 'PTT'."
            )
        self.mode = mode  # "TOGGLE" or "PTT"
        self.press_command = press_command
        self.release_command = release_command


class Config:
    """Runtime configuration containing device and binding options."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.device_path: str | None = None
        self.device_name: str | None = None
        self.reconnect_delay_s: float = 5.0
        self.bindings: Dict[str, BindingConfig] = {}

    def load_from_yaml(self) -> None:
        """Loads and parses settings and bindings from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found at: {self.config_path}"
            )

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:
            raise ValueError(
                f"Failed to parse YAML configuration: {exc}"
            ) from exc

        self.device_path = data.get("device_path")
        self.device_name = data.get("device_name")

        reconnect_delay = data.get("reconnect_delay_s")
        if reconnect_delay is not None:
            try:
                self.reconnect_delay_s = float(reconnect_delay)
                if self.reconnect_delay_s <= 0:
                    raise ValueError
            except ValueError:
                raise ValueError(
                    f"reconnect_delay_s must be a positive number, got: {reconnect_delay}"
                )

        bindings_data = data.get("bindings") or {}
        self.bindings = {}
        for key_name, binding in bindings_data.items():
            if not isinstance(binding, dict):
                raise ValueError(
                    f"Binding for key '{key_name}' must be a dictionary."
                )

            mode = binding.get("mode")
            if not mode:
                raise ValueError(
                    f"Missing 'mode' for key binding '{key_name}'."
                )

            press_command = binding.get("press")
            release_command = binding.get("release")

            # Keys are saved in uppercase for case-insensitive lookup
            self.bindings[key_name.upper()] = BindingConfig(
                mode=mode,
                press_command=press_command,
                release_command=release_command,
            )

    def apply_env_overrides(self) -> None:
        """Applies environment variables values over YAML loaded settings."""
        env_device_path = os.environ.get("HID_DEVICE_PATH", "").strip()
        if env_device_path:
            self.device_path = env_device_path

        env_device_name = os.environ.get("HID_DEVICE_NAME", "").strip()
        if env_device_name:
            self.device_name = env_device_name

        env_reconnect_delay = os.environ.get("HID_RECONNECT_DELAY_S", "").strip()
        if env_reconnect_delay:
            try:
                delay = float(env_reconnect_delay)
                if delay <= 0:
                    raise ValueError
                self.reconnect_delay_s = delay
            except ValueError:
                raise ValueError(
                    f"HID_RECONNECT_DELAY_S must be a positive float, got: '{env_reconnect_delay}'"
                )


def load_config() -> Config:
    """
    Load configuration from the path in environment variable or default location.
    """
    config_path_str = os.environ.get("HID_CONFIG_PATH", "").strip()
    if config_path_str:
        config_path = Path(config_path_str)
    else:
        # Default: config/hid-daemon.yaml relative to current working directory or relative to the src folder
        config_path = (
            Path(__file__).resolve().parent.parent / "config" / "hid-daemon.yaml"
        )

    config = Config(config_path)
    config.load_from_yaml()
    config.apply_env_overrides()
    return config
