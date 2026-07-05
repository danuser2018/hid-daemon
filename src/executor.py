"""
executor.py — Executes system commands as subprocesses.
"""

import subprocess
import logging

logger = logging.getLogger("hid_daemon.executor")


class CommandExecutor:
    """Helper to execute configured system commands as subprocesses."""

    def execute(self, command: str) -> bool:
        """
        Executes a system command as a subprocess.
        Returns True if successful (exit status 0), False otherwise.
        Does not raise exceptions on command failures.
        """
        if not command or not command.strip():
            logger.warning("Empty command requested for execution.")
            return False

        logger.info("Executing system command: '%s'", command)
        try:
            # shell=True allows executing complex shell pipelines if configured
            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                logger.info(
                    "Command '%s' executed successfully (exit code 0).", command
                )
                return True
            else:
                logger.error(
                    "Command '%s' failed with exit code %d.\n"
                    "stdout: %s\n"
                    "stderr: %s",
                    command,
                    result.returncode,
                    result.stdout.strip(),
                    result.stderr.strip(),
                )
                return False
        except Exception as exc:
            logger.exception(
                "Failed to run command '%s' due to exception.", command
            )
            return False
        return False
