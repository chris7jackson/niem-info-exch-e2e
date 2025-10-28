# Known Issues

## JSON Schema Conversion Failure with CMF Tool

### Issue Description

The CMF Tool (version 1.0) has a bug that causes JSON Schema conversion to fail for certain NIEM schemas, particularly NIEM 3.0 schemas like the NEICE IEPD Package.

### Error Details

```
java.lang.IndexOutOfBoundsException: Index 0 out of bounds for length 0
at org.mitre.niem.json.OfDefinition.setRequired(OfDefinition.java:87)
at org.mitre.niem.json.JSONSchema.processHasProperties(JSONSchema.java:253)
```

**Root Cause**: The CMF tool's JSON Schema generator attempts to access an empty ArrayList when processing properties that should be marked as "required". This is a bug in the CMF tool's Java code.

**Affected Schemas**: NIEM 3.0 schemas, including:
- NEICE IEPD Package V04
- Other schemas that define certain property cardinality patterns

### Impact

- **Schema Upload**: ✅ Succeeds - XSD files are stored and CMF is generated
- **XML Ingestion**: ✅ Works - You can ingest XML files using the schema
- **JSON Schema Generation**: ❌ Fails - JSON schema file is not created
- **JSON Ingestion**: ❌ Blocked - Cannot validate/ingest JSON files without the schema

### Workarounds

#### Option 1: Use XML Ingestion (Recommended)
The system is designed to handle both XML and JSON. If JSON schema generation fails, use XML ingestion instead:

```bash
# Upload your schema (will show warning if JSON fails)
POST /api/schema/xsd

# Ingest XML data files
POST /api/ingest/xml
```

#### Option 2: Report to Upstream
This bug should be reported to the NIEMOpen CMFTool project:
- Repository: https://github.com/niemopen/cmftool
- Issues: https://github.com/niemopen/cmftool/issues

Include:
- Error stack trace (from API logs)
- Schema files that reproduce the issue
- CMF Tool version: 1.0

#### Option 3: Manual JSON Schema Creation
If you need JSON ingestion, you can:
1. Manually create a JSON Schema from your XSD
2. Upload it to MinIO at: `niem-schemas/{schema_id}/{base_name}.json`
3. Update metadata.json to include `json_schema_filename`

### Detection

The system now automatically detects this failure and:
- Logs detailed error information
- Returns a warning in the schema upload response
- Prevents JSON ingestion attempts with a clear error message

Check the API response for:
```json
{
  "schema_id": "...",
  "is_active": true,
  "warnings": [
    "JSON schema conversion failed - JSON file ingestion will not be available. XML ingestion is still supported. Error: Failed to convert CMF to JSON Schema"
  ]
}
```

### Future Resolution

Potential fixes:
1. **Upgrade CMF Tool**: When a newer version with the bug fix is released
2. **Patch CMF Tool**: Decompile and patch the JAR file
3. **Alternative Tool**: Use a different XSD-to-JSON Schema converter
4. **Contribute Fix**: Fix the bug in CMFTool source and contribute upstream

### Related Files

- `api/src/niem_api/services/cmf_tool.py`: CMF tool wrapper with error logging
- `api/src/niem_api/handlers/schema.py`: Schema upload handler with failure handling
- `api/src/niem_api/handlers/ingest.py`: JSON ingestion with schema validation check

### References

- CMFTool Repository: https://github.com/niemopen/cmftool
- NIEM Common Model Format: https://github.com/niemopen/common-model-format
- NIEM JSON Specification: https://niem.github.io/NIEM-JSON-Spec/

---

**Last Updated**: 2025-10-27
**Affects**: CMFTool v1.0
**Status**: Upstream bug, workarounds available
