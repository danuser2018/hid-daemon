"""
test_listener.py — Unit tests for src/listener.py.
"""

import pytest
from unittest.mock import patch, MagicMock
from src.listener import DeviceListener


class TestDeviceListener:
    """Tests for DeviceListener class."""

    def test_find_device_by_name_no_name(self):
        """Verifies that find_device_by_name returns None if device_name is not configured."""
        listener = DeviceListener(device_path=None, device_name=None)
        assert listener.find_device_by_name() is None

    @patch("evdev.list_devices")
    def test_find_device_by_name_permission_denied_listing(self, mock_list):
        """Verifies that PermissionError is propagated when listing devices fails."""
        mock_list.side_effect = PermissionError("Access denied")
        listener = DeviceListener(device_path=None, device_name="Test Device")
        with pytest.raises(PermissionError, match="Access denied"):
            listener.find_device_by_name()

    @patch("evdev.InputDevice")
    @patch("evdev.list_devices")
    def test_find_device_by_name_success(self, mock_list, mock_input_device):
        """Verifies that a matching device name is correctly resolved to its path."""
        mock_list.return_value = ["/dev/input/event0", "/dev/input/event1"]

        mock_dev0 = MagicMock()
        mock_dev0.name = "Wrong Device"
        mock_dev0.path = "/dev/input/event0"

        mock_dev1 = MagicMock()
        mock_dev1.name = "Target Device"
        mock_dev1.path = "/dev/input/event1"

        # Side effect to return different devices based on path
        def side_effect(path):
            if path == "/dev/input/event0":
                return mock_dev0
            return mock_dev1

        mock_input_device.side_effect = side_effect

        listener = DeviceListener(device_path=None, device_name="Target Device")
        resolved_path = listener.find_device_by_name()

        assert resolved_path == "/dev/input/event1"

    @patch("evdev.InputDevice")
    @patch("evdev.list_devices")
    def test_find_device_by_name_multiple_matches(
        self, mock_list, mock_input_device
    ):
        """Verifies that if multiple devices match, the first one is selected."""
        mock_list.return_value = ["/dev/input/event0", "/dev/input/event1"]

        mock_dev0 = MagicMock()
        mock_dev0.name = "Target Device"
        mock_dev0.path = "/dev/input/event0"

        mock_dev1 = MagicMock()
        mock_dev1.name = "Target Device"
        mock_dev1.path = "/dev/input/event1"

        mock_input_device.side_effect = lambda path: (
            mock_dev0 if path == "/dev/input/event0" else mock_dev1
        )

        listener = DeviceListener(device_path=None, device_name="Target Device")
        resolved_path = listener.find_device_by_name()

        assert resolved_path == "/dev/input/event0"

    @patch("evdev.InputDevice")
    @patch("evdev.list_devices")
    def test_find_device_by_name_permission_denied_accessing_device(
        self, mock_list, mock_input_device
    ):
        """Verifies that PermissionError is propagated when accessing a specific device file fails."""
        mock_list.return_value = ["/dev/input/event0"]
        mock_input_device.side_effect = PermissionError("Access denied to event0")

        listener = DeviceListener(device_path=None, device_name="Target Device")
        with pytest.raises(PermissionError, match="Access denied to event0"):
            listener.find_device_by_name()

    @patch("evdev.InputDevice")
    def test_connect_by_path_success(self, mock_input_device):
        """Verifies connection success when device_path is explicitly set."""
        mock_dev = MagicMock()
        mock_dev.name = "Custom Device"
        mock_dev.path = "/dev/input/event5"
        mock_input_device.return_value = mock_dev

        listener = DeviceListener(device_path="/dev/input/event5", device_name=None)
        assert listener.connect() is True
        assert listener.device == mock_dev

    @patch("evdev.InputDevice")
    def test_connect_by_path_permission_error(self, mock_input_device):
        """Verifies that PermissionError is raised on connection if permissions are missing."""
        mock_input_device.side_effect = PermissionError("No permissions")

        listener = DeviceListener(device_path="/dev/input/event5", device_name=None)
        with pytest.raises(PermissionError, match="No permissions"):
            listener.connect()

    @patch("evdev.InputDevice")
    def test_connect_by_path_os_error(self, mock_input_device):
        """Verifies that connect returns False if an OSError (like file not found) occurs."""
        mock_input_device.side_effect = OSError("Device not found")

        listener = DeviceListener(device_path="/dev/input/event5", device_name=None)
        assert listener.connect() is False
        assert listener.device is None

    @patch("src.listener.DeviceListener.find_device_by_name")
    @patch("evdev.InputDevice")
    def test_connect_by_name_success(self, mock_input_device, mock_find):
        """Verifies that connect resolves path by name if device_path is not set."""
        mock_find.return_value = "/dev/input/event2"
        mock_dev = MagicMock()
        mock_dev.name = "My Target Device"
        mock_dev.path = "/dev/input/event2"
        mock_input_device.return_value = mock_dev

        listener = DeviceListener(
            device_path=None, device_name="My Target Device"
        )
        assert listener.connect() is True
        assert listener.device == mock_dev
        mock_find.assert_called_once()

    def test_read_events_not_connected(self):
        """Verifies that read_events raises OSError if not connected."""
        listener = DeviceListener(device_path="/dev/input/event0", device_name=None)
        with pytest.raises(OSError, match="Device is not connected"):
            list(listener.read_events())

    def test_read_events_loop(self):
        """Verifies that read_events yields events from evdev's read_loop."""
        listener = DeviceListener(device_path="/dev/input/event0", device_name=None)
        mock_device = MagicMock()
        mock_events = [
            MagicMock(type=1, code=67, value=1),
            MagicMock(type=1, code=67, value=0),
        ]
        mock_device.read_loop.return_value = mock_events
        listener.device = mock_device

        events = list(listener.read_events())
        assert events == mock_events
        mock_device.read_loop.assert_called_once()
