# UI Validation Error Display - Implementation Summary

## Changes Made

### Backend Changes

#### 1. Structured Error Models (`api/src/niem_api/models/models.py`)
```python
class ValidationError(BaseModel):
    file: str
    line: Optional[int]
    column: Optional[int]
    message: str
    severity: str
    rule: Optional[str]
    context: Optional[str]

class ValidationResult(BaseModel):
    valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    summary: str
    raw_output: Optional[str]
```

#### 2. CMF Output Parser (`api/src/niem_api/clients/cmf_client.py`)
- Added `parse_cmf_validation_output()` to extract structured errors from CMF tool
- Parses `[error]` and `[warning]` markers with file:line:column locations
- Handles both structured and unstructured error formats

#### 3. Enhanced Validation Handler (`api/src/niem_api/handlers/ingest.py`)
- `_validate_xml_content()` now returns structured `ValidationResult` in HTTPException detail
- `_create_error_result()` includes optional `validation_details` field
- `_process_single_file()` propagates validation results to API response
- Added helpful default messages when validation_details not available

### Frontend Changes

#### 1. Updated TypeScript Types (`ui/src/lib/api.ts`)
```typescript
export interface ValidationError {
  file: string;
  line?: number;
  column?: number;
  message: string;
  severity: string;
  rule?: string;
  context?: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  summary: string;
  raw_output?: string;
}

export interface IngestFileResult {
  filename: string;
  status: string;
  nodes_created?: number;
  relationships_created?: number;
  error?: string;
  validation_details?: ValidationResult;  // NEW
}
```

#### 2. New Validation Errors Component (`ui/src/components/IngestValidationErrors.tsx`)
- Expandable/collapsible validation error display
- Shows errors with file:line:column locations
- Displays severity badges (errors vs warnings)
- Includes raw CMF output in expandable section
- Color-coded by severity (red for errors, yellow for warnings)

#### 3. Updated IngestResults Component (`ui/src/components/IngestResults.tsx`)
- Now imports and uses `IngestValidationErrors` component
- Shows "Validation failed" instead of generic error when validation_details available
- Renders detailed validation errors below each failed file

## User Experience Improvements

### Before
```
Warning: 2 files failed to process.
CrashDriverInvalid.xml: Validation error:
CrashDriverInvalidTest.xml: Validation error:
```

### After
**Collapsed State:**
```
[▶] ⚠ Validation Failed: CrashDriverInvalid.xml
    Validation failed with 2 error(s) and 0 warning(s)
    [2 errors]
```

**Expanded State:**
```
[▼] ⚠ Validation Failed: CrashDriverInvalid.xml
    Validation failed with 2 error(s) and 0 warning(s)
    [2 errors]

    Errors (2)
    ┌────────────────────────────────────────────┐
    │ ⚠ CrashDriverInvalid.xml:42:15    [ERROR]  │
    │ cvc-complex-type.2.4.a: Invalid content    │
    │ was found starting with element            │
    │ 'nc:InvalidElement'. Expected is           │
    │ ( "{http://...}PersonBirthDate" ).         │
    └────────────────────────────────────────────┘

    ┌────────────────────────────────────────────┐
    │ ⚠ CrashDriverInvalid.xml:58:3     [ERROR]  │
    │ Element 'nc:InvalidElement' is not allowed │
    │ for content model '(nc:PersonBirthDate)'   │
    └────────────────────────────────────────────┘

    [▶] Show raw validation output
```

## Features

✅ **Detailed error locations** - Line and column numbers for each error
✅ **Multiple errors shown** - All validation errors displayed, not just first
✅ **Severity levels** - Distinguishes errors from warnings
✅ **Expandable interface** - Collapsed by default to reduce clutter
✅ **Raw output access** - Full CMF output available for debugging
✅ **Helpful fallback messages** - Clear guidance when detailed errors unavailable
✅ **Visual hierarchy** - Color coding and icons for quick scanning
✅ **Mobile friendly** - Responsive design with proper text wrapping

## API Response Format

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
            "message": "cvc-complex-type.2.4.a: Invalid content...",
            "severity": "error",
            "rule": null,
            "context": null
          }
        ],
        "warnings": [],
        "summary": "Validation failed with 1 error(s) and 0 warning(s)",
        "raw_output": "[error] CrashDriverInvalid.xml:42:15: ..."
      }
    }
  ]
}
```

## Backward Compatibility

✅ Fully backward compatible - `validation_details` field is optional
✅ Existing error handling continues to work
✅ UI gracefully handles missing validation_details
✅ Default error messages provided when detailed errors unavailable

## Testing

To test the validation error display:

1. Start the system: `docker compose up -d`
2. Upload a valid schema (e.g., `samples/CrashDriver-cmf/CrashDriver.xsd`)
3. Activate the schema
4. Try uploading an invalid XML file:
   - `samples/CrashDriver-cmf/CrashDriverInvalid.xml`
5. Click on the file in the results to expand validation details
6. Click "Show raw validation output" to see full CMF output

## Future Enhancements

- Add "Copy error" button for easy sharing
- Link error rules to NIEM documentation
- Suggest fixes based on common error patterns
- Add inline file preview showing error location
- Export validation report as PDF/HTML
