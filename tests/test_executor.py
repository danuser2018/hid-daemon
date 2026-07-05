"""
test_executor.py — Unit tests for src/executor.py.
"""

import pytest
import subprocess
from unittest.mock import patch, MagicMock
from src.executor import CommandExecutor


def test_execute_empty_command():
    """Verifies that an empty command is ignored and returns False."""
    executor = CommandExecutor()
    assert executor.execute("") is False
    assert executor.execute("   ") is False


@patch("subprocess.run")
def test_execute_success(mock_run):
    """Verifies that a successful command returns True."""
    mock_response = MagicMock()
    mock_response.returncode = 0
    mock_response.stdout = "Everything ok"
    mock_response.stderr = ""
    mock_run.return_value = mock_response

    executor = CommandExecutor()
    result = executor.execute("echo 'hello'")

    assert result is True
    mock_run.assert_called_once_with(
        "echo 'hello'",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


@patch("subprocess.run")
def test_execute_failure(mock_run):
    """Verifies that a failing command returns False."""
    mock_response = MagicMock()
    mock_response.returncode = 127
    mock_response.stdout = ""
    mock_response.stderr = "/bin/sh: command-not-found: not found"
    mock_run.return_value = mock_response

    executor = CommandExecutor()
    result = executor.execute("command-not-found")

    assert result is False
    mock_run.assert_called_once_with(
        "command-not-found",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


@patch("subprocess.run")
def test_execute_exception(mock_run):
    """Verifies that if subprocess.run raises an exception, the executor returns False."""
    mock_run.side_effect = RuntimeError("Process failed to start")

    executor = CommandExecutor()
    result = executor.execute("some-command")

    assert result is False
    mock_run.assert_called_once()
