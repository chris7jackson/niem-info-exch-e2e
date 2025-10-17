#!/usr/bin/env python3
"""Tests for error handling in ingest handler."""


from niem_api.handlers.ingest import _create_error_result


class TestIngestErrorHandling:
    """Test suite for ingest error handling."""

    def test_create_error_result_basic(self):
        """Test creating basic error result without validation details."""
        result = _create_error_result("test.xml", "File not found")

        assert result["filename"] == "test.xml"
        assert result["status"] == "failed"
        assert result["error"] == "File not found"
        assert "validation_details" not in result

    def test_create_error_result_with_validation(self):
        """Test creating error result with validation details."""
        validation_result = {
            "valid": False,
            "errors": [
                {
                    "file": "test.xml",
                    "line": 10,
                    "column": 5,
                    "message": "Invalid element",
                    "severity": "error"
                }
            ],
            "warnings": [],
            "summary": "Validation failed with 1 error(s)"
        }

        result = _create_error_result("test.xml", "Validation failed", validation_result)

        assert result["filename"] == "test.xml"
        assert result["status"] == "failed"
        assert result["error"] == "Validation failed"
        assert "validation_details" in result
        assert result["validation_details"]["valid"] is False
        assert len(result["validation_details"]["errors"]) == 1
