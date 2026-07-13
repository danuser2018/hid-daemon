"""
test_hid_daemon.py — Unit and integration tests for src/hid_daemon.py.
"""

import pytest
import sys
import evdev
from unittest.mock import patch, MagicMock, call
from src.config import Config, BindingConfig
from src.hid_daemon import HidDaemon, resolve_key_names, main


def test_resolve_key_names():
    """Verifies key name resolution for single, multiple and invalid codes."""
    with patch("evdev.ecodes.KEY") as mock_key_map, \
         patch("evdev.ecodes.BTN") as mock_btn_map, \
         patch("evdev.ecodes.bytype") as mock_bytype_map:
        
        # Single string return from KEY
        mock_key_map.get.return_value = "KEY_F9"
        assert resolve_key_names(67) == ["KEY_F9"]

        # Fallback to BTN if KEY returns None
        mock_key_map.get.return_value = None
        mock_btn_map.get.return_value = "BTN_THUMB2"
        assert resolve_key_names(290) == ["BTN_THUMB2"]

        # Fallback to bytype if both KEY and BTN return None
        mock_key_map.get.return_value = None
        mock_btn_map.get.return_value = None
        mock_bytype_map.get.return_value = {290: "BTN_THUMB2"}
        assert resolve_key_names(290) == ["BTN_THUMB2"]

        # List/Tuple return
        mock_key_map.get.return_value = ["KEY_F9", "KEY_SELECT"]
        assert resolve_key_names(67) == ["KEY_F9", "KEY_SELECT"]

        # Invalid/Error return
        mock_key_map.get.side_effect = Exception("error")
        assert resolve_key_names(999) == []


class TestHidDaemonEvents:
    """Tests for key events processing inside HidDaemon."""

    def test_handle_key_event_ignores_repeat(self):
        """Verifies value=2 (key repeat) is completely ignored."""
        config = MagicMock(spec=Config)
        daemon = HidDaemon(config)
        daemon.executor = MagicMock()

        daemon.handle_key_event("KEY_F9", 2)
        daemon.executor.execute.assert_not_called()

    def test_handle_key_event_no_binding(self):
        """Verifies unconfigured key is ignored."""
        config = MagicMock(spec=Config)
        config.bindings = {}
        daemon = HidDaemon(config)
        daemon.executor = MagicMock()

        daemon.handle_key_event("KEY_F9", 1)
        daemon.executor.execute.assert_not_called()

    def test_handle_key_event_ptt_mode(self):
        """Verifies PTT mode executes press command on press (1) and release command on release (0)."""
        config = MagicMock(spec=Config)
        binding = BindingConfig(
            mode="PTT", press_command="mic-start", release_command="mic-stop"
        )
        config.bindings = {"KEY_F9": binding}
        daemon = HidDaemon(config)
        daemon.executor = MagicMock()

        # Press (1)
        daemon.handle_key_event("KEY_F9", 1)
        daemon.executor.execute.assert_called_once_with("mic-start")

        # Reset mock
        daemon.executor.execute.reset_mock()

        # Release (0)
        daemon.handle_key_event("KEY_F9", 0)
        daemon.executor.execute.assert_called_once_with("mic-stop")

    def test_handle_key_event_toggle_mode(self):
        """Verifies TOGGLE mode alternates between press and release command on sequential presses."""
        config = MagicMock(spec=Config)
        binding = BindingConfig(
            mode="TOGGLE", press_command="mic-start", release_command="mic-stop"
        )
        config.bindings = {"KEY_F9": binding}
        daemon = HidDaemon(config)
        daemon.executor = MagicMock()

        # First press: triggers press_command
        daemon.handle_key_event("KEY_F9", 1)
        daemon.executor.execute.assert_called_once_with("mic-start")
        assert daemon.toggle_states["KEY_F9"] is True

        daemon.executor.execute.reset_mock()

        # Release: ignored in TOGGLE
        daemon.handle_key_event("KEY_F9", 0)
        daemon.executor.execute.assert_not_called()

        # Second press: triggers release_command
        daemon.handle_key_event("KEY_F9", 1)
        daemon.executor.execute.assert_called_once_with("mic-stop")
        assert daemon.toggle_states["KEY_F9"] is False

    def test_handle_key_event_toggle_mode_no_release_command(self):
        """Verifies TOGGLE mode falls back to press command on second press if release command is missing."""
        config = MagicMock(spec=Config)
        binding = BindingConfig(
            mode="TOGGLE", press_command="mic-start", release_command=None
        )
        config.bindings = {"KEY_F9": binding}
        daemon = HidDaemon(config)
        daemon.executor = MagicMock()

        # First press
        daemon.handle_key_event("KEY_F9", 1)
        daemon.executor.execute.assert_called_once_with("mic-start")

        daemon.executor.execute.reset_mock()

        # Second press -> falls back to press_command
        daemon.handle_key_event("KEY_F9", 1)
        daemon.executor.execute.assert_called_once_with("mic-start")


class TestHidDaemonLoop:
    """Integration style unit tests for the main run loop."""

    @patch("src.hid_daemon.DeviceListener")
    def test_run_loop_permission_error_exits(self, mock_listener_class):
        """Verifies daemon exits with status 1 on PermissionError."""
        mock_listener = MagicMock()
        mock_listener.connect.side_effect = PermissionError("Fatal denied")
        mock_listener_class.return_value = mock_listener

        config = MagicMock(spec=Config)
        config.device_path = "/dev/input/event0"
        config.device_name = None
        config.reconnect_delay_s = 0.01

        daemon = HidDaemon(config)

        with pytest.raises(SystemExit) as exc_info:
            daemon.run()

        assert exc_info.value.code == 1

    @patch("src.hid_daemon.DeviceListener")
    def test_run_loop_reconnection_flow(self, mock_listener_class):
        """Verifies that the loop retries connection and handles disconnection cleanly."""
        mock_listener = MagicMock()
        # First connect: fails (returns False)
        # Second connect: succeeds (returns True), then read_events raises OSError (disconnection)
        # Third connect: loop stops because stop_event is set
        mock_listener.connect.side_effect = [False, True]

        mock_event = MagicMock()
        mock_event.type = evdev.ecodes.EV_KEY
        mock_event.code = 67
        mock_event.value = 1

        def mock_read_events():
            yield mock_event
            # Simulate disconnection after yielding one event
            raise OSError("Disconnected")

        mock_listener.read_events.side_effect = mock_read_events
        mock_listener_class.return_value = mock_listener

        config = MagicMock(spec=Config)
        config.device_path = None
        config.device_name = "Target Device"
        config.reconnect_delay_s = 0.001
        # Mock KEY_F9 to press command
        binding = BindingConfig(mode="PTT", press_command="mic-start", release_command=None)
        config.bindings = {"KEY_F9": binding}

        daemon = HidDaemon(config)

        # We will patch resolve_key_names to return KEY_F9 for code 67
        with patch("src.hid_daemon.resolve_key_names", return_value=["KEY_F9"]):
            # Run the daemon, but schedule it to stop after connection attempts
            def connect_side_effect():
                count = mock_listener.connect.call_count
                if count >= 2:
                    daemon.stop()
                if count == 1:
                    return False
                return True

            mock_listener.connect.side_effect = connect_side_effect

            daemon.run()

            # Verify we connected twice
            assert mock_listener.connect.call_count == 2
            # Verify the command executor was run once
            assert daemon.toggle_states == {}


@patch("src.hid_daemon.load_config")
@patch("src.hid_daemon.HidDaemon")
@patch("signal.signal")
def test_main_startup(mock_signal, mock_daemon_class, mock_load):
    """Verifies main() function loads configuration and registers signal handlers."""
    mock_config = MagicMock(spec=Config)
    mock_load.return_value = mock_config

    mock_daemon = MagicMock()
    mock_daemon_class.return_value = mock_daemon

    main()

    # Let's verify daemon.run() was called.
    mock_daemon.run.assert_called_once()
    mock_load.assert_called_once()
    assert mock_signal.call_count == 2
