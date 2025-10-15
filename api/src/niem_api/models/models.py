#!/usr/bin/env python3

from typing import List, Optional, Dict, Any
from pydantic import BaseModel


# Pydantic Models


class NiemNdrViolation(BaseModel):
    type: str  # 'error', 'warning', 'info'
    rule: str
    message: str
    location: str
    file: Optional[str] = None  # Source file where violation was found


class NiemNdrReport(BaseModel):
    status: str  # 'pass', 'fail', 'error'
    message: str
    conformance_target: str
    violations: List[NiemNdrViolation] = []
    summary: Dict[str, int] = {}
    detected_schema_type: Optional[str] = None  # 'ref', 'ext', 'sub', or None
    rules_applied: Optional[int] = None  # Number of rules applied


class SchevalIssue(BaseModel):
    """Schematron validation issue with precise line/column information."""
    file: str  # File being validated
    line: int  # Line number where issue occurs
    column: int  # Column number where issue occurs
    message: str  # Error message
    severity: str  # 'error', 'warning', 'info'
    rule: Optional[str] = None  # Validation rule identifier (e.g., "Rule 7-10")


class SchevalReport(BaseModel):
    """Schematron validation report from scheval tool."""
    status: str  # 'pass', 'fail', 'error'
    message: str
    conformance_target: str
    errors: List[SchevalIssue] = []
    warnings: List[SchevalIssue] = []
    summary: Dict[str, int] = {}  # Contains 'total_issues', 'error_count', 'warning_count'
    metadata: Dict[str, Any] = {}  # Additional metadata about the validation


class ImportInfo(BaseModel):
    schema_location: str
    namespace: str
    status: str  # 'satisfied' or 'missing'
    expected_filename: Optional[str] = None


class NamespaceUsage(BaseModel):
    prefix: str
    namespace_uri: str
    status: str  # 'satisfied' or 'missing'


class FileImportInfo(BaseModel):
    filename: str
    imports: List[ImportInfo] = []
    namespaces_used: List[NamespaceUsage] = []


class ImportValidationReport(BaseModel):
    status: str  # 'pass' or 'fail'
    files: List[FileImportInfo] = []
    summary: str
    total_files: int = 0
    total_imports: int = 0
    total_namespaces: int = 0
    missing_count: int = 0


class SchemaResponse(BaseModel):
    schema_id: str
    scheval_report: Optional[SchevalReport] = None
    import_validation_report: Optional[ImportValidationReport] = None
    is_active: bool


class ResetRequest(BaseModel):
    schemas: bool = False
    data: bool = False
    neo4j: bool = False
    dry_run: bool = True
    confirm_token: Optional[str] = None


class ResetResponse(BaseModel):
    counts: Dict[str, int]
    confirm_token: Optional[str] = None
    message: str


class ValidationError(BaseModel):
    """Structured validation error from CMF tool or other validators."""
    file: str  # File being validated
    line: Optional[int] = None  # Line number if available
    column: Optional[int] = None  # Column number if available
    message: str  # Error message
    severity: str = "error"  # 'error', 'warning', 'info'
    rule: Optional[str] = None  # Validation rule identifier
    context: Optional[str] = None  # Additional context (e.g., element path)


class ValidationResult(BaseModel):
    """Result of a validation operation."""
    valid: bool
    errors: List[ValidationError] = []
    warnings: List[ValidationError] = []
    summary: str  # Human-readable summary