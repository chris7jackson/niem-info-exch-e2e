# Validation Error Handling - Implementation Summary

## Problem
Validation errors from CMF tool were generic and unhelpful:
```
Warning: 2 files failed to process.
CrashDriverInvalid.xml: Validation error:
```

No details about what failed, where, or why.

## Solution
Implemented standardized error propagation with structured validation results throughout the validation pipeline.

## Changes Made

### 1. New Structured Error Models (`api/src/niem_api/models/models.py`)

```python
class ValidationError(BaseModel):
    """Structured validation error from CMF tool or other validators."""
    file: str                      # File being validated
    line: Optional[int] = None     # Line number if available
    column: Optional[int] = None   # Column number if available
    message: str                   # Error message
    severity: str = "error"        # 'error', 'warning', 'info'
    rule: Optional[str] = None     # Validation rule identifier
    context: Optional[str] = None  # Additional context

class ValidationResult(BaseModel):
    """Result of a validation operation."""
    valid: bool
    errors: List[ValidationError] = []
    warnings: List[ValidationError] = []
    summary: str                   # Human-readable summary
    raw_output: Optional[str] = None  # Full validator output for debugging
```

### 2. CMF Output Parser (`api/src/niem_api/clients/cmf_client.py`)

Added `parse_cmf_validation_output()` function:
- Parses CMF tool stdout/stderr for error markers `[error]`, `[warning]`
- Extracts file:line:column location information
- Creates structured error dictionaries
- Handles both structured and unstructured error formats
- Pattern: `[severity] filename:line:column: message`

Example parsed output:
```python
{
    "errors": [
        {
            "file": "test.xml",
            "line": 42,
            "column": 15,
            "message": "cvc-complex-type.2.4.a: Invalid content",
            "severity": "error"
        }
    ],
    "warnings": [],
    "has_errors": True
}
```

### 3. Enhanced Validation Handler (`api/src/niem_api/handlers/ingest.py`)

Updated `_validate_xml_content()`:
- Calls `parse_cmf_validation_output()` after CMF validation
- Builds `ValidationResult` with structured errors
- Returns detailed HTTPException with validation_result in detail dict
- Logs first 5 errors with file:line:column information

Updated `_create_error_result()`:
- Accepts optional `validation_result` parameter
- Includes `validation_details` in error response when available

Updated `_process_single_file()`:
- Extracts validation_result from HTTPException detail dict
- Passes validation_result to `_create_error_result()`

### 4. Test Coverage

Created two test files:
- `api/tests/unit/clients/test_cmf_validation_parsing.py` - Tests CMF output parsing
- `api/tests/unit/handlers/test_ingest_error_handling.py` - Tests error handling flow

## API Response Format

### Before (generic error)
```json
{
  "results": [
    {
      "filename": "CrashDriverInvalid.xml",
      "status": "failed",
      "error": "Validation error: CrashDriverInvalid.xml"
    }
  ]
}
```

### After (detailed errors)
```json
{
  "results": [
    {
      "filename": "CrashDriverInvalid.xml",
      "status": "failed",
      "error": "Validation error: CrashDriverInvalid.xml",
      "validation_details": {
        "valid": false,
        "errors": [
          {
            "file": "CrashDriverInvalid.xml",
            "line": 42,
            "column": 15,
            "message": "cvc-complex-type.2.4.a: Invalid content was found...",
            "severity": "error",
            "rule": null,
            "context": null
          },
          {
            "file": "CrashDriverInvalid.xml",
            "line": 58,
            "column": 3,
            "message": "Element 'nc:InvalidElement' is not allowed...",
            "severity": "error",
            "rule": null,
            "context": null
          }
        ],
        "warnings": [],
        "summary": "Validation failed with 2 error(s) and 0 warning(s)",
        "raw_output": "[error] CrashDriverInvalid.xml:42:15: ..."
      }
    }
  ]
}
```

## Benefits

1. **Actionable errors**: Users see exactly what's wrong, where it is, and can fix it
2. **Multiple errors**: All validation errors shown, not just first failure
3. **Severity levels**: Distinguishes between errors, warnings, and info
4. **Debugging support**: Raw CMF output preserved for troubleshooting
5. **Consistent structure**: Same error format across all validation points
6. **UI-friendly**: Structured data easy to display in expandable error components

## Migration Path

The changes are **backward compatible**:
- Error responses still include the basic `error` field
- New `validation_details` field is optional
- Existing error handling continues to work
- UI can progressively enhance to show detailed errors

## Usage Example

Client code can now display detailed validation errors:

```typescript
if (result.status === "failed" && result.validation_details) {
  const { errors } = result.validation_details;
  errors.forEach(error => {
    console.error(
      `${error.file}:${error.line}:${error.column} - ${error.message}`
    );
  });
}
```

## Edge Cases Handled

- ✅ CMF errors with location info (file:line:column)
- ✅ CMF errors without location info (generic errors)
- ✅ Multiple errors in single file
- ✅ Errors in stderr vs stdout
- ✅ Mixed error and warning messages
- ✅ Unstructured error output (fallback to generic error)
- ✅ Empty validation output (no errors)
- ✅ CMF tool timeouts and crashes

## Future Enhancements

1. Add correlation_id to track errors across request lifecycle
2. Enhance UI to show errors inline with file upload
3. Add "copy error" button for easy sharing
4. Link error rules to NIEM documentation
5. Suggest fixes based on common error patterns
