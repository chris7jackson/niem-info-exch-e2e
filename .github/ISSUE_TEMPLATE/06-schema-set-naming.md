---
name: Add schema set naming for IEPD identification
about: Allow users to assign friendly names to schema sets
title: 'Add schema set naming for IEPD identification'
labels: enhancement, ui, ux, schema
assignees: ''
---

## Problem Statement

Currently, schema sets are identified only by:
- Auto-generated schema_id (hash)
- Primary filename (e.g., "CrashDriver.xsd")
- Upload timestamp

For users managing multiple IEPDs (Information Exchange Package Documentations) or versions, this makes it hard to:
- Distinguish between different versions of the same IEPD
- Quickly identify the purpose of a schema set
- Organize schemas by project or use case

## User Value

- **Better organization**: Name schemas by purpose ("CrashDriver v1.2", "Arrest Report Production")
- **Easier selection**: Dropdown shows "My Project Schema" instead of UUID
- **Version management**: Track schema iterations clearly
- **Team collaboration**: Shared understanding of which schema is which

## Proposed Solution

Add optional user-defined name for schema sets, stored in metadata and displayed throughout the UI.

## Acceptance Criteria

- [ ] Schema metadata includes `name` field (optional, user-defined)
- [ ] Schema metadata includes `description` field (optional, multi-line)
- [ ] Upload UI includes name/description inputs (optional fields)
- [ ] Schema list displays name prominently (falls back to primary_filename)
- [ ] Schema selection dropdowns show name instead of schema_id
- [ ] Name validation: 1-100 characters, no special chars except space/-/_
- [ ] Description validation: 0-500 characters
- [ ] API supports updating name/description after upload
- [ ] Tests verify name storage and retrieval

## Technical Context

**Backend Changes:**
- `api/src/niem_api/handlers/schema.py`
  - Function: `_store_schema_metadata()` (line ~688)
  - Add `name` and `description` to metadata dict
- `api/src/niem_api/models/models.py`
  - Add `name` and `description` to `SchemaResponse` model
- New endpoint: `PATCH /api/schema/{schema_id}/metadata`

**Current metadata structure:**
```python
schema_metadata = {
    "schema_id": schema_id,
    "primary_filename": primary_file.filename,
    "json_schema_filename": json_schema_filename,
    "cmf_filename": cmf_filename,
    "all_filenames": list(file_contents.keys()),
    "uploaded_at": timestamp,
    "known_gaps": "",
    "is_active": True
}
```

**Proposed metadata structure:**
```python
schema_metadata = {
    ...existing fields...,
    "name": name or primary_file.filename,  # User-defined or default
    "description": description or "",
    "tags": tags or [],  # Future: categorization
    "version": version or "1.0"  # Future: version tracking
}
```

**Frontend Changes:**
- `ui/src/components/SchemaManager.tsx`
  - Add name/description inputs to upload form
  - Display name in schema list (line ~505)
  - Add edit metadata button/modal
- `ui/src/components/SchemaMetadataEditor.tsx` - New component
- `ui/src/lib/api.ts`
  - Add `updateSchemaMetadata()` method
  - Add `name` and `description` to Schema interface

## Implementation Notes

1. **Upload Flow Enhancement:**
   ```tsx
   <SchemaUploadForm>
     <FileSelector />
     <TextField
       label="Schema Name (optional)"
       placeholder="e.g., CrashDriver Production v1.2"
       maxLength={100}
     />
     <TextArea
       label="Description (optional)"
       placeholder="Describe the purpose and version..."
       maxLength={500}
     />
     <UploadButton />
   </SchemaUploadForm>
   ```

2. **Display Priority:**
   - Show: `name` if provided
   - Fallback: `primary_filename`
   - Secondary: Upload date, schema_id prefix

3. **Edit Metadata Modal:**
   ```tsx
   <Modal title="Edit Schema Metadata">
     <TextField label="Name" value={schema.name} />
     <TextArea label="Description" value={schema.description} />
     <ButtonGroup>
       <Button onClick={handleSave}>Save</Button>
       <Button onClick={handleCancel}>Cancel</Button>
     </ButtonGroup>
   </Modal>
   ```

4. **Validation Rules:**
   - Name: Optional, 1-100 chars, alphanumeric + space/-/_ only
   - Description: Optional, 0-500 chars, any printable chars
   - No duplicate names (warn but allow)

5. **API Endpoints:**
   ```python
   # During upload
   POST /api/schema/xsd?name=...&description=...

   # Update existing
   PATCH /api/schema/{schema_id}/metadata
   Body: {"name": "...", "description": "..."}
   ```

## UI Mockup

**Schema List Display:**
```
┌─────────────────────────────────────────────────────────────┐
│ Uploaded Schemas                                             │
├─────────────────────────────────────────────────────────────┤
│ CrashDriver Production v1.2           [Active] [Edit]       │
│ Crash analysis for traffic incidents                         │
│ Schema ID: c597afe... | Uploaded: Oct 14, 2025              │
│ Files: CrashDriver.xsd (+5 files)                           │
│ Generated: CrashDriver.cmf | CrashDriver.json               │
├─────────────────────────────────────────────────────────────┤
│ Arrest Report Schema                  [Activate] [Edit]     │
│ Justice domain arrest reporting                              │
│ Schema ID: 9af41a3... | Uploaded: Oct 10, 2025              │
└─────────────────────────────────────────────────────────────┘
```

## Related Issues

- Related to: All schema management features
- Enhances: #7 (data import wizard) - schema selection
- Future: Schema versioning (#future)

## Priority

**Low** - Quality of life improvement, not blocking

## Estimated Effort

**Small (S)** - ~2-4 hours
- Backend: Add fields to metadata (30 min)
- Backend: Add update endpoint (1 hour)
- Frontend: Add inputs to form (1 hour)
- Frontend: Add edit modal (1-2 hours)
- Testing: (30 min)

## Additional Context

**Similar Features in Other Tools:**
- Postman: Collection names and descriptions
- GitHub: Repository names and descriptions
- AWS S3: Bucket tags and metadata

**Future Enhancements:**
- **Tags**: Categorize schemas (e.g., "Justice", "Health", "Production")
- **Version tracking**: Automatic versioning (v1, v2, etc.)
- **Search**: Filter schemas by name/description
- **Favorites**: Pin frequently used schemas
- **Sharing**: Export schema metadata as JSON

**Storage Considerations:**
- Name/description stored in MinIO metadata.json
- No separate database table needed
- Retrieved with schema list
- Cached in UI state

**Accessibility:**
- Input labels properly associated
- Placeholder text provides examples
- Character count indicator for limits
- Keyboard navigation support
