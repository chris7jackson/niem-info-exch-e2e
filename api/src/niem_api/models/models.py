#!/usr/bin/env python3

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
    niem_ndr_report: NiemNdrReport | None = None
    import_validation_report: ImportValidationReport | None = None
    is_active: bool


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
