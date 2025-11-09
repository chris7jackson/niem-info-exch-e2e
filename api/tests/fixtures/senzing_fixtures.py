#!/usr/bin/env python3
"""
Test fixtures for Senzing entity resolution tests.

Provides reusable test data, mock objects, and helper functions.
"""

import json
from typing import Dict, List


# Sample NIEM entities for testing
SAMPLE_ENTITIES = {
    "peter_wimsey_1": {
        "neo4j_id": 1001,
        "entity_id": "pw_1",
        "qname": "j:CrashDriver",
        "source": "test1.xml",
        "labels": ["j_CrashDriver"],
        "properties": {
            "_upload_id": "upload_test_1",
            "_schema_id": "schema_test",
            "sourceDoc": "test1.xml",
            "PersonGivenName": "Peter",
            "PersonSurName": "Wimsey",
            "PersonMiddleName": "Death Bredon",
            "BirthDate": "1890-05-04",
            "DriverLicense": "DL123456",
        },
    },
    "peter_wimsey_2": {
        "neo4j_id": 1002,
        "entity_id": "pw_2",
        "qname": "j:CrashDriver",
        "source": "test2.xml",
        "labels": ["j_CrashDriver"],
        "properties": {
            "_upload_id": "upload_test_2",
            "_schema_id": "schema_test",
            "sourceDoc": "test2.xml",
            "PersonGivenName": "Peter",
            "PersonSurName": "Wimsey",
            "PersonMiddleName": "Death Bredon",
            "BirthDate": "1890-05-04",
            "DriverLicense": "DL123456",
        },
    },
    "harriet_vane": {
        "neo4j_id": 1003,
        "entity_id": "hv_1",
        "qname": "j:CrashDriver",
        "source": "test3.xml",
        "labels": ["j_CrashDriver"],
        "properties": {
            "_upload_id": "upload_test_3",
            "_schema_id": "schema_test",
            "sourceDoc": "test3.xml",
            "PersonGivenName": "Harriet",
            "PersonSurName": "Vane",
            "BirthDate": "1893-06-15",
        },
    },
    "jason_ohlendorf": {
        "neo4j_id": 1004,
        "entity_id": "jo_1",
        "qname": "cyfs:Child",
        "source": "followup.xml",
        "labels": ["cyfs_Child"],
        "properties": {
            "_upload_id": "upload_test_4",
            "_schema_id": "schema_test",
            "sourceDoc": "followup.xml",
            "PersonFullName": "Jason Ohlendorf",
            "PersonSSN": "123-45-7890",
            "BirthDate": "2008-04-01",
        },
    },
}


# Sample Senzing responses
SAMPLE_SENZING_RESPONSES = {
    "single_entity": {
        "RESOLVED_ENTITY": {
            "ENTITY_ID": 1001,
            "ENTITY_NAME": "PETER WIMSEY",
            "RECORDS": [
                {"DATA_SOURCE": "NIEM_GRAPH", "RECORD_ID": "pw_1", "MATCH_KEY": "+NAME+DOB", "MATCH_SCORE": 95}
            ],
        }
    },
    "duplicate_entity": {
        "RESOLVED_ENTITY": {
            "ENTITY_ID": 1001,
            "ENTITY_NAME": "PETER WIMSEY",
            "RECORDS": [
                {
                    "DATA_SOURCE": "NIEM_GRAPH",
                    "RECORD_ID": "pw_1",
                    "MATCH_KEY": "+NAME+DOB+EXACTLY_SAME",
                    "MATCH_SCORE": 100,
                },
                {
                    "DATA_SOURCE": "NIEM_GRAPH",
                    "RECORD_ID": "pw_2",
                    "MATCH_KEY": "+NAME+DOB+EXACTLY_SAME",
                    "MATCH_SCORE": 100,
                },
            ],
        }
    },
}


def create_mock_senzing_client(responses: Dict[str, Dict] = None):
    """
    Create a mock Senzing client for testing.

    Args:
        responses: Dictionary mapping record_ids to Senzing responses

    Returns:
        Mock SenzingClient
    """
    if responses is None:
        responses = {}

    mock_client = Mock()
    mock_client.is_available = Mock(return_value=True)
    mock_client.initialized = True

    # Mock add_record to always succeed
    mock_client.add_record = Mock(return_value=True)

    # Mock get_entity_by_record_id to return responses
    def get_entity_side_effect(data_source, record_id, flags=None):
        return responses.get(record_id, SAMPLE_SENZING_RESPONSES["single_entity"])

    mock_client.get_entity_by_record_id = Mock(side_effect=get_entity_side_effect)

    # Mock batch processing
    def process_batch_side_effect(records):
        return {"processed": len(records), "failed": 0, "errors": []}

    mock_client.process_batch = Mock(side_effect=process_batch_side_effect)

    return mock_client


def get_sample_entity_list() -> List[Dict]:
    """Get list of sample entities for testing."""
    return [SAMPLE_ENTITIES["peter_wimsey_1"], SAMPLE_ENTITIES["peter_wimsey_2"], SAMPLE_ENTITIES["harriet_vane"]]


def get_duplicate_entities() -> List[Dict]:
    """Get list of entities that should resolve as duplicates."""
    return [SAMPLE_ENTITIES["peter_wimsey_1"], SAMPLE_ENTITIES["peter_wimsey_2"]]


def get_unique_entities() -> List[Dict]:
    """Get list of unique entities (no duplicates)."""
    return [SAMPLE_ENTITIES["harriet_vane"], SAMPLE_ENTITIES["jason_ohlendorf"]]


def assert_resolved_entity_structure(resolved_entity: Dict):
    """
    Assert that a ResolvedEntity node has the correct structure.

    Args:
        resolved_entity: Dictionary representing a ResolvedEntity node
    """
    required_fields = ["entity_id", "name", "resolved_count", "resolved_at", "_upload_ids", "_schema_ids", "sourceDocs"]

    for field in required_fields:
        assert field in resolved_entity, f"Missing required field: {field}"

    # Verify types
    assert isinstance(resolved_entity["_upload_ids"], list)
    assert isinstance(resolved_entity["_schema_ids"], list)
    assert isinstance(resolved_entity["sourceDocs"], list)
    assert isinstance(resolved_entity["resolved_count"], int)

    # Verify values make sense
    assert resolved_entity["resolved_count"] >= 2  # Must have at least 2 to be a duplicate
    assert len(resolved_entity["_upload_ids"]) > 0
    assert len(resolved_entity["sourceDocs"]) > 0


def assert_resolved_to_relationship(relationship: Dict):
    """
    Assert that a RESOLVED_TO relationship has the correct structure.

    Args:
        relationship: Dictionary representing a RESOLVED_TO relationship
    """
    required_fields = ["confidence", "resolution_method", "resolved_at"]

    for field in required_fields:
        assert field in relationship, f"Missing required field: {field}"

    # Verify types and values
    assert isinstance(relationship["confidence"], (int, float))
    assert 0 <= relationship["confidence"] <= 1
    assert relationship["resolution_method"] in ["senzing", "text_based"]


# Sample Senzing configuration
SAMPLE_FIELD_MAPPINGS = {
    "nc_PersonFullName": "PRIMARY_NAME_FULL",
    "nc_PersonGivenName": "PRIMARY_NAME_FIRST",
    "nc_PersonSurName": "PRIMARY_NAME_LAST",
    "nc_PersonMiddleName": "PRIMARY_NAME_MIDDLE",
    "nc_PersonBirthDate": "DATE_OF_BIRTH",
    "nc_PersonSSNIdentification": "SSN_NUMBER",
    "nc_DriverLicenseIdentification": "DRIVERS_LICENSE_NUMBER",
}


def get_mock_yaml_config():
    """Get mock YAML configuration for Senzing mappings."""
    return {
        "field_mappings": SAMPLE_FIELD_MAPPINGS,
        "entity_categories": {
            "person": {"patterns": ["person", "driver", "child"], "senzing_record_type": "PERSON"},
            "organization": {"patterns": ["organization", "org", "agency"], "senzing_record_type": "ORGANIZATION"},
        },
        "custom_mappings": {},
        "multi_value_fields": ["PRIMARY_NAME_MIDDLE"],
        "date_formats": {"input_formats": ["%Y-%m-%d", "%m/%d/%Y"], "output_format": "%Y-%m-%d"},
    }
