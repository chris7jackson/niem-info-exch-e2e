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
        with patch('niem_api.services.cmf_tool.Path') as mock_path:
            mock_jar_file = Mock()
            mock_jar_file.exists.return_value = False
            mock_path.return_value = mock_jar_file

            result = is_cmf_available()

            assert result is False

    @pytest.mark.asyncio
    async def test_download_and_setup_cmf_success(self):
        """Test successful CMF tool download and setup"""
        with patch('niem_api.services.cmf_tool.httpx.AsyncClient') as mock_client, \
             patch('niem_api.services.cmf_tool.Path') as mock_path, \
             patch('builtins.open', create=True) as mock_open:

            # Mock HTTP response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'fake jar content'

            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            # Mock file operations
            mock_jar_file = Mock()
            mock_jar_file.exists.return_value = False
            mock_jar_file.parent.exists.return_value = True
            mock_path.return_value = mock_jar_file

            result = await download_and_setup_cmf()

            assert result is True
            mock_open.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_and_setup_cmf_already_exists(self):
        """Test CMF setup when tool already exists"""
        with patch('niem_api.services.cmf_tool.Path') as mock_path:
            mock_jar_file = Mock()
            mock_jar_file.exists.return_value = True
            mock_path.return_value = mock_jar_file

            result = await download_and_setup_cmf()

            assert result is True

    def test_convert_xsd_to_cmf_success(self, sample_xsd_content):
        """Test successful XSD to CMF conversion"""
        with patch('niem_api.services.cmf_tool.run_cmf_command') as mock_run:
            mock_run.return_value = {
                "returncode": 0,
                "stdout": "Conversion successful",
                "stderr": ""
            }

            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = "<cmf>converted</cmf>"

                result = convert_xsd_to_cmf(sample_xsd_content)

                assert result["status"] == "success"
                assert "cmf_content" in result
                mock_run.assert_called_once()

    def test_convert_xsd_to_cmf_failure(self, sample_xsd_content):
        """Test XSD to CMF conversion failure"""
        with patch('niem_api.services.cmf_tool.run_cmf_command') as mock_run:
            mock_run.return_value = {
                "returncode": 1,
                "stdout": "",
                "stderr": "Conversion failed: Invalid XSD"
            }

            result = convert_xsd_to_cmf(sample_xsd_content)

            assert result["status"] == "error"
            assert "Invalid XSD" in result["error"]

    def test_convert_cmf_to_jsonschema_success(self, sample_cmf_content):
        """Test successful CMF to JSON Schema conversion"""
        with patch('niem_api.services.cmf_tool.run_cmf_command') as mock_run:
            mock_run.return_value = {
                "returncode": 0,
                "stdout": "Conversion successful",
                "stderr": ""
            }

            mock_json_schema = {"type": "object", "properties": {}}
            with patch('builtins.open', create=True), \
                 patch('json.load', return_value=mock_json_schema):

                result = convert_cmf_to_jsonschema(sample_cmf_content)

                assert result["status"] == "success"
                assert result["jsonschema"] == mock_json_schema

    def test_convert_cmf_to_jsonschema_invalid_json(self, sample_cmf_content):
        """Test CMF to JSON Schema conversion with invalid JSON output"""
        with patch('niem_api.services.cmf_tool.run_cmf_command') as mock_run:
            mock_run.return_value = {
                "returncode": 0,
                "stdout": "Conversion successful",
                "stderr": ""
            }

            with patch('builtins.open', create=True), \
                 patch('json.load', side_effect=ValueError("Invalid JSON")):

                result = convert_cmf_to_jsonschema(sample_cmf_content)

                assert result["status"] == "error"
                assert "Invalid JSON" in result["error"]

    def test_run_cmf_command(self):
        """Test CMF command execution"""
        with patch('subprocess.run') as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = b"stdout"
            mock_result.stderr = b"stderr"
            mock_subprocess.return_value = mock_result

            result = run_cmf_command(["--help"])

            assert result["returncode"] == 0
            assert result["stdout"] == "stdout"
            assert result["stderr"] == "stderr"

    def test_run_cmf_command_timeout(self):
        """Test CMF command execution with timeout"""
        with patch('subprocess.run') as mock_subprocess:
            import subprocess
            mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd=["--slow-operation"], timeout=1)

            result = run_cmf_command(["--slow-operation"], timeout=1)

            assert result["returncode"] == -1
            assert "timeout" in result["error"].lower()
