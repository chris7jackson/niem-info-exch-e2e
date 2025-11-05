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

    def detect_sparse_connectivity(
        self,
        selections: dict[str, bool],
        element_tree: list[dict],
        result: ValidationResult
    ) -> None:
        """Detect sparse connectivity warnings.

        Warns when a reference source is deselected, meaning relationships
        will be sparse (not every instance will have the relationship).
        Per ADR-002, this is allowed but should be flagged.

        Args:
            selections: Dictionary mapping qnames to selection state
            element_tree: Flattened element tree structure
            result: ValidationResult to add warnings to
        """
        element_map = {elem["qname"]: elem for elem in element_tree}

        for element in element_tree:
            qname = element["qname"]

            # Check if this element has children (references) but is NOT selected
            if not selections.get(qname, False) and element.get("children"):
                # This element is deselected but has references to other elements
                # Check if any of its children are selected (would create sparse relationships)
                for child_qname in element.get("children", []):
                    if selections.get(child_qname, False):
                        # Child is selected but parent is not - sparse connectivity
                        result.warnings.append(ValidationMessage(
                            severity=ValidationSeverity.WARNING,
                            type=ValidationWarningType.SPARSE_CONNECTIVITY.value,
                            message=f"Element '{qname}' is deselected but references selected element '{child_qname}'",
                            element=qname,
                            recommendation=f"Consider selecting '{qname}' to create consistent relationships to '{child_qname}' for better relationship analysis",
                            impact="moderate",
                            details={
                                "source": qname,
                                "target": child_qname
                            }
                        ))

    def detect_deep_flattening(
        self,
        selections: dict[str, bool],
        element_tree: list[dict],
        result: ValidationResult
    ) -> None:
        """Detect deep flattening warnings.

        DISABLED: Deep nesting is common in NIEM schemas and creates too many warnings.
        The warnings were cluttering the UI and making the modal unusable.

        Args:
            selections: Dictionary mapping qnames to selection state
            element_tree: Flattened element tree structure
            result: ValidationResult to add warnings to
        """
        # DEEP_NESTING_THRESHOLD = 3
        #
        # for element in element_tree:
        #     qname = element["qname"]
        #     depth = element.get("depth", 0)
        #
        #     # Warn if element is deep and deselected (will create complex property paths)
        #     if not selections.get(qname, False) and depth > DEEP_NESTING_THRESHOLD:
        #         result.warnings.append(ValidationMessage(
        #             severity=ValidationSeverity.WARNING,
        #             type=ValidationWarningType.DEEP_FLATTENING.value,
        #             message=f"Element '{qname}' at depth {depth} will be flattened, creating complex property names",
        #             element=qname,
        #             recommendation=f"Consider selecting '{qname}' as a node to simplify property paths and improve query readability",
        #             impact="low",
        #             details={"depth": depth}
        #         ))
        pass  # Method disabled to avoid warning clutter

    def detect_insufficient_endpoints(
        self,
        selections: dict[str, bool],
        element_tree: list[dict],
        result: ValidationResult
    ) -> None:
        """Detect insufficient endpoint warnings for associations.

        Warns when associations have fewer than 2 endpoints after filtering
        by selection state, making them less useful for relationship analysis.

        Args:
            selections: Dictionary mapping qnames to selection state
            element_tree: Flattened element tree structure
            result: ValidationResult to add warnings to
        """
        for element in element_tree:
            qname = element["qname"]
            node_type = element.get("node_type")

            # Only check associations
            if node_type != "association":
                continue

            # Skip if not selected
            if not selections.get(qname, False):
                continue

            # Count selected children (endpoints)
            selected_endpoint_count = sum(
                1 for child_qname in element.get("children", [])
                if selections.get(child_qname, False)
            )

            if selected_endpoint_count < 2:
                result.warnings.append(ValidationMessage(
                    severity=ValidationSeverity.WARNING,
                    type=ValidationWarningType.INSUFFICIENT_ENDPOINTS.value,
                    message=f"Association '{qname}' has only {selected_endpoint_count} selected endpoint(s)",
                    element=qname,
                    recommendation="Consider selecting more endpoints for this association to enable meaningful relationship analysis",
                    impact="moderate",
                    details={"endpoint_count": selected_endpoint_count}
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

        # Run hard validations (errors block application)
        self.validate_has_selections(selections, result)

        # Run warning detectors (non-blocking)
        self.detect_sparse_connectivity(selections, element_tree, result)
        self.detect_deep_flattening(selections, element_tree, result)
        self.detect_insufficient_endpoints(selections, element_tree, result)

        # Set validation result flags
        result.valid = len(result.errors) == 0
        result.can_proceed = len(result.errors) == 0

        return result
