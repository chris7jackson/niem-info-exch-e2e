---
name: Add XML-to-JSON instance data transformation using CMF tool
about: Convert XML instance documents to JSON using NIEM CMF transformation
title: 'Add XML-to-JSON instance data transformation using CMF tool'
labels: enhancement, cmf-tool, transformation
assignees: ''
---

## Problem Statement

Users may have NIEM XML instance documents and want to:
1. Convert them to JSON format for easier consumption
2. Validate both XML and JSON versions against the same schema
3. Use JSON for modern APIs while maintaining XML compatibility

Currently, the system only validates XML or JSON separately. There's no built-in transformation between formats.

## User Value

- **Format flexibility**: Accept XML, work with JSON (or vice versa)
- **Modernization**: Enable JSON APIs without rewriting XML-based systems
- **Validation consistency**: Ensure XML and JSON represent the same data
- **Developer experience**: JSON is easier to work with in web applications

## Proposed Solution

Use NIEM CMF tool's transformation capabilities (if available) to convert instance documents between XML and JSON formats, preserving NIEM semantics.

## Acceptance Criteria

- [ ] Research CMF tool transformation commands (beyond x2m, m2jmsg)
- [ ] Implement XML instance → JSON transformation service
- [ ] Implement JSON instance → XML transformation service (if needed)
- [ ] Add API endpoints for transformation:
  - `POST /api/transform/xml-to-json`
  - `POST /api/transform/json-to-xml` (optional)
- [ ] Preserve all data during transformation (lossless)
- [ ] Maintain NIEM semantics (ids, refs, augmentations)
- [ ] Add UI button "Convert to JSON" on XML upload
- [ ] Show transformation results with download option
- [ ] Handle transformation errors gracefully
- [ ] Tests verify transformation accuracy

## Technical Context

**CMF Tool Research Needed:**
- Check if CMF tool has instance document transformation commands
- Current known commands: `x2m` (schema), `m2jmsg` (schema), `xval` (validation)
- May need to explore CMF tool documentation or source code

**Files to create/modify:**
- `api/src/niem_api/services/cmf_tool.py` - Add transformation functions
- `api/src/niem_api/clients/cmf_client.py` - Add command to allowlist
- `api/src/niem_api/handlers/transform.py` - New handler for transformation
- `api/src/niem_api/main.py` - Add transformation endpoints
- `ui/src/components/TransformButton.tsx` - UI for transformation

**Alternative Approach (if CMF doesn't support it):**
- Use Python libraries (xmltodict + custom logic)
- Implement custom transformer following NIEM JSON-LD spec
- Reference: https://github.com/NIEM/NIEM-JSON-Spec

**Proposed API:**
```python
def transform_xml_to_json(
    xml_content: str,
    schema_id: str,
    preserve_structure: bool = True
) -> Dict[str, Any]:
    """
    Transform NIEM XML instance to JSON-LD format

    Args:
        xml_content: XML instance document
        schema_id: Schema to use for transformation
        preserve_structure: Keep NIEM structure vs flatten

    Returns:
        JSON-LD object following NIEM conventions
    """
```

## Implementation Notes

1. **CMF Tool Investigation (Phase 1):**
   - Run `cmftool help` to see all available commands
   - Check CMF tool repository for transformation features
   - Document findings in issue comments

2. **Transformation Strategy (Phase 2a - If CMF supports it):**
   - Add transformation command to CMF client
   - Create service layer wrapper
   - Handle @context generation for JSON-LD
   - Preserve structures:id and structures:ref

3. **Custom Implementation (Phase 2b - If CMF doesn't support it):**
   - Parse XML to dict using ElementTree
   - Generate JSON-LD following NIEM spec
   - Map structures namespace to JSON-LD conventions
   - Handle augmentations, metadata, references

4. **API Integration (Phase 3):**
   - Create transformation endpoints
   - Add to existing upload flow (optional transformation)
   - Store both formats in MinIO
   - Link in metadata

5. **UI Integration (Phase 4):**
   - Add "Convert to JSON" button on XML upload success
   - Show side-by-side comparison
   - Enable download of converted format

## Test Cases

```xml
<!-- Input: CrashDriver XML -->
<j:Crash>
  <j:CrashDriver structures:id="P01">
    <nc:PersonName>
      <nc:PersonGivenName>Peter</nc:PersonGivenName>
    </nc:PersonName>
  </j:CrashDriver>
</j:Crash>
```

```json
// Expected Output: NIEM JSON-LD
{
  "@context": { ... },
  "j:Crash": {
    "j:CrashDriver": {
      "@id": "#P01",
      "nc:PersonName": {
        "nc:PersonGivenName": "Peter"
      }
    }
  }
}
```

## Related Issues

- Related to: Existing XML/JSON ingestion logic
- May impact: #7 (data import wizard)
- Enhances: User workflow for data upload

## Priority

**Low-Medium** - Nice to have, not blocking core functionality

## Estimated Effort

**Medium to Large (M-L)** - ~8-16 hours
- Depends heavily on CMF tool capabilities
- If custom implementation needed: Extra Large (16-24 hours)
- Research phase: 2-4 hours
- Implementation: 6-12 hours
- Testing: 4-6 hours

## Additional Context

**NIEM JSON-LD Specification:**
- https://github.com/NIEM/NIEM-JSON-Spec
- Defines JSON-LD representation of NIEM data
- Uses @context, @id, @type conventions

**CMF Tool Repository:**
- https://github.com/niemopen/cmftool
- Check for transformation documentation
- May have experimental commands not in current version

**Use Cases:**
1. Government agency receives XML, needs JSON for web services
2. Developer testing: Upload XML, compare with JSON validation
3. Format migration: Bulk convert legacy XML to modern JSON

**Risks:**
- CMF tool may not support instance transformation
- Custom implementation requires deep NIEM spec knowledge
- Transformation may not be fully lossless for complex cases
