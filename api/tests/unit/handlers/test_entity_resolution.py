#!/usr/bin/env python3
"""
Unit tests for entity resolution handler functions.

Tests internal helper functions in isolation with mocked dependencies.

Run with: pytest api/tests/unit/handlers/test_entity_resolution.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from niem_api.handlers.entity_resolution import (
    _create_entity_key,
    _group_entities_by_key,
    _count_senzing_mappable_fields,
    _load_senzing_field_mappings,
)
from niem_api.services.entity_to_senzing import (
    format_date_for_senzing,
    extract_confidence_from_senzing,
)


class TestEntityKeyCreation:
    """Test entity key generation for text-based matching."""

    def test_full_name_key(self):
        """Test key generation from PersonFullName."""
        entity = {"properties": {"PersonFullName": "Jason Ohlendorf"}}

        key = _create_entity_key(entity)
        assert key == "jason_ohlendorf"

    def test_given_surname_key(self):
        """Test key generation from GivenName + SurName."""
        entity = {"properties": {"PersonGivenName": "Peter", "PersonSurName": "Wimsey"}}

        key = _create_entity_key(entity)
        assert key == "peter_wimsey"

    def test_empty_properties(self):
        """Test handling of entity with no name properties."""
        entity = {"properties": {}}

        key = _create_entity_key(entity)
        assert key == ""

    def test_only_given_name(self):
        """Test that only given name is insufficient."""
        entity = {"properties": {"PersonGivenName": "Peter"}}

        key = _create_entity_key(entity)
        assert key == ""  # Need both given and surname

    def test_name_normalization(self):
        """Test that names are normalized (lowercase, spaces to underscores)."""
        entity = {"properties": {"PersonFullName": "JOHN DOE"}}

        key = _create_entity_key(entity)
        assert key == "john_doe"


class TestEntityGrouping:
    """Test grouping entities by matching keys."""

    def test_group_duplicates(self):
        """Test grouping entities with same names."""
        entities = [
            {"neo4j_id": 1, "properties": {"PersonGivenName": "Peter", "PersonSurName": "Wimsey"}},
            {"neo4j_id": 2, "properties": {"PersonGivenName": "Peter", "PersonSurName": "Wimsey"}},
            {"neo4j_id": 3, "properties": {"PersonGivenName": "Harriet", "PersonSurName": "Vane"}},
        ]

        groups = _group_entities_by_key(entities)

        # Should have one group (peter_wimsey with 2 entities)
        # Harriet is unique so not included in duplicate groups
        assert "peter_wimsey" in groups
        assert len(groups["peter_wimsey"]) == 2
        assert groups["peter_wimsey"][0]["neo4j_id"] == 1
        assert groups["peter_wimsey"][1]["neo4j_id"] == 2

        # Unique entities not in groups
        assert "harriet_vane" not in groups

    def test_no_duplicates(self):
        """Test when all entities are unique."""
        entities = [
            {"neo4j_id": 1, "properties": {"PersonGivenName": "Peter", "PersonSurName": "Wimsey"}},
            {"neo4j_id": 2, "properties": {"PersonGivenName": "Harriet", "PersonSurName": "Vane"}},
            {"neo4j_id": 3, "properties": {"PersonGivenName": "Lord", "PersonSurName": "Peter"}},
        ]

        groups = _group_entities_by_key(entities)

        # No duplicates, so empty dict
        assert groups == {}

    def test_empty_entity_list(self):
        """Test with empty entity list."""
        groups = _group_entities_by_key([])
        assert groups == {}


class TestSenzingFieldMapping:
    """Test Senzing field mapping configuration."""

    @patch("niem_api.handlers.entity_resolution.Path")
    @patch("builtins.open")
    @patch("yaml.safe_load")
    def test_load_field_mappings(self, mock_yaml, mock_open, mock_path):
        """Test loading field mappings from YAML."""
        # Mock file exists
        mock_path.return_value.exists.return_value = True

        # Mock YAML content
        mock_yaml.return_value = {
            "field_mappings": {"nc_PersonFullName": "PRIMARY_NAME_FULL", "nc_PersonGivenName": "PRIMARY_NAME_FIRST"},
            "custom_mappings": {"custom_Field": "CUSTOM_FIELD"},
        }

        # Clear cache
        import niem_api.handlers.entity_resolution as er_module

        er_module._SENZING_FIELD_MAPPINGS = None

        mappings = _load_senzing_field_mappings()

        # Should merge field_mappings and custom_mappings
        assert len(mappings) == 3
        assert mappings["nc_PersonFullName"] == "PRIMARY_NAME_FULL"
        assert mappings["custom_Field"] == "CUSTOM_FIELD"

    def test_count_mappable_fields(self):
        """Test counting properties that map to Senzing fields."""
        with patch("niem_api.handlers.entity_resolution._load_senzing_field_mappings") as mock_load:
            mock_load.return_value = {
                "nc_PersonFullName": "PRIMARY_NAME_FULL",
                "nc_PersonGivenName": "PRIMARY_NAME_FIRST",
                "nc_PersonSurName": "PRIMARY_NAME_LAST",
            }

            # Node with 2 mappable fields
            node_keys = [
                "id",
                "qname",
                "nc_PersonFullName",  # Mappable
                "nc_PersonGivenName",  # Mappable
                "some_other_field",
            ]

            count = _count_senzing_mappable_fields(node_keys)
            assert count == 2

    def test_count_with_prefixes(self):
        """Test counting fields with long prefixes."""
        with patch("niem_api.handlers.entity_resolution._load_senzing_field_mappings") as mock_load:
            mock_load.return_value = {"nc_PersonFullName": "PRIMARY_NAME_FULL"}

            # Property with long prefix should still match
            node_keys = ["role_of_person__nc_PersonFullName"]  # Should match nc_PersonFullName

            count = _count_senzing_mappable_fields(node_keys)
            assert count == 1


class TestDateFormatting:
    """Test date formatting for Senzing."""

    def test_iso_date_unchanged(self):
        """Test that ISO dates pass through."""
        date = format_date_for_senzing("2025-01-15")
        assert date == "2025-01-15"

    def test_us_date_conversion(self):
        """Test US date format conversion."""
        date = format_date_for_senzing("01/15/2025")
        assert date == "2025-01-15"

    def test_invalid_date_returns_original(self):
        """Test that invalid dates return original."""
        date = format_date_for_senzing("not-a-date")
        assert date == "not-a-date"


class TestConfidenceExtraction:
    """Test Senzing confidence score extraction."""

    def test_score_0_to_100_range(self):
        """Test scores in 0-100 range."""
        result = {"RESOLVED_ENTITY": {"MATCH_SCORE": 85}}
        confidence = extract_confidence_from_senzing(result)
        assert confidence == 0.85

    def test_score_0_to_1000_range(self):
        """Test scores in 0-1000 range."""
        result = {"RESOLVED_ENTITY": {"MATCH_SCORE": 850}}
        confidence = extract_confidence_from_senzing(result)
        assert confidence == 0.85

    def test_score_0_to_1_range(self):
        """Test scores already in 0-1 range."""
        result = {"RESOLVED_ENTITY": {"MATCH_SCORE": 0.95}}
        confidence = extract_confidence_from_senzing(result)
        assert confidence == 0.95

    def test_missing_score(self):
        """Test handling of missing match score."""
        result = {"RESOLVED_ENTITY": {}}
        confidence = extract_confidence_from_senzing(result)
        assert confidence == 0.0

    def test_score_capped_at_1(self):
        """Test that confidence is capped at 1.0."""
        result = {"RESOLVED_ENTITY": {"MATCH_SCORE": 9999}}
        confidence = extract_confidence_from_senzing(result)
        assert confidence <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
