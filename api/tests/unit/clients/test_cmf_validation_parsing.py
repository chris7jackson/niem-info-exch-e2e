#!/usr/bin/env python3
"""Tests for CMF validation output parsing."""

import pytest
from niem_api.clients.cmf_client import parse_cmf_validation_output


class TestCMFValidationParsing:
    """Test suite for CMF validation output parsing."""

    def test_parse_error_with_location(self):
        """Test parsing error with file, line, and column."""
        stdout = "[error] test.xml:42:15: cvc-complex-type.2.4.a: Invalid content"
        stderr = ""
        filename = "test.xml"

        result = parse_cmf_validation_output(stdout, stderr, filename)

        assert result["has_errors"] is True
        assert len(result["errors"]) == 1
        assert result["errors"][0]["file"] == "test.xml"
        assert result["errors"][0]["line"] == 42
        assert result["errors"][0]["column"] == 15
        assert "Invalid content" in result["errors"][0]["message"]
        assert result["errors"][0]["severity"] == "error"

    def test_parse_error_without_location(self):
        """Test parsing error without location information."""
        stdout = "[error] Schema validation failed"
        stderr = ""
        filename = "test.xml"

        result = parse_cmf_validation_output(stdout, stderr, filename)

        assert result["has_errors"] is True
        assert len(result["errors"]) == 1
        assert result["errors"][0]["file"] == "test.xml"
        assert result["errors"][0]["line"] is None
        assert result["errors"][0]["column"] is None
        assert "Schema validation failed" in result["errors"][0]["message"]

    def test_parse_multiple_errors(self):
        """Test parsing multiple errors."""
        stdout = """[error] test.xml:10:5: Element not allowed here
[error] test.xml:20:12: Missing required attribute
[warning] test.xml:30:1: Deprecated element usage"""
        stderr = ""
        filename = "test.xml"

        result = parse_cmf_validation_output(stdout, stderr, filename)

        assert result["has_errors"] is True
        assert len(result["errors"]) == 2
        assert len(result["warnings"]) == 1

        # Check first error
        assert result["errors"][0]["line"] == 10
        assert result["errors"][0]["column"] == 5
        assert "not allowed" in result["errors"][0]["message"]

        # Check second error
        assert result["errors"][1]["line"] == 20
        assert result["errors"][1]["column"] == 12
        assert "required attribute" in result["errors"][1]["message"]

        # Check warning
        assert result["warnings"][0]["line"] == 30
        assert result["warnings"][0]["severity"] == "warning"

    def test_parse_warning_only(self):
        """Test parsing warnings without errors."""
        stdout = "[warning] test.xml:5:1: Unused namespace declaration"
        stderr = ""
        filename = "test.xml"

        result = parse_cmf_validation_output(stdout, stderr, filename)

        assert result["has_errors"] is False
        assert len(result["errors"]) == 0
        assert len(result["warnings"]) == 1
        assert result["warnings"][0]["severity"] == "warning"

    def test_parse_stderr_errors(self):
        """Test parsing errors from stderr."""
        stdout = ""
        stderr = "[error] Fatal: Cannot read schema file"
        filename = "test.xml"

        result = parse_cmf_validation_output(stdout, stderr, filename)

        assert result["has_errors"] is True
        assert len(result["errors"]) == 1
        assert "Cannot read schema" in result["errors"][0]["message"]

    def test_parse_mixed_stdout_stderr(self):
        """Test parsing errors from both stdout and stderr."""
        stdout = "[error] test.xml:10:5: Validation error in content"
        stderr = "[error] Schema loading failed"
        filename = "test.xml"

        result = parse_cmf_validation_output(stdout, stderr, filename)

        assert result["has_errors"] is True
        assert len(result["errors"]) == 2

    def test_parse_empty_output(self):
        """Test parsing when no errors or warnings present."""
        stdout = "Validation successful\nNo errors found"
        stderr = ""
        filename = "test.xml"

        result = parse_cmf_validation_output(stdout, stderr, filename)

        assert result["has_errors"] is False
        assert len(result["errors"]) == 0
        assert len(result["warnings"]) == 0

    def test_parse_unstructured_error_fallback(self):
        """Test fallback for unstructured error messages."""
        stdout = "Error occurred during validation"
        stderr = ""
        filename = "test.xml"

        result = parse_cmf_validation_output(stdout, stderr, filename)

        # Should create a generic error when "error" keyword found but not structured
        assert result["has_errors"] is True
        assert len(result["errors"]) == 1
        assert result["errors"][0]["file"] == "test.xml"
        assert "Error occurred" in result["errors"][0]["message"]

    def test_parse_case_insensitive_severity(self):
        """Test that severity markers are case-insensitive."""
        stdout = "[ERROR] test.xml:1:1: Case test\n[Warning] test.xml:2:1: Another case test"
        stderr = ""
        filename = "test.xml"

        result = parse_cmf_validation_output(stdout, stderr, filename)

        assert len(result["errors"]) == 1
        assert len(result["warnings"]) == 1
        assert result["errors"][0]["severity"] == "error"
        assert result["warnings"][0]["severity"] == "warning"

    def test_parse_info_messages(self):
        """Test parsing info-level messages."""
        stdout = "[info] test.xml:1:1: Schema version detected"
        stderr = ""
        filename = "test.xml"

        result = parse_cmf_validation_output(stdout, stderr, filename)

        assert result["has_errors"] is False
        # Info messages go to warnings list (non-blocking)
        assert len(result["warnings"]) == 0  # Info is currently ignored in our implementation
