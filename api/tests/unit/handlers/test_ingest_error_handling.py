#!/usr/bin/env python3
"""Tests for error handling in ingest handler."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException, UploadFile

from niem_api.handlers.ingest import _create_error_result
from niem_api.models.models import ValidationError, ValidationResult


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

    def test_validation_error_model(self):
        """Test ValidationError model creation."""
        error = ValidationError(
            file="test.xml",
            line=42,
            column=15,
            message="Element not allowed",
            severity="error",
            rule="cvc-complex-type.2.4.a"
        )

        assert error.file == "test.xml"
        assert error.line == 42
        assert error.column == 15
        assert error.message == "Element not allowed"
        assert error.severity == "error"
        assert error.rule == "cvc-complex-type.2.4.a"

    def test_validation_result_model(self):
        """Test ValidationResult model creation."""
        errors = [
            ValidationError(
                file="test.xml",
                line=10,
                message="Error 1",
                severity="error"
            ),
            ValidationError(
                file="test.xml",
                line=20,
                message="Error 2",
                severity="error"
            )
        ]

        warnings = [
            ValidationError(
                file="test.xml",
                line=30,
                message="Warning 1",
                severity="warning"
            )
        ]

        result = ValidationResult(
            valid=False,
            errors=errors,
            warnings=warnings,
            summary="2 errors, 1 warning"
        )

        assert result.valid is False
        assert len(result.errors) == 2
        assert len(result.warnings) == 1
        assert result.summary == "2 errors, 1 warning"

    def test_validation_error_optional_fields(self):
        """Test ValidationError with optional fields."""
        error = ValidationError(
            file="test.xml",
            message="Generic error",
            severity="error"
        )

        assert error.file == "test.xml"
        assert error.line is None
        assert error.column is None
        assert error.rule is None
        assert error.context is None
        assert error.message == "Generic error"
