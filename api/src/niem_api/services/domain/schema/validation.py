#!/usr/bin/env python3
"""Schema design validation for graph schema designer.

This module validates user schema design selections to ensure:
- At least one node is selected
- Reference endpoints are valid
- Property names don't conflict after flattening
- Neo4j identifier constraints are met

It also detects warnings and provides suggestions for best practices.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ValidationSeverity(str, Enum):
    """Severity level for validation messages."""
    ERROR = "error"          # Blocks design application
    WARNING = "warning"      # Allows but warns user
    SUGGESTION = "suggestion"  # Helpful hints


class ValidationErrorType(str, Enum):
    """Types of validation errors that block design application."""
    NO_SELECTIONS = "no_selections"
    PROPERTY_CONFLICT = "property_conflict"
    INVALID_IDENTIFIER = "invalid_identifier"


class ValidationWarningType(str, Enum):
    """Types of validation warnings that allow but suggest caution."""
    SPARSE_CONNECTIVITY = "sparse_connectivity"
    DEEP_FLATTENING = "deep_flattening"
    INSUFFICIENT_ENDPOINTS = "insufficient_endpoints"
    INFORMATION_LOSS = "information_loss"


@dataclass
class ValidationMessage:
    """A validation message (error, warning, or suggestion)."""
    severity: ValidationSeverity
    type: str
    message: str
    element: Optional[str] = None
    recommendation: Optional[str] = None
    impact: Optional[str] = None  # low, moderate, high
    details: Optional[dict] = None


@dataclass
class ValidationSummary:
    """Summary statistics for the design validation."""
    nodes_selected: int = 0
    nodes_flattened: int = 0
    relationships_created: int = 0
    properties_flattened: int = 0
    total_elements: int = 0


@dataclass
class ValidationResult:
    """Result of schema design validation."""
    valid: bool
    can_proceed: bool  # False if errors, True if only warnings
    errors: list[ValidationMessage] = field(default_factory=list)
    warnings: list[ValidationMessage] = field(default_factory=list)
    suggestions: list[ValidationMessage] = field(default_factory=list)
    summary: Optional[ValidationSummary] = None


class SchemaDesignValidator:
    """Validates schema design selections before application.

    This validator checks for errors that would prevent successful graph
    creation and provides warnings/suggestions for analysis quality.
    """

    def __init__(self):
        """Initialize the validator."""
        pass

    def validate_has_selections(
        self,
        selections: dict[str, bool],
        result: ValidationResult
    ) -> None:
        """Validate that at least one node is selected.

        Args:
            selections: Dictionary mapping qnames to selection state
            result: ValidationResult to add errors to
        """
        selected_count = sum(1 for is_selected in selections.values() if is_selected)

        if selected_count == 0:
            result.errors.append(ValidationMessage(
                severity=ValidationSeverity.ERROR,
                type=ValidationErrorType.NO_SELECTIONS.value,
                message="Must select at least one element to create graph nodes",
                recommendation="Select at least one element from the tree to proceed with schema design",
                impact="high"
            ))

    def validate(
        self,
        selections: dict[str, bool],
        element_tree: list[dict]
    ) -> ValidationResult:
        """Validate schema design selections.

        Args:
            selections: Dictionary mapping qnames to selection state
            element_tree: Flattened element tree structure

        Returns:
            ValidationResult with errors, warnings, and suggestions
        """
        result = ValidationResult(valid=True, can_proceed=True)

        # Run validation methods
        self.validate_has_selections(selections, result)
        # TODO: More validation methods
        # - validate_property_conflicts()
        # - validate_neo4j_identifiers()
        # - detect_sparse_connectivity()
        # - detect_deep_flattening()
        # - detect_insufficient_endpoints()

        # Set validation result flags
        result.valid = len(result.errors) == 0
        result.can_proceed = len(result.errors) == 0

        return result
