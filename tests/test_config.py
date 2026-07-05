"""
test_config.py — Unit tests for src/config.py.
"""

import os
import pytest
import yaml
from pathlib import Path
from src.config import load_config, Config, BindingConfig


def test_binding_config_valid():
    """Validates that BindingConfig initializes with correct parameters."""
    binding = BindingConfig(
        mode="TOGGLE", press_command="mic-start", release_command="mic-stop"
    )
    assert binding.mode == "TOGGLE"
    assert binding.press_command == "mic-start"
    assert binding.release_command == "mic-stop"


def test_binding_config_invalid_mode():
    """Validates that BindingConfig raises ValueError on invalid mode."""
    with pytest.raises(ValueError, match="Invalid binding mode"):
        BindingConfig(
            mode="INVALID", press_command="start", release_command="stop"
        )


class TestConfigLoad:
    """Tests for Config class loading and overrides."""

    def test_missing_file_raises_error(self, tmp_path):
        """Verifies that FileNotFoundError is raised if YAML file does not exist."""
        non_existent = tmp_path / "missing.yaml"
        cfg = Config(non_existent)
        with pytest.raises(FileNotFoundError):
            cfg.load_from_yaml()

    def test_invalid_yaml_raises_error(self, tmp_path):
        """Verifies that ValueError is raised if YAML is malformed."""
        invalid_file = tmp_path / "invalid.yaml"
        with open(invalid_file, "w", encoding="utf-8") as f:
            f.write("invalid: yaml: : content")

        cfg = Config(invalid_file)
        with pytest.raises(ValueError, match="Failed to parse YAML"):
            cfg.load_from_yaml()

    def test_valid_yaml_loading(self, tmp_path):
        """Verifies parsing of standard YAML properties."""
        yaml_content = {
            "device_path": "/dev/input/event1",
            "device_name": "My Device",
            "reconnect_delay_s": 3.5,
            "bindings": {
                "KEY_F9": {
                    "mode": "TOGGLE",
                    "press": "mic-start",
                    "release": "mic-stop",
                },
                "key_a": {"mode": "PTT", "press": "run-a"},
            },
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_content, f)

        cfg = Config(config_file)
        cfg.load_from_yaml()

        assert cfg.device_path == "/dev/input/event1"
        assert cfg.device_name == "My Device"
        assert cfg.reconnect_delay_s == 3.5
        assert len(cfg.bindings) == 2
        assert "KEY_F9" in cfg.bindings
        assert "KEY_A" in cfg.bindings  # case-insensitive key names saved in uppercase
        assert cfg.bindings["KEY_F9"].mode == "TOGGLE"
        assert cfg.bindings["KEY_F9"].press_command == "mic-start"
        assert cfg.bindings["KEY_F9"].release_command == "mic-stop"
        assert cfg.bindings["KEY_A"].mode == "PTT"
        assert cfg.bindings["KEY_A"].press_command == "run-a"
        assert cfg.bindings["KEY_A"].release_command is None

    def test_invalid_reconnect_delay_in_yaml(self, tmp_path):
        """Verifies that invalid reconnect_delay_s values in YAML raise ValueError."""
        yaml_content = {"reconnect_delay_s": -1.0}
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_content, f)

        cfg = Config(config_file)
        with pytest.raises(ValueError, match="reconnect_delay_s must be a positive number"):
            cfg.load_from_yaml()

    def test_invalid_binding_format_in_yaml(self, tmp_path):
        """Verifies that non-dictionary bindings raise ValueError."""
        yaml_content = {"bindings": {"KEY_F9": "not-a-dict"}}
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_content, f)

        cfg = Config(config_file)
        with pytest.raises(ValueError, match="must be a dictionary"):
            cfg.load_from_yaml()

    def test_missing_mode_in_yaml(self, tmp_path):
        """Verifies that a binding without mode raises ValueError."""
        yaml_content = {"bindings": {"KEY_F9": {"press": "mic-start"}}}
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_content, f)

        cfg = Config(config_file)
        with pytest.raises(ValueError, match="Missing 'mode'"):
            cfg.load_from_yaml()

    def test_apply_env_overrides(self, tmp_path, monkeypatch):
        """Verifies that environment variables successfully override YAML values."""
        yaml_content = {
            "device_path": "/dev/input/event1",
            "device_name": "My Device",
            "reconnect_delay_s": 3.5,
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_content, f)

        monkeypatch.setenv("HID_DEVICE_PATH", "/dev/input/event99")
        monkeypatch.setenv("HID_DEVICE_NAME", "Override Device")
        monkeypatch.setenv("HID_RECONNECT_DELAY_S", "7.5")

        cfg = Config(config_file)
        cfg.load_from_yaml()
        cfg.apply_env_overrides()

        assert cfg.device_path == "/dev/input/event99"
        assert cfg.device_name == "Override Device"
        assert cfg.reconnect_delay_s == 7.5

    def test_apply_invalid_env_reconnect_delay(self, tmp_path, monkeypatch):
        """Verifies that invalid environment variable reconnect delay raises ValueError."""
        yaml_content = {"reconnect_delay_s": 3.5}
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_content, f)

        monkeypatch.setenv("HID_RECONNECT_DELAY_S", "invalid-float")
        cfg = Config(config_file)
        cfg.load_from_yaml()
        with pytest.raises(ValueError, match="HID_RECONNECT_DELAY_S must be a positive float"):
            cfg.apply_env_overrides()

    def test_apply_negative_env_reconnect_delay(self, tmp_path, monkeypatch):
        """Verifies that negative environment variable reconnect delay raises ValueError."""
        yaml_content = {"reconnect_delay_s": 3.5}
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_content, f)

        monkeypatch.setenv("HID_RECONNECT_DELAY_S", "-2.0")
        cfg = Config(config_file)
        cfg.load_from_yaml()
        with pytest.raises(ValueError, match="HID_RECONNECT_DELAY_S must be a positive float"):
            cfg.apply_env_overrides()


def test_load_config_helper(tmp_path, monkeypatch):
    """Verifies that load_config uses HUD_CONFIG_PATH env var to locate config."""
    yaml_content = {
        "device_path": "/dev/input/event0",
        "device_name": "Test Device",
        "reconnect_delay_s": 5.0,
    }
    config_file = tmp_path / "custom-config.yaml"
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(yaml_content, f)

    monkeypatch.setenv("HID_CONFIG_PATH", str(config_file))
    cfg = load_config()

    assert cfg.config_path == config_file
    assert cfg.device_path == "/dev/input/event0"
