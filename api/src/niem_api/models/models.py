#!/usr/bin/env python3

from typing import Any

from pydantic import BaseModel

# Pydantic Models


class NiemNdrViolation(BaseModel):
    type: str  # 'error', 'warning', 'info'
    rule: str
    message: str
    location: str
    file: str | None = None  # Source file where violation was found


class NiemNdrReport(BaseModel):
    status: str  # 'pass', 'fail', 'error'
    message: str
    conformance_target: str
    violations: list[NiemNdrViolation] = []
    summary: dict[str, int] = {}
    detected_schema_type: str | None = None  # 'ref', 'ext', 'sub', or None
    rules_applied: int | None = None  # Number of rules applied


class SchevalIssue(BaseModel):
    """Schematron validation issue with precise line/column information."""

    file: str  # File being validated
    line: int | None = None  # Line number where issue occurs (None for tool-level errors)
    column: int | None = None  # Column number where issue occurs (None for tool-level errors)
    message: str  # Error message
    severity: str  # 'error', 'warning', 'info'
    rule: str | None = None  # Validation rule identifier (e.g., "Rule 7-10")


class SchevalReport(BaseModel):
    """Schematron validation report from scheval tool."""

    status: str  # 'pass', 'fail', 'error'
    message: str
    conformance_target: str
    errors: list[SchevalIssue] = []
    warnings: list[SchevalIssue] = []
    summary: dict[str, int] = {}  # 'total_issues', 'error_count', 'warning_count'
    metadata: dict[str, Any] = {}  # Additional metadata about the validation


class ImportInfo(BaseModel):
    schema_location: str
    namespace: str
    status: str  # 'satisfied' or 'missing'
    expected_filename: str | None = None


class NamespaceUsage(BaseModel):
    prefix: str
    namespace_uri: str
    status: str  # 'satisfied' or 'missing'


class FileImportInfo(BaseModel):
    filename: str
    imports: list[ImportInfo] = []
    namespaces_used: list[NamespaceUsage] = []


class ImportValidationReport(BaseModel):
    status: str  # 'pass' or 'fail'
    files: list[FileImportInfo] = []
    summary: str
    total_files: int = 0
    total_imports: int = 0
    total_namespaces: int = 0
    missing_count: int = 0


class SchemaResponse(BaseModel):
    schema_id: str
    scheval_report: SchevalReport | None = None
    import_validation_report: ImportValidationReport | None = None
    is_active: bool
    warnings: list[str] = []


class ResetRequest(BaseModel):
    schemas: bool = False
    data: bool = False
    neo4j: bool = False
    dry_run: bool = True
    confirm_token: str | None = None


class ResetResponse(BaseModel):
    counts: dict[str, int]
    confirm_token: str | None = None
    message: str


class ValidationError(BaseModel):
    """Structured validation error from CMF tool or other validators."""
    file: str  # File being validated
    line: int | None = None  # Line number if available
    column: int | None = None  # Column number if available
    message: str  # Error message
    severity: str = "error"  # 'error', 'warning', 'info'
    rule: str | None = None  # Validation rule identifier
    context: str | None = None  # Additional context (e.g., element path)


class ValidationResult(BaseModel):
    """Result of a validation operation."""
    valid: bool
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []
    summary: str  # Human-readable summary


# Entity Resolution Models

class NodeTypeInfo(BaseModel):
    """Information about a node type available for entity resolution."""
    qname: str  # Qualified name (e.g., 'j:CrashDriver')
    label: str  # Neo4j label (e.g., 'j_CrashDriver')
    count: int  # Number of entities of this type
    nameFields: list[str]  # Available name fields for matching
    category: str | None = None  # Entity category: person, organization, location, address, vehicle, other
    recommended: bool = False  # Whether this type is recommended for entity resolution


class EntityResolutionRequest(BaseModel):
    """Request to run entity resolution with selected node types."""
    selectedNodeTypes: list[str] = []  # List of qnames to resolve


class EntityResolutionResponse(BaseModel):
    """Response from entity resolution operation."""
    status: str  # 'success' or 'error'
    message: str
    entitiesExtracted: int = 0
    duplicateGroupsFound: int = 0
    resolvedEntitiesCreated: int = 0
    relationshipsCreated: int = 0
    entitiesResolved: int = 0  # Total entities involved in resolution
    nodeTypesProcessed: list[str] = []  # List of qnames that were processed
