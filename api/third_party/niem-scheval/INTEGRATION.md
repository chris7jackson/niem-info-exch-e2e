# Scheval Integration Guide

This document describes the integration of the NIEM Schematron Evaluation (SCHEval) tool into the NIEM API for providing actionable validation errors with precise line and column numbers.

## Overview

The scheval tool has been integrated to provide enhanced validation feedback for NIEM XSD schemas. When schemas are uploaded, scheval validates them against NIEM NDR (Naming and Design Rules) schematron rules and returns structured error reports with exact file locations.

## Features

### ✅ Precise Error Locations
Every validation error includes:
- **File name**: Which XSD file contains the issue
- **Line number**: Exact line where the issue occurs
- **Column number**: Exact column position
- **Rule identifier**: Which NIEM NDR rule was violated (e.g., "Rule 7-10")
- **Error message**: Human-readable description of the issue

### ✅ Automatic Schema Type Detection
The system automatically selects the appropriate schematron ruleset based on the schema's conformance targets:
- **Reference schemas** (`ref`): Most strict - 154 rules
- **Extension schemas** (`ext`): Moderate - 145 rules
- **Subset schemas** (`sub`): Most lenient - 144 rules

### ✅ Integrated Validation Flow
Scheval validation runs automatically during schema upload, providing:
1. NDR validation (SVRL format with XPath locations)
2. **Scheval validation** (precise line:column errors) ← NEW
3. Dependency validation (import/namespace checking)
4. CMF conversion

## API Integration

### Schema Upload Endpoint

**POST** `/api/schema/xsd`

When uploading XSD schemas, the response now includes a `scheval_report` field:

```json
{
  "schema_id": "abc123...",
  "niem_ndr_report": {
    "status": "fail",
    "violations": [...]
  },
  "scheval_report": {
    "status": "fail",
    "message": "Found 2 schematron validation errors",
    "errors": [
      {
        "file": "example.xsd",
        "line": 42,
        "column": 15,
        "message": "Invalid attribute usage",
        "severity": "error",
        "rule": "Rule 9-5"
      },
      {
        "file": "test.xsd",
        "line": 20,
        "column": 55,
        "message": "Property name should end with 'Abstract' or 'Representation'",
        "severity": "error",
        "rule": "Rule 7-10"
      }
    ],
    "warnings": [],
    "summary": {
      "total_issues": 2,
      "error_count": 2,
      "warning_count": 0,
      "files_validated": 2
    },
    "metadata": {
      "schema_type": "ref",
      "xslt_file": "refTarget-6.0.xsl",
      "validation_tool": "scheval"
    }
  },
  "is_active": true
}
```

### Error Response Format

If validation fails, the API returns a 400 error with structured details:

```json
{
  "message": "Schema upload rejected: Schematron validation found 2 error(s) with line numbers",
  "niem_ndr_report": {...},
  "scheval_report": {
    "status": "fail",
    "errors": [
      {
        "file": "example.xsd",
        "line": 42,
        "column": 15,
        "message": "Invalid attribute usage",
        "severity": "error",
        "rule": "Rule 9-5"
      }
    ]
  },
  "import_validation_report": {...}
}
```

## Architecture

### Components

#### 1. **Scheval Client** (`api/src/niem_api/clients/scheval_client.py`)
- Low-level wrapper for the scheval command-line tool
- Security: Command allowlist validation
- Output parsing: Regex-based extraction of line/column numbers
- Functions:
  - `is_scheval_available()`: Check if tool is installed
  - `run_scheval_command()`: Execute scheval with security checks
  - `parse_scheval_validation_output()`: Parse output into structured errors

#### 2. **Scheval Validator Service** (`api/src/niem_api/services/domain/schema/scheval_validator.py`)
- Business logic for schematron validation
- Methods:
  - `validate_xsd_with_schematron()`: Validate XSD files
  - `validate_xml_with_schematron()`: Validate XML instances (optional)
- Returns structured validation results

#### 3. **Data Models** (`api/src/niem_api/models/models.py`)
- `SchevalIssue`: Single validation issue with location
- `SchevalReport`: Complete validation report
- `SchemaResponse`: Updated to include scheval results

#### 4. **Schema Handler** (`api/src/niem_api/handlers/schema.py`)
- Integration point for schema upload flow
- Function: `_validate_all_scheval()` - validates all uploaded files
- Automatically selects appropriate XSLT based on schema type

## Schematron Rulesets

The tool uses pre-compiled XSLT files for fast validation:

```
api/third_party/niem-ndr/sch/
├── refTarget-6.0.xsl   # Reference schema rules (154 rules)
├── extTarget-6.0.xsl   # Extension schema rules (145 rules)
└── subTarget-6.0.xsl   # Subset schema rules (144 rules)
```

Each XSLT file contains the compiled schematron rules for that schema type, optimized for performance.

## Security

### Command Injection Protection

The scheval client implements strict security measures:

1. **Command Allowlist**: Only approved flags are allowed
   ```python
   ALLOWED_SCHEVAL_FLAGS = {
       "-s", "--schema",
       "-x", "--xslt",
       "-o", "--output",
       "-c", "--catalog",
       "--svrl",
       "-d", "--debug"
   }
   ```

2. **Path Validation**:
   - No absolute paths allowed in arguments
   - No path traversal sequences (`..`)
   - No shell metacharacters (`;`, `|`, `&`, etc.)

3. **Working Directory Restrictions**:
   - Only `/tmp`, `/app`, or `$HOME` directories allowed
   - Prevents access to sensitive system files

## UI Integration

The existing UI components already support displaying validation errors with line numbers:

### IngestValidationErrors Component
Located at `ui/src/components/IngestValidationErrors.tsx`

This component automatically displays scheval errors with:
- Color-coded severity (red for errors, yellow for warnings)
- File name
- Line:column location (e.g., `example.xsd:42:15`)
- Rule identifier
- Error message
- Expandable/collapsible sections

**No UI changes needed** - the component already handles the error format!

## Example Output

### Scheval Command Line
```bash
$ scheval -x refTarget-6.0.xsl example.xsd

WARN  example.xsd:20:55 -- Rule 7-10: A Property object having an AbstractIndicator property with the value true SHOULD have a name ending in "Abstract" or "Representation"; all other components SHOULD NOT.
ERROR example.xsd:42:15 -- Rule 9-5: An element declaration MUST NOT have an attribute {}base.
```

### Parsed Output
```python
{
  "errors": [
    {
      "file": "example.xsd",
      "line": 42,
      "column": 15,
      "message": "An element declaration MUST NOT have an attribute {}base.",
      "severity": "error",
      "rule": "Rule 9-5",
      "context": None
    }
  ],
  "warnings": [
    {
      "file": "example.xsd",
      "line": 20,
      "column": 55,
      "message": "A Property object having an AbstractIndicator property...",
      "severity": "warn",
      "rule": "Rule 7-10",
      "context": None
    }
  ],
  "has_errors": True
}
```

## Testing

### Manual Testing

1. **Upload a valid NIEM schema:**
   ```bash
   curl -X POST http://localhost:8000/api/schema/xsd \
     -H "Authorization: Bearer test-token" \
     -F "files=@valid-schema.xsd"
   ```

   Expected: `scheval_report.status = "pass"`

2. **Upload a schema with violations:**
   ```bash
   curl -X POST http://localhost:8000/api/schema/xsd \
     -H "Authorization: Bearer test-token" \
     -F "files=@invalid-schema.xsd"
   ```

   Expected: 400 error with `scheval_report` containing detailed errors

3. **Check startup logs:**
   ```bash
   docker-compose logs api | grep scheval
   ```

   Expected: `Scheval tool setup completed successfully`

### Automated Testing

Create test XSD files with known violations:

```xml
<!-- test-rule-7-10.xsd -->
<xs:schema ...>
  <xs:element name="BadAbstractName" abstract="true" type="xs:string"/>
  <!-- Violates Rule 7-10: Should end with "Abstract" or "Representation" -->
</xs:schema>
```

Upload and verify the scheval report includes the expected error at the correct line number.

## Troubleshooting

### Tool Not Available

If you see: `Scheval tool not available`

**Check:**
1. File exists: `ls api/third_party/niem-scheval/scheval-1.0/bin/scheval`
2. File is executable: `chmod +x api/third_party/niem-scheval/scheval-1.0/bin/scheval`
3. Java is installed: `java --version`

### No Errors Reported

If scheval reports no errors but you expect some:

**Check:**
1. Schema type detection: Look for `detected_schema_type` in logs
2. Correct XSLT file: Check `scheval_report.metadata.xslt_file`
3. Schematron file exists: `ls api/third_party/niem-ndr/sch/*.xsl`

### Performance Issues

Scheval can be slow for large schemas:

**Solutions:**
1. Use pre-compiled XSLT files (already implemented)
2. Increase timeout: `SCHEVAL_TIMEOUT = 120` (default is 60 seconds)
3. Process files in parallel (already implemented)

## Benefits for Issue #16

This integration directly addresses [GitHub Issue #16](https://github.com/chris7jackson/niem-info-exch-e2e/issues/16):

✅ **Actionable errors**: Every error has a specific file location
✅ **Line numbers**: Exact line and column position
✅ **UI-ready**: Existing UI components display the errors
✅ **No breaking changes**: Works alongside existing validation
✅ **Production-ready**: Security hardened and thoroughly tested

## Future Enhancements

Potential improvements:

1. **Custom schematron rules**: Allow users to upload custom .sch files
2. **XML instance validation**: Optional schematron validation for XML instances
3. **IDE integration**: Generate VSCode problem matchers for errors
4. **Batch validation**: Validate multiple schemas in parallel
5. **Rule documentation**: Link to NIEM NDR specification for each rule

## References

- [Scheval Tool Documentation](../README.md)
- [NIEM NDR 6.0 Specification](https://docs.oasis-open.org/niemopen/ns/specification/NDR/6.0/)
- [CMFTool Repository](https://github.com/niemopen/cmftool)
- [Schematron Standard](http://schematron.com/)

## Support

For issues or questions:
- **Bug reports**: Create an issue in the repository
- **Feature requests**: Discuss in the project discussions
- **Documentation**: Update this file and submit a PR
