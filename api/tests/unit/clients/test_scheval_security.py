#!/usr/bin/env python3
"""Tests for Scheval client security validation."""

import tempfile
from unittest.mock import MagicMock, patch

import pytest

from niem_api.clients.scheval_client import run_scheval_command, SchevalError, _validate_scheval_command


class TestSchevalSecurityValidation:
    """Test suite for Scheval client security validation."""

    def test_validate_command_with_absolute_path_in_tmp(self):
        """Test argument validation with absolute path in /tmp (line 314)."""
        # Create a real temp file to use as argument
        with tempfile.NamedTemporaryFile(suffix=".xsd", delete=False) as tmpfile:
            tmpfile_path = tmpfile.name

            # This should trigger the security validation at line 314
            # and pass because /tmp is an allowed prefix
            try:
                _validate_scheval_command(["-x", tmpfile_path])
                # If we get here, validation passed (expected)
            except SchevalError:
                pytest.fail("Validation should allow /tmp paths")

    def test_validate_command_rejects_unsafe_absolute_path(self):
        """Test that argument validation rejects unsafe absolute paths."""
        # Try to validate with /etc path (should be rejected)
        with pytest.raises(SchevalError) as exc_info:
            _validate_scheval_command(["-x", "/etc/passwd"])

        assert "outside allowed directories" in str(exc_info.value)

    @patch("niem_api.clients.scheval_client.subprocess.run")
    @patch("niem_api.clients.scheval_client.SCHEVAL_TOOL_PATH", "/app/bin/scheval")
    def test_working_dir_security_validation_with_tmp(self, mock_run):
        """Test that working_dir security validation is triggered with /tmp path (line 414)."""
        # Create a real temp directory in /tmp
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock successful subprocess run
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "success"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            # Call run_scheval_command with custom working_dir in /tmp
            # This should trigger the security validation code at line 414
            run_scheval_command(["--help"], working_dir=tmpdir)

            # Verify subprocess was called with the working directory
            mock_run.assert_called_once()
            assert mock_run.call_args[1]["cwd"] == tmpdir

    @patch("niem_api.clients.scheval_client.subprocess.run")
    @patch("niem_api.clients.scheval_client.SCHEVAL_TOOL_PATH", "/app/bin/scheval")
    def test_working_dir_validation_rejects_unsafe_path(self, mock_run):
        """Test that working_dir validation rejects paths outside allowed locations."""
        # Try to use /etc as working dir (should be rejected)
        with pytest.raises(SchevalError) as exc_info:
            run_scheval_command(["--help"], working_dir="/etc")

        assert "not in allowed locations" in str(exc_info.value)
        # Subprocess should never be called
        mock_run.assert_not_called()

    @patch("niem_api.clients.scheval_client.subprocess.run")
    @patch("niem_api.clients.scheval_client.SCHEVAL_TOOL_PATH", "/app/bin/scheval")
    def test_working_dir_validation_rejects_nonexistent_path(self, mock_run):
        """Test that working_dir validation rejects non-existent directories."""
        with pytest.raises(SchevalError) as exc_info:
            run_scheval_command(["--help"], working_dir="/tmp/nonexistent_dir_12345")

        assert "does not exist" in str(exc_info.value)
        mock_run.assert_not_called()
