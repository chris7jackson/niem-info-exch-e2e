#!/usr/bin/env python3
"""Tests for CMF client security validation."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from niem_api.clients.cmf_client import run_cmf_command, CMFError


class TestCMFSecurityValidation:
    """Test suite for CMF client security validation."""

    @patch('niem_api.clients.cmf_client.subprocess.run')
    @patch('niem_api.clients.cmf_client.CMF_TOOL_PATH', '/app/bin/cmftool')
    def test_working_dir_security_validation_with_tmp(self, mock_run):
        """Test that working_dir security validation is triggered with /tmp path."""
        # Create a real temp directory in /tmp
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock successful subprocess run
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "success"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            # Call run_cmf_command with custom working_dir in /tmp
            # This should trigger the security validation code at line 399
            run_cmf_command(["-version"], working_dir=tmpdir)

            # Verify subprocess was called with the working directory
            mock_run.assert_called_once()
            assert mock_run.call_args[1]['cwd'] == tmpdir

    @patch('niem_api.clients.cmf_client.subprocess.run')
    @patch('niem_api.clients.cmf_client.CMF_TOOL_PATH', '/app/bin/cmftool')
    def test_working_dir_validation_rejects_unsafe_path(self, mock_run):
        """Test that working_dir validation rejects paths outside allowed locations."""
        # Try to use /etc as working dir (should be rejected)
        with pytest.raises(CMFError) as exc_info:
            run_cmf_command(["-version"], working_dir="/etc")

        assert "not in allowed locations" in str(exc_info.value)
        # Subprocess should never be called
        mock_run.assert_not_called()

    @patch('niem_api.clients.cmf_client.subprocess.run')
    @patch('niem_api.clients.cmf_client.CMF_TOOL_PATH', '/app/bin/cmftool')
    def test_working_dir_validation_rejects_nonexistent_path(self, mock_run):
        """Test that working_dir validation rejects non-existent directories."""
        with pytest.raises(CMFError) as exc_info:
            run_cmf_command(["-version"], working_dir="/tmp/nonexistent_dir_12345")

        assert "does not exist" in str(exc_info.value)
        mock_run.assert_not_called()
