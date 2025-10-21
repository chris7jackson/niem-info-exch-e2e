#!/usr/bin/env python3

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from niem_api.services.cmf_tool import (
    convert_cmf_to_jsonschema,
    convert_xsd_to_cmf,
    download_and_setup_cmf,
    is_cmf_available,
    run_cmf_command,
)


class TestCMFTool:
    """Test suite for CMF tool service functions"""

    @pytest.fixture
    def sample_xsd_content(self):
        """Sample XSD content for conversion testing"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                   targetNamespace="http://example.com/test"
                   xmlns:tns="http://example.com/test">
            <xs:element name="TestElement" type="xs:string"/>
        </xs:schema>'''

    @pytest.fixture
    def sample_cmf_content(self):
        """Sample CMF content for JSON Schema conversion"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <cmf:Model xmlns:cmf="https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/">
            <cmf:Namespace>
                <cmf:NamespaceURI>http://example.com/test</cmf:NamespaceURI>
                <cmf:NamespacePrefixText>test</cmf:NamespacePrefixText>
            </cmf:Namespace>
        </cmf:Model>'''

    def test_is_cmf_available_true(self):
        """Test CMF availability check when tool exists"""
        with patch('niem_api.services.cmf_tool.Path') as mock_path:
            mock_jar_file = Mock()
            mock_jar_file.exists.return_value = True
            mock_path.return_value = mock_jar_file

            result = is_cmf_available()

            assert result is True

    def test_is_cmf_available_false(self):
        """Test CMF availability check when tool doesn't exist"""
        with patch('niem_api.clients.cmf_client.CMF_TOOL_PATH', '/fake/path/cmftool.jar'), \
             patch('niem_api.clients.cmf_client.Path') as mock_path:
            mock_jar_file = Mock()
            mock_jar_file.exists.return_value = False
            mock_jar_file.is_file.return_value = False
            mock_path.return_value = mock_jar_file

            result = is_cmf_available()

            assert result is False

    @pytest.mark.asyncio
    async def test_download_and_setup_cmf_success(self):
        """Test successful CMF tool setup verification"""
        with patch('niem_api.clients.cmf_client.is_cmf_available') as mock_available:
            mock_available.return_value = True

            result = await download_and_setup_cmf()

            assert result is True
            mock_available.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_and_setup_cmf_already_exists(self):
        """Test CMF setup when tool already exists"""
        with patch('niem_api.services.cmf_tool.Path') as mock_path:
            mock_jar_file = Mock()
            mock_jar_file.exists.return_value = True
            mock_path.return_value = mock_jar_file

            result = await download_and_setup_cmf()

            assert result is True

    def test_convert_xsd_to_cmf_success(self):
        """Test successful XSD to CMF conversion"""
        from pathlib import Path

        with patch('niem_api.services.cmf_tool.CMF_TOOL_PATH', '/fake/cmftool.jar'), \
             patch('niem_api.services.cmf_tool.run_cmf_command') as mock_run, \
             patch('builtins.open', create=True) as mock_open:

            # Mock successful CMF conversion
            mock_run.return_value = {
                "returncode": 0,
                "stdout": "Conversion successful",
                "stderr": ""
            }

            # Mock reading the generated CMF file
            mock_open.return_value.__enter__.return_value.read.return_value = "<cmf>converted</cmf>"

            # Create a mock Path that has rglob method
            mock_source_dir = Mock(spec=Path)
            mock_source_dir.rglob.return_value = [Mock(spec=Path)]
            mock_source_dir.__truediv__ = Mock(return_value=Mock(spec=Path, exists=Mock(return_value=True), parent=Mock(), name="schema.xsd"))

            result = convert_xsd_to_cmf(mock_source_dir, "schema.xsd")

            assert result["status"] == "success"
            assert "cmf_content" in result

    def test_convert_xsd_to_cmf_failure(self):
        """Test XSD to CMF conversion failure"""
        from pathlib import Path

        with patch('niem_api.services.cmf_tool.CMF_TOOL_PATH', '/fake/cmftool.jar'), \
             patch('niem_api.services.cmf_tool.run_cmf_command') as mock_run:

            # Mock failed CMF conversion
            mock_run.return_value = {
                "returncode": 1,
                "stdout": "",
                "stderr": "Conversion failed: Invalid XSD"
            }

            # Create a mock Path
            mock_source_dir = Mock(spec=Path)
            mock_source_dir.rglob.return_value = [Mock(spec=Path)]
            mock_source_dir.__truediv__ = Mock(return_value=Mock(spec=Path, exists=Mock(return_value=True), parent=Mock(), name="schema.xsd"))

            result = convert_xsd_to_cmf(mock_source_dir, "schema.xsd")

            assert result["status"] == "error"
            assert "Invalid XSD" in result["error"]

    def test_convert_cmf_to_jsonschema_success(self, sample_cmf_content):
        """Test successful CMF to JSON Schema conversion"""
        import json

        with patch('niem_api.services.cmf_tool.CMF_TOOL_PATH', '/fake/cmftool.jar'), \
             patch('niem_api.services.cmf_tool.run_cmf_command') as mock_run, \
             patch('os.path.exists') as mock_exists, \
             patch('builtins.open', create=True) as mock_open:

            mock_run.return_value = {
                "returncode": 0,
                "stdout": "Conversion successful",
                "stderr": ""
            }

            # Mock that JSON schema file exists
            mock_exists.return_value = True

            # Mock reading the JSON schema file
            mock_json_schema = {"type": "object", "properties": {}}
            mock_file = Mock()
            mock_file.read.return_value = json.dumps(mock_json_schema)
            mock_open.return_value.__enter__.return_value = mock_file

            result = convert_cmf_to_jsonschema(sample_cmf_content)

            assert result["status"] == "success"
            assert result["jsonschema"] == mock_json_schema

    def test_convert_cmf_to_jsonschema_invalid_json(self, sample_cmf_content):
        """Test CMF to JSON Schema conversion with invalid JSON output"""
        import json as json_module

        with patch('niem_api.services.cmf_tool.CMF_TOOL_PATH', '/fake/cmftool.jar'), \
             patch('niem_api.services.cmf_tool.run_cmf_command') as mock_run, \
             patch('os.path.exists') as mock_exists, \
             patch('builtins.open', create=True) as mock_open:

            mock_run.return_value = {
                "returncode": 0,
                "stdout": "Conversion successful",
                "stderr": ""
            }

            # Mock that JSON schema file exists
            mock_exists.return_value = True

            # Mock reading invalid JSON
            mock_file = Mock()
            mock_file.read.return_value = "invalid json content"
            mock_open.return_value.__enter__.return_value = mock_file

            # Patch json.loads to raise ValueError
            with patch('json.loads', side_effect=json_module.JSONDecodeError("Invalid JSON", "", 0)):
                result = convert_cmf_to_jsonschema(sample_cmf_content)

                assert result["status"] == "error"
                # The error message will include the exception details
                assert "error" in result

    def test_run_cmf_command(self):
        """Test CMF command execution"""
        with patch('niem_api.clients.cmf_client.CMF_TOOL_PATH', '/fake/cmftool.jar'), \
             patch('subprocess.run') as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "stdout"
            mock_result.stderr = "stderr"
            mock_subprocess.return_value = mock_result

            result = run_cmf_command(["help"])

            assert result["returncode"] == 0
            assert result["stdout"] == "stdout"
            assert result["stderr"] == "stderr"

    def test_run_cmf_command_timeout(self):
        """Test CMF command execution with timeout"""
        import subprocess

        with patch('niem_api.clients.cmf_client.CMF_TOOL_PATH', '/fake/cmftool.jar'), \
             patch('subprocess.run') as mock_subprocess:
            mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd=["version"], timeout=1)

            try:
                result = run_cmf_command(["version"], timeout=1)
                assert False, "Expected CMFError to be raised"
            except Exception as e:
                # run_cmf_command raises CMFError on timeout
                assert "timeout" in str(e).lower()
