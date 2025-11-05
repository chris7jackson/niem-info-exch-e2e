#!/usr/bin/env python3
"""Unit tests for schema design validation."""

from niem_api.services.domain.schema.validation import (
    SchemaDesignValidator,
    ValidationSeverity,
    ValidationErrorType,
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
