#!/usr/bin/env python3
"""
Unit tests for NIEM to Senzing entity conversion.

Tests the field mapping, entity categorization, and data transformation logic.

Run with: pytest api/tests/unit/services/test_entity_to_senzing.py -v
"""

import json
import pytest
from niem_api.services.entity_to_senzing import (
    neo4j_entity_to_senzing_record,
    batch_convert_to_senzing,
    get_entity_category,
    format_date_for_senzing,
    extract_confidence_from_senzing,
)


class TestEntityCategorization:
    """Test entity category detection."""

    def test_person_category(self):
        """Test person entity detection."""
        entity = {"qname": "j:CrashDriver"}
        assert get_entity_category(entity) == "person"

        entity = {"qname": "nc:Person"}
        assert get_entity_category(entity) == "person"

        entity = {"qname": "cyfs:Child"}
        assert get_entity_category(entity) == "person"

    def test_organization_category(self):
        """Test organization entity detection."""
        entity = {"qname": "nc:Organization"}
        assert get_entity_category(entity) == "organization"

        entity = {"qname": "j:EnforcementOfficial"}
        assert get_entity_category(entity) == "organization"

    def test_address_category(self):
        """Test address entity detection."""
        entity = {"qname": "nc:Address"}
        assert get_entity_category(entity) == "address"

        entity = {"qname": "nc:Location"}
        assert get_entity_category(entity) == "address"

    def test_unknown_category(self):
        """Test fallback for unknown entities."""
        entity = {"qname": "unknown:Type"}
        assert get_entity_category(entity) == "other"


class TestFieldMapping:
    """Test NIEM to Senzing field mapping."""

    def test_person_name_mapping(self):
        """Test person name fields are mapped correctly."""
        entity = {
            "qname": "j:CrashDriver",
            "neo4j_id": 123,
            "entity_id": "test_123",
            "source": "test.xml",
            "properties": {"PersonGivenName": "Peter", "PersonSurName": "Wimsey", "PersonMiddleName": "Death"},
        }

        result_json = neo4j_entity_to_senzing_record(entity)
        result = json.loads(result_json)

        assert result["DATA_SOURCE"] == "NIEM_GRAPH"
        assert result["RECORD_ID"] == "test_123"
        assert result["ENTITY_TYPE"] == "PERSON"
        assert result["PRIMARY_NAME_FIRST"] == "Peter"
        assert result["PRIMARY_NAME_LAST"] == "Wimsey"
        assert "PRIMARY_NAME_MIDDLE" in result

    def test_identification_mapping(self):
        """Test identification fields are mapped."""
        entity = {
            "qname": "j:CrashDriver",
            "neo4j_id": 124,
            "entity_id": "test_124",
            "source": "test.xml",
            "properties": {
                "PersonGivenName": "Test",
                "PersonSurName": "Person",
                "PersonSSNIdentification": "123-45-6789",
                "PersonBirthDate": "1990-01-15",
                "DriverLicenseIdentification": "DL123456",
            },
        }

        result_json = neo4j_entity_to_senzing_record(entity)
        result = json.loads(result_json)

        # Note: Actual field names depend on mapping configuration
        # These tests verify the structure, not specific field names
        assert "DATA_SOURCE" in result
        assert "RECORD_ID" in result
        assert result["SOURCE_FILE"] == "test.xml"

    def test_empty_properties(self):
        """Test handling of entity with minimal properties."""
        entity = {
            "qname": "j:CrashDriver",
            "neo4j_id": 125,
            "entity_id": "test_125",
            "source": "test.xml",
            "properties": {},
        }

        result_json = neo4j_entity_to_senzing_record(entity)
        result = json.loads(result_json)

        # Should still have base structure
        assert result["DATA_SOURCE"] == "NIEM_GRAPH"
        assert result["RECORD_ID"] == "test_125"
        assert result["ENTITY_TYPE"] == "PERSON"


class TestDateFormatting:
    """Test date formatting for Senzing."""

    def test_iso_date_format(self):
        """Test ISO format dates."""
        assert format_date_for_senzing("2025-01-15") == "2025-01-15"
        assert format_date_for_senzing("1990-05-04") == "1990-05-04"

    def test_us_date_format(self):
        """Test US format dates."""
        result = format_date_for_senzing("01/15/2025")
        assert result == "2025-01-15"

    def test_invalid_date(self):
        """Test handling of invalid dates."""
        # Should return original string if cannot parse
        result = format_date_for_senzing("invalid-date")
        assert result == "invalid-date"

    def test_empty_date(self):
        """Test empty date string."""
        assert format_date_for_senzing("") == ""
        assert format_date_for_senzing(None) is None or format_date_for_senzing(None) == ""


class TestBatchConversion:
    """Test batch entity conversion."""

    def test_batch_convert_multiple_entities(self):
        """Test converting multiple entities at once."""
        entities = [
            {
                "qname": "j:CrashDriver",
                "neo4j_id": 1,
                "entity_id": "e1",
                "source": "test1.xml",
                "properties": {"PersonGivenName": "Peter", "PersonSurName": "Wimsey"},
            },
            {
                "qname": "j:CrashDriver",
                "neo4j_id": 2,
                "entity_id": "e2",
                "source": "test2.xml",
                "properties": {"PersonGivenName": "Harriet", "PersonSurName": "Vane"},
            },
        ]

        result = batch_convert_to_senzing(entities)

        assert len(result) == 2
        assert result[0][0] == "NIEM_GRAPH"  # data_source
        assert result[0][1] == "e1"  # record_id
        assert isinstance(result[0][2], str)  # JSON string

        # Verify JSON is valid
        record1 = json.loads(result[0][2])
        assert "DATA_SOURCE" in record1
        assert "RECORD_ID" in record1

    def test_batch_convert_empty_list(self):
        """Test converting empty entity list."""
        result = batch_convert_to_senzing([])
        assert result == []


class TestConfidenceExtraction:
    """Test confidence score extraction from Senzing results."""

    def test_extract_confidence_from_match_score(self):
        """Test extracting confidence from Senzing match score."""
        senzing_result = {"RESOLVED_ENTITY": {"MATCH_SCORE": 95}}

        confidence = extract_confidence_from_senzing(senzing_result)
        assert 0.0 <= confidence <= 1.0
        assert confidence == 0.95  # 95 / 100

    def test_extract_confidence_high_score(self):
        """Test handling of high match scores."""
        senzing_result = {"RESOLVED_ENTITY": {"MATCH_SCORE": 950}}  # Out of 1000

        confidence = extract_confidence_from_senzing(senzing_result)
        assert 0.0 <= confidence <= 1.0
        assert confidence == 0.95

    def test_extract_confidence_missing_score(self):
        """Test handling of missing match score."""
        senzing_result = {"RESOLVED_ENTITY": {}}

        confidence = extract_confidence_from_senzing(senzing_result)
        assert confidence == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
