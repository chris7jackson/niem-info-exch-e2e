---
name: Display exact line numbers and source snippets for NDR violations
about: Show NDR validation errors with line numbers and code context in UI
title: 'Display exact line numbers and source snippets for NDR violations'
labels: enhancement, ui, validation, ndr
assignees: ''
---

## Problem Statement

Currently, NDR validation errors show generic location information (XPath expressions) but don't display:
- Exact line numbers where violations occur
- Source code snippets with context
- Visual indicators of the problematic code

This makes it difficult for developers to quickly locate and fix issues in their schemas.

## User Value

- **Faster debugging**: Jump directly to line with error
- **Better understanding**: See code context around violation
- **Professional UX**: Similar to modern IDE error displays
- **Reduced friction**: Less switching between UI and text editor

## Current Behavior

Validation results show:
```
Rule 9-52: Element name must follow naming conventions
Location: /*[local-name()='schema'][1]/*[local-name()='complexType'][2]
```

User must manually parse XPath to find the problematic element.

## Desired Behavior

Validation results show:
```
Rule 9-52: Element name must follow naming conventions
File: CrashDriver.xsd
Line 42, Column 15

  40  <xs:complexType name="DriverType">
  41    <xs:annotation>...</xs:annotation>
> 42    <xs:element name="driverAge" type="xs:int"/>
  43    <xs:element name="DriverLicense" type="j:DriverLicenseType"/>
  44  </xs:complexType>

Expected: Element names in PascalCase (e.g., "DriverAge" not "driverAge")
```

## Acceptance Criteria

- [ ] Backend already extracts line numbers (validator.py line 450-517)
- [ ] API response includes `line_number` and `source_snippet` fields
- [ ] UI ValidationResults component displays line numbers prominently
- [ ] UI shows source code snippet with syntax highlighting
- [ ] Error line highlighted or marked with indicator (e.g., `> 42`)
- [ ] Snippet shows 2-3 lines of context before and after
- [ ] Collapsible/expandable snippet view for long violations lists
- [ ] Line numbers are clickable (copy to clipboard) for easy reference
- [ ] Works for both NDR validation and import validation
- [ ] Mobile-responsive snippet display

## Technical Context

**Backend (Already Implemented!):**
- `api/src/niem_api/services/domain/schema/validator.py`
- Function: `_extract_source_snippet_from_xpath()` (lines 450-517)
- Function: `_extract_violation_from_element()` (lines 519-548)
- Returns: `{"snippet": "...", "line_number": 42}`

**Backend Response Structure:**
```python
{
  "type": "error",
  "rule": "9-52",
  "message": "Element name must follow naming conventions",
  "location": "/*[local-name()='schema']...",
  "source_snippet": {  # Already available!
    "snippet": ">  42  <xs:element name=\"driverAge\"...",
    "line_number": 42
  }
}
```

**Frontend Files to Modify:**
- `ui/src/components/ValidationResults.tsx` - Main validation display
- `ui/src/components/ViolationSnippet.tsx` - New component for code display
- `ui/src/lib/api.ts` - Add `source_snippet` to TypeScript types

**UI Component Structure:**
```tsx
<ViolationItem>
  <ViolationHeader rule={violation.rule} message={violation.message} />
  <ViolationLocation file={violation.file} line={violation.line_number} />
  {violation.source_snippet && (
    <CodeSnippet
      code={violation.source_snippet.snippet}
      language="xml"
      highlightLine={violation.source_snippet.line_number}
    />
  )}
</ViolationItem>
```

## Implementation Notes

1. **Phase 1: Backend Verification (1 hour)**
   - Verify `source_snippet` is present in API responses
   - Test with various schema violations
   - Ensure snippet extraction works for different violation types

2. **Phase 2: TypeScript Types (1 hour)**
   - Add `source_snippet` to `NiemNdrViolation` interface
   - Update API client to handle new fields
   - Add type safety for snippet rendering

3. **Phase 3: UI Components (4-6 hours)**
   - Create `ViolationSnippet` component
   - Add syntax highlighting (use `prism-react-renderer` or similar)
   - Implement line number display
   - Add error line highlighting
   - Make snippets collapsible for long lists

4. **Phase 4: Styling (2-3 hours)**
   - Match existing UI theme
   - Ensure readability (monospace font, proper spacing)
   - Add copy-to-clipboard for line numbers
   - Mobile-responsive design

5. **Phase 5: Testing (2 hours)**
   - Test with various violation types
   - Test with/without snippets (graceful degradation)
   - Test collapsible behavior
   - Cross-browser testing

## Test Cases

1. **Violation with Snippet:**
   - Upload schema with NDR violation
   - Verify snippet appears in results
   - Verify line number is correct
   - Verify snippet shows context

2. **Violation without Snippet:**
   - Backend fails to extract snippet (edge case)
   - Verify UI gracefully shows XPath location instead
   - No UI errors

3. **Multiple Violations:**
   - Schema with 10+ violations
   - Verify all snippets render correctly
   - Verify performance is acceptable

4. **Long Files:**
   - Snippet near end of 1000+ line file
   - Verify line numbers display correctly

## Related Issues

- Enhances: Existing NDR validation feature
- Related to: #1, #2, #3 (graph improvements requiring schema fixes)
- Improves: Developer experience across the board

## Priority

**Low-Medium** - Quality of life improvement, not blocking

## Estimated Effort

**Small to Medium (S-M)** - ~4-8 hours
- Backend already done! ✅
- Mainly frontend UI work
- Syntax highlighting library integration
- Styling and responsiveness

## Additional Context

**Similar UX Examples:**
- ESLint error display in VS Code
- TypeScript error display in IDE
- GitHub PR code review comments

**Libraries for Syntax Highlighting:**
- `prism-react-renderer` - Lightweight, themeable
- `react-syntax-highlighter` - Feature-rich
- `highlight.js` - Popular, well-maintained

**Accessibility:**
- Ensure code snippets have proper ARIA labels
- Support keyboard navigation
- High contrast mode for readability

**Future Enhancements:**
- Click line number to open file at that location (if integrated with IDE)
- Download problematic file section
- Suggest auto-fixes for common violations
