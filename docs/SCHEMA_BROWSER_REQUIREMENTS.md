# Schema Browser - Functional Requirements

## 1. Overview

The Schema Browser is an interactive graph-based visualization tool for exploring NIEM CMF schemas. It replaces the previous XSD tree-based browser with a more powerful graph visualization that shows relationships, associations, and augmentations.

## 2. User Stories

| ID | User Story | Priority |
|----|------------|----------|
| US-1 | As a schema developer, I want to see the hierarchical structure of a schema so I can understand its organization | High |
| US-2 | As an IEPD developer, I want to find relationships between types so I can build correct exchanges | High |
| US-3 | As a schema architect, I want to identify central/heavily-used types for optimization | Medium |
| US-4 | As a developer, I want to export schema diagrams for documentation | Medium |
| US-5 | As a newcomer, I want to navigate intuitively without training | High |

## 3. Functional Requirements

### FR-1: Schema Selection

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-1.1 | User can select from dropdown of all uploaded schemas | Dropdown shows all schemas with primary filename and upload date |
| FR-1.2 | Active schema is pre-selected by default | On page load, active schema is auto-selected |
| FR-1.3 | Schema metadata displayed | Shows schema ID, file count, upload date after selection |

### FR-2: Graph Visualization Modes

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-2.1 | Tree Graph mode available | Tab labeled "Tree Graph" displays hierarchical layout |
| FR-2.2 | Network Graph mode available | Tab labeled "Network Graph" displays force-directed layout |
| FR-2.3 | User can switch modes | Clicking tab switches view without data reload |
| FR-2.4 | Layout persists when switching filters | Applied filters remain when switching between tabs |

### FR-3: Tree Graph Expand/Collapse

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-3.1 | Initially display root-level nodes | On load, only namespace or top-level classes shown |
| FR-3.2 | Double-click expands node | Double-clicking node shows immediate children |
| FR-3.3 | Double-click collapses node | Double-clicking expanded node hides children |
| FR-3.4 | Visual indicator for collapsed nodes | [+] shown on nodes with hidden children |
| FR-3.5 | Visual indicator for expanded nodes | [-] shown on nodes with visible children |
| FR-3.6 | Smooth animation | Expand/collapse animates over 500ms |
| FR-3.7 | "Expand All" button | Expands all nodes to depth 3 |
| FR-3.8 | "Collapse All" button | Collapses all nodes to root level |
| FR-3.9 | Depth slider control | Slider shows nodes up to N levels deep (1-10) |
| FR-3.10 | Right-click context menu | Menu shows expand/collapse options |

### FR-4: Node Display

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-4.1 | Nodes colored by namespace | Colors assigned dynamically based on category in data (e.g., distinct colors for CORE, DOMAIN, EXTENSION categories) |
| FR-4.2 | Nodes shaped by type | Shapes assigned dynamically based on nodeType in data (e.g., rectangles for classes, diamonds for associations) |
| FR-4.3 | Node size by connection count | Size ranges from 40px (few connections) to 120px (many) |
| FR-4.4 | Node label shows short name | Shows "PersonType" not "nc:PersonType" |
| FR-4.5 | Tooltip on hover | Hover shows full qualified name and documentation preview |

### FR-5: Edge Display

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-5.1 | Edges styled by type | Styles assigned dynamically based on edgeType in data (e.g., solid for property, dashed for association) |
| FR-5.2 | Edge labels show relationship | Label displays property or relationship name |
| FR-5.3 | Edge color matches target | Edge color follows target node's namespace color |
| FR-5.4 | Click edge shows details | Clicking edge highlights and shows detail panel |

### FR-6: Navigation & Interaction

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-6.1 | Click node selects | Single click selects node and shows detail panel |
| FR-6.2 | Ctrl+Click multi-selects | Holding Ctrl allows selecting multiple nodes |
| FR-6.3 | Drag canvas to pan | Mouse drag moves viewport |
| FR-6.4 | Scroll to zoom | Mouse wheel zooms 10%-500% |
| FR-6.5 | "Fit to Screen" button | Auto-zooms to show all visible nodes |
| FR-6.6 | "Reset View" button | Returns zoom and pan to initial state |
| FR-6.7 | Minimap shows viewport | Corner minimap shows current view position |

### FR-7: Search & Filter

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-7.1 | Search bar filters nodes | Search term highlights matching nodes |
| FR-7.2 | Search highlights in yellow | Matching nodes turn yellow |
| FR-7.3 | Search shows result count | Displays "Found X nodes matching 'term'" |
| FR-7.4 | Namespace filter checkboxes | Multi-select checkboxes for each namespace |
| FR-7.5 | Type filter checkboxes | Multi-select for Classes, Associations, Properties |
| FR-7.6 | "Clear Filters" button | Resets all filters to defaults |
| FR-7.7 | Filters apply instantly | No page reload needed |
| FR-7.8 | URL params reflect state | Filter state saved in URL (bookmarkable) |

### FR-8: Detail Panel

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-8.1 | Shows on node click | Right sidebar appears on selection |
| FR-8.2 | Displays full information | Shows all fields listed in FR-8.2 spec |
| FR-8.3 | Links are clickable | Clicking property navigates to that type |
| FR-8.4 | Mode toggle buttons | "View in Tree Mode" / "View in Network Mode" buttons work |
| FR-8.5 | Close button functional | X button hides panel |

**FR-8.2 Detail Panel Content**:
- Full qualified name (e.g., "nc:PersonType")
- Namespace (name, URI, category)
- Node type (ObjectType, AssociationType, etc.)
- Full documentation text
- Properties list (name, type, cardinality)
- "Used In" count and list
- Augmented by (if applicable)
- Extends (base type, if applicable)
- Source file location

### FR-9: Path Finding

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-9.1 | Select two nodes | Ctrl+Click two nodes to select |
| FR-9.2 | "Find Path" button appears | Button visible when exactly 2 nodes selected |
| FR-9.3 | Calculates shortest path | Uses Dijkstra or BFS algorithm |
| FR-9.4 | Highlights path | Path edges and nodes highlighted in green |
| FR-9.5 | Shows path description | Displays "N-hop path via property → association → ..." |
| FR-9.6 | "Clear Path" button | Removes path highlighting |

### FR-10: Export & Share

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-10.1 | Export as PNG | Downloads 1920x1080 image |
| FR-10.2 | Export as SVG | Downloads scalable vector graphic |
| FR-10.3 | Copy shareable link | Copies URL with filter state to clipboard |
| FR-10.4 | Export visible subgraph | Downloads filtered graph as JSON |

### FR-11: Performance

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-11.1 | Initial load time | < 2 seconds for 500-node schemas |
| FR-11.2 | Expand/collapse speed | Animation completes in 500ms |
| FR-11.3 | Search responsiveness | Results update within 100ms |
| FR-11.4 | Large schema support | Handles 5000 nodes without lag |
| FR-11.5 | Virtual rendering | Renders only visible viewport for 1000+ nodes |

### FR-12: Accessibility

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-12.1 | Keyboard navigation | Tab, Arrow keys, Enter, Escape functional |
| FR-12.2 | Screen reader support | Node selection announced |
| FR-12.3 | High contrast mode | Available via button |
| FR-12.4 | Focus indicators | Visible on all interactive elements |

## 4. Non-Functional Requirements

### NFR-1: Browser Compatibility
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

### NFR-2: Responsive Design
- Minimum screen width: 1024px
- Detail panel collapses on screens < 1280px
- Warnings shown on mobile devices

### NFR-3: Error Handling
- Graceful degradation if CMF parse fails
- User-friendly error messages
- Fallback to schema list if graph unavailable

### NFR-4: Data Integrity
- Graph reflects current CMF in MinIO
- No stale cached data
- Refresh button to reload from server

## 5. UI Layout Specification

```
┌──────────────────────────────────────────────────────────────────┐
│  Schema Browser                                  [Help] [Close]  │
├──────────────────────────────────────────────────────────────────┤
│  Schema: [CrashDriver IEPD (Active) ▼]       Updated: Jan 7     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [Tree Graph ●] [Network Graph ○]                               │
│                                                                  │
├───────────┬──────────────────────────────────┬──────────────────┤
│  FILTERS  │      GRAPH CANVAS                │  DETAIL PANEL    │
│  (200px)  │      (flexible width)            │  (300px)         │
│           │                                  │                  │
│  Search   │  ┌────────────────────────────┐ │  PersonType      │
│  [_____]  │  │                            │ │  ──────────────  │
│           │  │                            │ │  ObjectType      │
│  NS:      │  │   Interactive Graph View   │ │  NIEM Core       │
│  ☑ Core   │  │                            │ │                  │
│  ☑ Justice│  │   [Nodes and Edges]        │ │  "A data type    │
│  ☑ Ext    │  │                            │ │  for a human..."│
│           │  │                            │ │                  │
│  Types:   │  └────────────────────────────┘ │  Properties (12):│
│  ☑ Class  │                                  │  • PersonName    │
│  ☑ Assoc  │  [Fit] [Reset] [Expand All]     │  • PersonBirth   │
│           │  [Collapse All] [Export PNG]     │  • PersonSSN     │
│  Depth:   │                                  │  ...             │
│  [==|--]  │  Layout: [Tree●] [Force○]       │                  │
│           │  Zoom: 100%                      │  Used in (23)    │
│  [Clear]  │                                  │  [View Detail]   │
└───────────┴──────────────────────────────────┴──────────────────┘
```

## 6. Acceptance Criteria

| AC | Criterion | Test Method |
|----|-----------|-------------|
| AC-1 | Load schema within 2s | Performance test |
| AC-2 | Expand node on double-click | Manual test |
| AC-3 | Search highlights nodes | Manual test |
| AC-4 | Filter hides nodes | Manual test |
| AC-5 | Detail panel shows info | Manual test |
| AC-6 | Mode switching works | Manual test |
| AC-7 | Export PNG succeeds | Manual test |
| AC-8 | Collapse all works | Manual test |
| AC-9 | Depth slider functional | Manual test |
| AC-10 | Path finding works | Manual test |

## 7. Out of Scope

The following features are explicitly NOT included in this version:

- Editing schemas via UI
- Schema comparison/diff view
- Automatic schema generation
- Real-time collaboration
- Schema validation
- Mobile/tablet support
- Offline mode
- Multi-language support

## 8. Dependencies

### Backend
- CMF Parser module
- MinIO for CMF storage
- FastAPI for API endpoint

### Frontend
- Cytoscape.js (graph visualization)
- cytoscape-dagre (tree layout)
- cytoscape-cose-bilkent (force layout)
- React 18+
- TypeScript 5+

## 9. Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| CMF parse failure | High | Low | Comprehensive error handling, fallback to list view |
| Large schema performance | Medium | Medium | Virtual rendering, lazy loading, depth limits |
| Browser incompatibility | Low | Low | Test on all target browsers, polyfills where needed |
| User confusion | Medium | Medium | Inline help, tooltips, user guide documentation |

## 10. Success Metrics

- **User Adoption**: 80%+ of users switch from old tree view to new graph view
- **Performance**: 95% of schemas load in < 2s
- **Usability**: 90%+ of users can find relationships without help
- **Exports**: 50%+ of sessions include at least one export
- **Errors**: < 1% of sessions encounter errors

## 11. Design Principles

### 11.1 Data-Driven, NIEM-Agnostic Frontend

**Principle**: The frontend must not hardcode NIEM-specific values. All visualization decisions should be based on data received from the API.

**Rationale**:
- NIEM evolves over time (new categories, new relationship types)
- Users may define custom categories in their CMF
- System should work with any CMF-compliant schema, not just NIEM

**Implementation Guidelines**:

1. **No Hardcoded Enums**
   - Don't use `enum` types for `namespaceCategory`, `nodeType`, or `edgeType`
   - Use `string` types and handle values dynamically
   - Provide reasonable defaults for unknown values

2. **Dynamic Color Assignment**
   ```typescript
   // ❌ BAD: Hardcoded
   const colors = {
     'CORE': '#3182ce',
     'DOMAIN': '#38a169',
     'EXTENSION': '#dd6b20'
   };

   // ✅ GOOD: Dynamic with fallback
   const getCategoryColor = (category: string) => {
     const colorMap = buildColorMapFromData(graphData.namespaces);
     return colorMap[category] || '#718096'; // Gray fallback
   };
   ```

3. **Dynamic Shape Assignment**
   ```typescript
   // ❌ BAD: Hardcoded switch
   switch (nodeType) {
     case 'class': return 'roundrectangle';
     case 'association': return 'diamond';
     default: return 'ellipse';
   }

   // ✅ GOOD: Configurable mapping with defaults
   const defaultShapes = {
     'class': 'roundrectangle',
     'association': 'diamond',
     'property': 'ellipse'
   };
   const getNodeShape = (nodeType: string) =>
     defaultShapes[nodeType] || 'ellipse';
   ```

4. **Dynamic Filter Generation**
   ```typescript
   // ✅ GOOD: Generate filters from actual data
   const availableCategories = [
     ...new Set(graphData.namespaces.map(ns => ns.category))
   ];

   return (
     <div>
       {availableCategories.map(cat => (
         <Checkbox key={cat} label={cat} />
       ))}
     </div>
   );
   ```

5. **Unknown Value Handling**
   - Always provide visual feedback for unknown categories/types
   - Log unexpected values (helps identify CMF parsing issues)
   - Use neutral defaults (gray color, basic shape)
   - Display actual value in detail panel

**Benefits**:
- Works with any NIEM version (6.0, 7.0, future)
- Supports custom CMF extensions
- No frontend updates needed when CMF spec evolves
- Future-proof architecture

## 12. Future Enhancements (Post-v1.0)

- Schema comparison/diff view
- Collaborative annotation/comments
- Custom layouts (save preferred arrangement)
- Advanced filtering (by property type, cardinality, etc.)
- Graph analytics (centrality, clustering)
- Integration with external NIEM tools
- Schema templates and generators
