"""
listener.py — Listens for events on raw HID devices using evdev.
"""

import evdev
import logging
from typing import Iterator, Any

logger = logging.getLogger("hid_daemon.listener")


class DeviceListener:
    """Monitors raw HID input devices and reads event streams."""

    def __init__(self, device_path: str | None, device_name: str | None):
        self.device_path = device_path
        self.device_name = device_name
        self.device: evdev.InputDevice | None = None

    def find_device_by_name(self) -> str | None:
        """
        Scans /dev/input/event* and returns the path of the device matching device_name.
        Raises PermissionError if accessing device files is denied.
        """
        if not self.device_name:
            return None

        logger.debug(
            "Scanning input devices to find match for: '%s'", self.device_name
        )
        try:
            device_paths = evdev.list_devices()
        except PermissionError as exc:
            logger.critical(
                "Permission denied listing input devices. "
                "Ensure the current user belongs to the 'input' group: "
                "sudo usermod -aG input $USER"
            )
            raise exc
        except Exception as exc:
            logger.error("Error listing input devices: %s", exc)
            return None

        matching_paths = []
        for path in device_paths:
            try:
                dev = evdev.InputDevice(path)
                if dev.name == self.device_name:
                    matching_paths.append(dev.path)
            except PermissionError as exc:
                logger.critical(
                    "Permission denied accessing device file %s. "
                    "Ensure the current user belongs to the 'input' group: "
                    "sudo usermod -aG input $USER",
                    path,
                )
                raise exc
            except Exception as exc:
                # Some device paths might not be accessible or have other errors, ignore them
                logger.debug("Skipping device file %s: %s", path, exc)
                continue

        if not matching_paths:
            logger.warning(
                "No input device found matching name: '%s'", self.device_name
            )
            return None

        if len(matching_paths) > 1:
            logger.warning(
                "Multiple devices match name '%s': %s. Selecting first match: %s",
                self.device_name,
                matching_paths,
                matching_paths[0],
            )

        return matching_paths[0]

    def connect(self) -> bool:
        """
        Attempts to connect to the configured HID device.
        Returns True if successful, False otherwise.
        Raises PermissionError if accessing the device file is denied.
        """
        path_to_connect = self.device_path

        # If path is not set, look it up by name
        if not path_to_connect:
            try:
                path_to_connect = self.find_device_by_name()
            except PermissionError as exc:
                raise exc
            except Exception as exc:
                logger.error("Error searching device by name: %s", exc)
                return False

        if not path_to_connect:
            logger.warning(
                "Cannot connect: no device path or name could be resolved."
            )
            return False

        logger.info(
            "Attempting to connect to device at path: %s", path_to_connect
        )
        try:
            self.device = evdev.InputDevice(path_to_connect)
            logger.info(
                "Successfully connected to device: '%s' (%s)",
                self.device.name,
                self.device.path,
            )
            return True
        except PermissionError as exc:
            logger.critical(
                "Permission denied accessing device file %s. "
                "Ensure the current user belongs to the 'input' group: "
                "sudo usermod -aG input $USER",
                path_to_connect,
            )
            raise exc
        except (OSError, FileNotFoundError) as exc:
            logger.warning(
                "Failed to open device at path %s: %s", path_to_connect, exc
            )
            self.device = None
            return False

    def read_events(self) -> Iterator[Any]:
        """
        Yields input events from the device.
        Raises OSError or FileNotFoundError if the device is disconnected.
        """
        if not self.device:
            raise OSError("Device is not connected.")

        # read_loop() yields evdev.events.InputEvent instances.
        # It raises OSError/FileNotFoundError internally if the device gets disconnected.
        for event in self.device.read_loop():
            yield event
