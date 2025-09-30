#!/usr/bin/env python3

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, AsyncMock

from minio import Minio
from neo4j import GraphDatabase

from niem_api.services.neo4j_client import Neo4jClient


class TestHelpers:
    """Common test helper functions"""

    @staticmethod
    def create_mock_s3_client() -> Mock:
        """Create a mock MinIO S3 client for testing"""
        mock_client = Mock(spec=Minio)
        mock_client.bucket_exists.return_value = True
        mock_client.make_bucket.return_value = None
        mock_client.list_objects.return_value = iter([])
        mock_client.get_object.return_value = Mock()
        mock_client.put_object.return_value = Mock()
        mock_client.remove_object.return_value = None
        return mock_client

    @staticmethod
    def create_mock_neo4j_client() -> Mock:
        """Create a mock Neo4j client for testing"""
        mock_client = Mock(spec=Neo4jClient)
        mock_client.query.return_value = []
        mock_client.query_graph.return_value = {"nodes": [], "relationships": []}
        mock_client.check_connection.return_value = True
        mock_client.get_database_stats.return_value = {
            "node_count": 0,
            "relationship_count": 0,
            "labels": [],
            "relationship_types": []
        }
        return mock_client

    @staticmethod
    def create_temp_file(content: str, suffix: str = ".tmp") -> Path:
        """Create a temporary file with content"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False)
        temp_file.write(content)
        temp_file.close()
        return Path(temp_file.name)

    @staticmethod
    def create_temp_xsd(content: Optional[str] = None) -> Path:
        """Create a temporary XSD file"""
        if content is None:
            content = '''<?xml version="1.0" encoding="UTF-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                       targetNamespace="http://example.com/test"
                       xmlns:tns="http://example.com/test">
                <xs:element name="TestElement" type="xs:string"/>
            </xs:schema>'''
        return TestHelpers.create_temp_file(content, ".xsd")

    @staticmethod
    def create_temp_cmf(content: Optional[str] = None) -> Path:
        """Create a temporary CMF file"""
        if content is None:
            content = '''<?xml version="1.0" encoding="UTF-8"?>
            <cmf:Model xmlns:cmf="https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/"
                       xmlns:structures="https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/">
                <cmf:Namespace>
                    <cmf:NamespaceURI>http://example.com/test</cmf:NamespaceURI>
                    <cmf:NamespacePrefixText>test</cmf:NamespacePrefixText>
                </cmf:Namespace>
            </cmf:Model>'''
        return TestHelpers.create_temp_file(content, ".cmf")

    @staticmethod
    def create_temp_json(data: Dict[str, Any]) -> Path:
        """Create a temporary JSON file"""
        content = json.dumps(data, indent=2)
        return TestHelpers.create_temp_file(content, ".json")

    @staticmethod
    async def wait_for_condition(
        condition_func: callable,
        timeout: float = 5.0,
        interval: float = 0.1
    ) -> bool:
        """Wait for a condition to become true"""
        elapsed = 0.0
        while elapsed < timeout:
            if await condition_func() if asyncio.iscoroutinefunction(condition_func) else condition_func():
                return True
            await asyncio.sleep(interval)
            elapsed += interval
        return False

    @staticmethod
    def assert_dict_contains(actual: Dict, expected: Dict, path: str = ""):
        """Assert that actual dict contains all keys/values from expected dict"""
        for key, expected_value in expected.items():
            current_path = f"{path}.{key}" if path else key
            assert key in actual, f"Missing key '{current_path}' in actual dict"

            actual_value = actual[key]
            if isinstance(expected_value, dict) and isinstance(actual_value, dict):
                TestHelpers.assert_dict_contains(actual_value, expected_value, current_path)
            else:
                assert actual_value == expected_value, f"Value mismatch at '{current_path}': expected {expected_value}, got {actual_value}"

    @staticmethod
    def cleanup_temp_files(*paths: Path):
        """Clean up temporary files"""
        for path in paths:
            if path and path.exists():
                path.unlink()


class AsyncContextManager:
    """Helper for testing async context managers"""

    def __init__(self, return_value=None):
        self.return_value = return_value
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self.return_value

    async def __aexited__(self, exc_type, exc_val, exc_tb):
        self.exited = True
        return False


class MockUploadFile:
    """Mock UploadFile for testing file uploads"""

    def __init__(self, filename: str, content: bytes, content_type: str = "application/octet-stream"):
        self.filename = filename
        self.content = content
        self.content_type = content_type
        self._position = 0

    async def read(self, size: int = -1) -> bytes:
        """Read file content"""
        if size == -1:
            content = self.content[self._position:]
            self._position = len(self.content)
        else:
            content = self.content[self._position:self._position + size]
            self._position += len(content)
        return content

    async def seek(self, position: int):
        """Seek to position"""
        self._position = max(0, min(position, len(self.content)))

    async def close(self):
        """Close file"""
        pass


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, isolated)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (require external services)"
    )
    config.addinivalue_line(
        "markers", "slow: Slow running tests"
    )
    config.addinivalue_line(
        "markers", "smoke: Smoke tests for critical functionality"
    )
    config.addinivalue_line(
        "markers", "security: Security-related tests"
    )
    config.addinivalue_line(
        "markers", "performance: Performance benchmark tests"
    )