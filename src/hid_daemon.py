"""
hid_daemon.py — Entry point and main event loop for the hid-daemon.
"""

import sys
import signal
import logging
import threading
import evdev
from typing import Dict, List

from src.config import load_config, Config
from src.executor import CommandExecutor
from src.listener import DeviceListener

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("hid_daemon")


def resolve_key_names(event_code: int) -> List[str]:
    """
    Resolves a numeric key event code into list of uppercase key name strings.
    E.g. 67 -> ["KEY_F9"]
    """
    try:
        val = evdev.ecodes.KEY.get(event_code)
        if isinstance(val, list):
            return [name.upper() for name in val]
        elif isinstance(val, str):
            return [val.upper()]
    except Exception:
        pass
    return []


class HidDaemon:
    """Daemon that connects to an HID device and executes commands based on key bindings."""

    def __init__(self, config: Config):
        self.config = config
        self.executor = CommandExecutor()
        self.stop_event = threading.Event()
        # Toggle state tracking. Keys are stored as uppercase string identifiers.
        self.toggle_states: Dict[str, bool] = {}

    def handle_key_event(self, key_id: str, value: int) -> None:
        """
        Processes key presses and releases.
        Key repeat (value == 2) must be ignored.
        """
        if value == 2:
            logger.debug("Ignoring key repeat event for: %s", key_id)
            return

        binding = self.config.bindings.get(key_id)
        if not binding:
            return

        logger.info(
            "Event detected for key %s (value=%d, mode=%s)",
            key_id,
            value,
            binding.mode,
        )

        if binding.mode == "PTT":
            if value == 1:  # Pressed
                if binding.press_command:
                    self.executor.execute(binding.press_command)
            elif value == 0:  # Released
                if binding.release_command:
                    self.executor.execute(binding.release_command)

        elif binding.mode == "TOGGLE":
            if value == 1:  # Pressed
                # Toggle state: True means active, False means idle
                current_state = self.toggle_states.get(key_id, False)
                next_state = not current_state
                self.toggle_states[key_id] = next_state

                if next_state:
                    # First press: execute press command
                    if binding.press_command:
                        self.executor.execute(binding.press_command)
                else:
                    # Second press: execute release command (fallback to press if none exists)
                    cmd_to_run = binding.release_command or binding.press_command
                    if cmd_to_run:
                        self.executor.execute(cmd_to_run)

    def process_events(self, listener: DeviceListener) -> None:
        """Reads and processes events from the listener until disconnected or stopped."""
        logger.info("Listening for events...")
        for event in listener.read_events():
            if self.stop_event.is_set():
                break

            # Type 1 is EV_KEY
            if event.type == evdev.ecodes.EV_KEY:
                code_str = str(event.code)
                names = resolve_key_names(event.code)

                # Find which key identifier is configured in bindings
                matched_key_id = None
                if code_str in self.config.bindings:
                    matched_key_id = code_str
                else:
                    for name in names:
                        if name in self.config.bindings:
                            matched_key_id = name
                            break

                if matched_key_id:
                    self.handle_key_event(matched_key_id, event.value)
                else:
                    logger.debug(
                        "Unhandled key code %d (names: %s)", event.code, names
                    )

    def stop(self) -> None:
        """Signals the daemon to stop."""
        self.stop_event.set()

    def run(self) -> None:
        """Main daemon loop. Handles connection retries and clean shutdown."""
        logger.info("Starting HID Daemon event loop...")
        listener = DeviceListener(
            self.config.device_path, self.config.device_name
        )

        while not self.stop_event.is_set():
            try:
                connected = listener.connect()
            except PermissionError:
                # PermissionError is fatal. Terminate immediately with exit code 1.
                logger.critical(
                    "Fatal permissions error: daemon cannot access the input device. Exiting."
                )
                sys.exit(1)
            except Exception as exc:
                logger.error("Unexpected error during connection: %s", exc)
                connected = False

            if connected:
                try:
                    self.process_events(listener)
                except (OSError, FileNotFoundError) as exc:
                    logger.warning("Device disconnected: %s", exc)
                except Exception as exc:
                    logger.error("Unexpected error in event loop: %s", exc)
            else:
                logger.info(
                    "Retrying connection in %.1f seconds...",
                    self.config.reconnect_delay_s,
                )

            # Responsive wait on stop event
            self.stop_event.wait(timeout=self.config.reconnect_delay_s)

        logger.info("HID Daemon event loop stopped.")


def main() -> None:
    logger.info("Initializing hid-daemon...")
    try:
        config = load_config()
    except FileNotFoundError as exc:
        logger.critical("Configuration error: %s", exc)
        sys.exit(1)
    except ValueError as exc:
        logger.critical("Configuration validation failed: %s", exc)
        sys.exit(1)

    daemon = HidDaemon(config)

    def signal_handler(signum, frame):
        logger.info("Received signal %d. Shutting down gracefully...", signum)
        daemon.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    daemon.run()
    logger.info("hid-daemon terminated successfully.")


if __name__ == "__main__":
    main()
