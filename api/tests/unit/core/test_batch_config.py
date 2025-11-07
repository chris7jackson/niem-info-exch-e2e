#!/usr/bin/env python3
"""Tests for batch configuration."""

import os
from unittest.mock import patch

import pytest

from niem_api.core.config import BatchConfig, batch_config


class TestBatchConfig:
    """Test suite for batch configuration."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = BatchConfig()

        assert config.MAX_CONCURRENT_OPERATIONS == 3
        assert config.OPERATION_TIMEOUT == 60
        assert config.MAX_SCHEMA_FILES == 150
        assert config.MAX_CONVERSION_FILES == 150
        assert config.MAX_INGEST_FILES == 150

    def test_get_batch_limit_schema(self):
        """Test getting batch limit for schema operation."""
        limit = batch_config.get_batch_limit('schema')
        assert limit == 150

    def test_get_batch_limit_conversion(self):
        """Test getting batch limit for conversion operation."""
        limit = batch_config.get_batch_limit('conversion')
        assert limit == 150

    def test_get_batch_limit_ingest(self):
        """Test getting batch limit for ingest operation."""
        limit = batch_config.get_batch_limit('ingest')
        assert limit == 150

    def test_get_batch_limit_unknown_operation(self):
        """Test getting batch limit for unknown operation returns default."""
        limit = batch_config.get_batch_limit('unknown_operation')
        assert limit == 10  # Default fallback

    @patch.dict(os.environ, {
        'BATCH_MAX_CONCURRENT_OPERATIONS': '5',
        'BATCH_OPERATION_TIMEOUT': '120',
        'BATCH_MAX_SCHEMA_FILES': '200',
        'BATCH_MAX_CONVERSION_FILES': '100',
        'BATCH_MAX_INGEST_FILES': '50'
    })
    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        # Need to create a new instance to pick up env vars
        config = BatchConfig()

        assert config.MAX_CONCURRENT_OPERATIONS == 5
        assert config.OPERATION_TIMEOUT == 120
        assert config.MAX_SCHEMA_FILES == 200
        assert config.MAX_CONVERSION_FILES == 100
        assert config.MAX_INGEST_FILES == 50

    @patch.dict(os.environ, {'BATCH_MAX_SCHEMA_FILES': '2'})
    def test_small_batch_limit(self):
        """Test setting a small batch limit via environment variable."""
        config = BatchConfig()
        assert config.MAX_SCHEMA_FILES == 2

    @patch.dict(os.environ, {'BATCH_MAX_CONCURRENT_OPERATIONS': '1'})
    def test_single_concurrent_operation(self):
        """Test setting concurrent operations to 1."""
        config = BatchConfig()
        assert config.MAX_CONCURRENT_OPERATIONS == 1

    def test_singleton_instance_exists(self):
        """Test that batch_config singleton instance exists."""
        assert batch_config is not None
        assert isinstance(batch_config, BatchConfig)
