#!/usr/bin/env python3
"""Tests for error handling in ingest handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from niem_api.handlers.ingest import _create_error_result, _store_processed_files


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

    @pytest.mark.asyncio
    async def test_store_processed_files_generates_hash(self):
        """Test that _store_processed_files generates MD5 hash for filename."""
        # Mock MinIO client
        mock_s3 = MagicMock()

        # Test data
        test_content = b"<root>test content</root>"
        test_filename = "test.xml"
        test_cypher = "CREATE (n:Test)"

        # Mock the upload_file function
        with patch("niem_api.handlers.ingest.upload_file", new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = None

            # Call the function
            await _store_processed_files(
                mock_s3,
                test_content,
                test_filename,
                test_cypher,
                "xml"
            )

            # Verify upload_file was called twice (once for data, once for cypher)
            assert mock_upload.call_count == 2

            # Check that filenames contain hash and timestamp
            data_call = mock_upload.call_args_list[0]
            assert "xml/" in data_call[0][2]  # filename path includes "xml/"
            assert test_filename in data_call[0][2]  # original filename is included
