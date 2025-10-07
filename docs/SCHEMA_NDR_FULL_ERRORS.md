# Schema Upload - Full NDR Error Display

## Problem
When uploading schemas with NIEM NDR violations, errors were truncated:
```
Schema upload rejected due to NIEM NDR validation failures.
Found 7 NIEM NDR violations across 1 files:
Rule 7-38: ...; Rule 7-38: ...; Rule 7-38: ...
and 4 more
```

Users couldn't see all violations or which file they were in.

## Solution
Return full NDR report in API error response and display all violations in UI, grouped by file.

## Changes Made

### Backend (`api/src/niem_api/handlers/schema.py`)

**Before:**
```python
if status == "fail":
    error_messages = [v["message"] for v in all_violations if v["type"] == "error"]
    violation_summary = f"Found {total_error_count} NIEM NDR violations..."
    if error_messages:
        violation_summary += f": {'; '.join(error_messages[:3])}"  # ❌ Truncated
        if len(error_messages) > 3:
            violation_summary += f" ... and {len(error_messages) - 3} more"

    raise HTTPException(
        status_code=400,
        detail=f"Schema upload rejected... {violation_summary}"  # ❌ String only
    )
```

**After:**
```python
if status == "fail":
    raise HTTPException(
        status_code=400,
        detail={
            "message": f"Schema upload rejected... Found {total_error_count} violations...",
            "niem_ndr_report": niem_ndr_report.model_dump()  # ✅ Full report
        }
    )
```

### Frontend (`ui/src/components/SchemaManager.tsx`)

**Before:**
```typescript
// Built truncated error message in UI
let errorMessage = `...Found ${totalErrors} violations across ${fileCount} files:\n\n`;
const filesToShow = Object.keys(violationsByFile).slice(0, 3);  // ❌ Only 3 files
filesToShow.forEach((file) => {
  violations.slice(0, 3).forEach((v) => { ... });  // ❌ Only 3 violations per file
  if (violations.length > 3) {
    errorMessage += `... and ${violations.length - 3} more violations\n`;
  }
});
```

**After:**
```typescript
} catch (err: any) {
  const detail = err.response?.data?.detail;
  if (detail && typeof detail === 'object' && detail.niem_ndr_report) {
    // ✅ Store full NDR report for ValidationResults component to display
    setLastValidationResult({
      niem_ndr_report: detail.niem_ndr_report
    });
    setError(detail.message || 'Schema validation failed');
  }
}
```

## Result

**Before:**
```
❌ Schema upload rejected due to NIEM NDR validation failures.
   Found 7 NIEM NDR violations across 1 files:
   Rule 7-38: ...; Rule 7-38: ...; Rule 7-38: ... and 4 more
```

**After:**
```
✅ Schema upload rejected: Found 7 NIEM NDR violations across 1 file(s).
   See details below.

   [Expandable ValidationResults component shows:]

   📋 NIEM NDR Violations by File (7)

   ├─ PrivacyMetadata.xsd (7 errors, 0 warnings)
      │
      ├─ ❌ Rule 7-38
      │  A type definition, element declaration, or attribute
      │  declaration MUST be a documented component
      │  Location: line 15, column 5
      │
      ├─ ❌ Rule 7-38
      │  A type definition, element declaration, or attribute
      │  declaration MUST be a documented component
      │  Location: line 22, column 5
      │
      ├─ ❌ Rule 7-38
      │  [... all 7 violations shown with full details]
```

## Features

✅ **All violations shown** - No truncation, all errors visible
✅ **Grouped by file** - Easy to see which file has which errors
✅ **Expandable interface** - File-by-file accordion for readability
✅ **Full error details** - Rule number, message, and location for each
✅ **Error/warning separation** - Visual distinction and counts
✅ **Backward compatible** - Handles both old string errors and new detailed errors

## UI Display Structure

The ValidationResults component shows:
1. **Summary** - Total violations across all files
2. **File grouping** - Expandable sections per file
3. **Violation details** - Each violation with:
   - Icon (error/warning indicator)
   - Rule number
   - Full message
   - Location in file

## Testing

To test the full error display:

1. Upload a schema with NDR violations:
   ```bash
   # Upload PrivacyMetadata.xsd which has multiple violations
   curl -X POST http://localhost:8000/api/schema/xsd \
     -H "Authorization: Bearer devtoken" \
     -F "files=@samples/PrivacyMetadata.xsd"
   ```

2. In UI, upload the same file
3. Click on "NIEM NDR Violations by File" to expand
4. Click on the filename to see all violations
5. Verify all 7 violations are shown (not truncated to 3)

## API Response Format

```json
{
  "detail": {
    "message": "Schema upload rejected due to NIEM NDR validation failures. Found 7 NIEM NDR violations across 1 files.",
    "niem_ndr_report": {
      "status": "fail",
      "message": "Validated 1 files, found 7 errors",
      "conformance_target": "all",
      "violations": [
        {
          "type": "error",
          "rule": "Rule 7-38",
          "message": "A type definition, element declaration, or attribute declaration MUST be a documented component",
          "location": "PrivacyMetadata.xsd:15:5",
          "file": "PrivacyMetadata.xsd"
        }
        // ... all 7 violations included
      ],
      "summary": {
        "error_count": 7,
        "warning_count": 0
      }
    }
  }
}
```

## Benefits

1. **Complete error visibility** - Users see every violation, not summaries
2. **File-based organization** - Easy to identify which file needs fixes
3. **Actionable information** - Line numbers and locations for quick fixes
4. **Professional UX** - Clean, organized display with expand/collapse
5. **No information loss** - Full error context preserved from validator
