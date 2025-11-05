#!/usr/bin/env python3
"""Unit tests for schema design validation."""

from niem_api.services.domain.schema.validation import (
    SchemaDesignValidator,
    ValidationSeverity,
    ValidationErrorType,
    ValidationWarningType,
)


class TestValidateHasSelections:
    """Tests for validate_has_selections method."""

    def test_no_selections_raises_error(self):
        """Test that no selections produces an error."""
        validator = SchemaDesignValidator()
        selections = {
            "nc:Person": False,
            "nc:Location": False,
            "j:Crash": False,
        }

        result = validator.validate(selections, [])

        assert not result.valid
        assert not result.can_proceed
        assert len(result.errors) == 1
        assert result.errors[0].type == ValidationErrorType.NO_SELECTIONS.value
        assert result.errors[0].severity == ValidationSeverity.ERROR

    def test_one_selection_passes(self):
        """Test that one selection passes validation."""
        validator = SchemaDesignValidator()
        selections = {
            "nc:Person": True,
            "nc:Location": False,
            "j:Crash": False,
        }

        result = validator.validate(selections, [])

        assert result.valid
        assert result.can_proceed
        assert len(result.errors) == 0

    def test_multiple_selections_passes(self):
        """Test that multiple selections pass validation."""
        validator = SchemaDesignValidator()
        selections = {
            "nc:Person": True,
            "nc:Location": True,
            "j:Crash": True,
        }

        result = validator.validate(selections, [])

        assert result.valid
        assert result.can_proceed
        assert len(result.errors) == 0

    def test_empty_selections_dict_raises_error(self):
        """Test that empty selections dictionary produces an error."""
        validator = SchemaDesignValidator()
        selections = {}

        result = validator.validate(selections, [])

        assert not result.valid
        assert not result.can_proceed
        assert len(result.errors) == 1
        assert result.errors[0].type == ValidationErrorType.NO_SELECTIONS.value


class TestDetectSparseConnectivity:
    """Tests for detect_sparse_connectivity warning detector."""

    def test_deselected_source_with_selected_target_warns(self):
        """Test warning when source is deselected but target is selected."""
        validator = SchemaDesignValidator()
        selections = {
            "nc:Person": False,  # Deselected
            "nc:Location": True,  # Selected
        }
        element_tree = [
            {
                "qname": "nc:Person",
                "children": ["nc:Location"],
            },
            {
                "qname": "nc:Location",
                "children": [],
            }
        ]

        result = validator.validate(selections, element_tree)

        assert result.valid
        assert result.can_proceed
        assert len(result.warnings) == 1
        assert result.warnings[0].type == ValidationWarningType.SPARSE_CONNECTIVITY.value
        assert "nc:Person" in result.warnings[0].message

    def test_both_selected_no_warning(self):
        """Test no warning when both source and target are selected."""
        validator = SchemaDesignValidator()
        selections = {
            "nc:Person": True,
            "nc:Location": True,
        }
        element_tree = [
            {
                "qname": "nc:Person",
                "children": ["nc:Location"],
            },
            {
                "qname": "nc:Location",
                "children": [],
            }
        ]

        result = validator.validate(selections, element_tree)

        assert result.valid
        assert result.can_proceed
        assert len(result.warnings) == 0


class TestDetectDeepFlattening:
    """Tests for detect_deep_flattening warning detector."""

    def test_deep_deselected_element_warns(self):
        """Test warning for deep elements that are deselected."""
        validator = SchemaDesignValidator()
        selections = {
            "nc:Person": True,
            "nc:PersonName": False,  # Depth 4, deselected
        }
        element_tree = [
            {
                "qname": "nc:Person",
                "depth": 0,
            },
            {
                "qname": "nc:PersonName",
                "depth": 4,  # Greater than threshold of 3
            }
        ]

        result = validator.validate(selections, element_tree)

        assert result.valid
        assert result.can_proceed
        assert len(result.warnings) == 1
        assert result.warnings[0].type == ValidationWarningType.DEEP_FLATTENING.value
        assert "nc:PersonName" in result.warnings[0].message

    def test_shallow_element_no_warning(self):
        """Test no warning for shallow elements."""
        validator = SchemaDesignValidator()
        selections = {
            "nc:Person": True,
            "nc:PersonName": False,  # Depth 2, below threshold
        }
        element_tree = [
            {
                "qname": "nc:Person",
                "depth": 0,
            },
            {
                "qname": "nc:PersonName",
                "depth": 2,  # Below threshold
            }
        ]

        result = validator.validate(selections, element_tree)

        assert result.valid
        assert result.can_proceed
        assert len(result.warnings) == 0


class TestDetectInsufficientEndpoints:
    """Tests for detect_insufficient_endpoints warning detector."""

    def test_association_with_one_endpoint_warns(self):
        """Test warning for association with only one endpoint."""
        validator = SchemaDesignValidator()
        selections = {
            "j:CrashDriverAssociation": True,
            "nc:Person": True,  # Only one endpoint selected
            "j:Crash": False,
        }
        element_tree = [
            {
                "qname": "j:CrashDriverAssociation",
                "node_type": "association",
                "children": ["nc:Person", "j:Crash"],
            },
            {
                "qname": "nc:Person",
                "node_type": "object",
                "children": [],
            },
            {
                "qname": "j:Crash",
                "node_type": "object",
                "children": [],
            }
        ]

        result = validator.validate(selections, element_tree)

        assert result.valid
        assert result.can_proceed
        assert len(result.warnings) == 1
        assert result.warnings[0].type == ValidationWarningType.INSUFFICIENT_ENDPOINTS.value
        assert "CrashDriverAssociation" in result.warnings[0].message

    def test_association_with_two_endpoints_no_warning(self):
        """Test no warning for association with two endpoints."""
        validator = SchemaDesignValidator()
        selections = {
            "j:CrashDriverAssociation": True,
            "nc:Person": True,
            "j:Crash": True,
        }
        element_tree = [
            {
                "qname": "j:CrashDriverAssociation",
                "node_type": "association",
                "children": ["nc:Person", "j:Crash"],
            },
            {
                "qname": "nc:Person",
                "node_type": "object",
                "children": [],
            },
            {
                "qname": "j:Crash",
                "node_type": "object",
                "children": [],
            }
        ]

        result = validator.validate(selections, element_tree)

        assert result.valid
        assert result.can_proceed
        assert len(result.warnings) == 0
