---
name: Data import wizard for graph structure definition
about: Interactive UI to map XML/JSON elements to graph nodes and properties
title: 'Build interactive data import wizard for graph structure customization'
labels: enhancement, ui, complex, future, wizard
assignees: ''
---

## Problem Statement

Currently, the mapping from NIEM XML/JSON to Neo4j graph structure is defined in `mapping.yaml`, which requires:
- Manual YAML editing
- Understanding of graph modeling concepts
- Technical knowledge of XPath, QNames, and Neo4j
- Restart/reload for changes to take effect

This creates a barrier for:
- Non-technical users
- Quick experimentation with different mappings
- Understanding how data maps to graph structure
- Visualizing the resulting graph schema

## User Value

- **Accessibility**: Non-developers can customize mappings
- **Visual understanding**: See how changes affect graph structure
- **Rapid iteration**: Test different mappings instantly
- **Reduced errors**: Wizard prevents invalid configurations
- **Discovery**: Explore XML/JSON structure interactively

## Proposed Solution

Build a multi-step wizard that:
1. Loads XML/JSON sample data
2. Visualizes document structure as tree
3. Lets users select elements to map as nodes
4. Lets users select properties for each node
5. Shows preview of resulting graph
6. Generates and saves mapping.yaml
7. Applies mapping to uploaded data

## Acceptance Criteria

- [ ] **Step 1: Upload Sample Data**
  - Upload XML or JSON file for analysis
  - Parse and extract structure
  - Display document overview

- [ ] **Step 2: Visualize Structure**
  - Tree view of XML/JSON hierarchy
  - Show element names, types, cardinality
  - Highlight current mapping (if exists)

- [ ] **Step 3: Node Selection**
  - Checkbox/select elements to map as nodes
  - Assign node labels (default from element name)
  - Mark required vs optional nodes

- [ ] **Step 4: Property Mapping**
  - For each node, select which sub-elements become properties
  - Choose property data types
  - Handle complex properties (nested objects)

- [ ] **Step 5: Relationship Definition**
  - Identify associations
  - Define edge labels and direction
  - Configure relationship properties

- [ ] **Step 6: Preview & Validation**
  - Show sample Cypher queries
  - Visualize resulting graph schema (nodes, edges, properties)
  - Validate mapping completeness
  - Check for conflicts/issues

- [ ] **Step 7: Save & Apply**
  - Generate mapping.yaml
  - Save to schema set
  - Option to apply to existing data (re-ingest)

- [ ] **Graph Schema Viewer**
  - Separate view showing all entity types
  - All relationship types and cardinality
  - Property lists per entity

## Technical Context

**High-Level Architecture:**
```
┌──────────────┐
│ Upload Sample│
│ XML/JSON     │
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ Parse & Build│
│ Element Tree │
└──────┬───────┘
       │
       ↓
┌──────────────┐      ┌──────────────┐
│ Wizard UI    │←────→│ Mapping      │
│ (React)      │      │ Generator    │
└──────┬───────┘      └──────────────┘
       │                      │
       ↓                      ↓
┌──────────────┐      ┌──────────────┐
│ Graph Schema │      │ mapping.yaml │
│ Visualizer   │      │ Output       │
└──────────────┘      └──────────────┘
```

**New Backend Services:**
- `api/src/niem_api/services/domain/mapping/wizard.py`
  - Parse sample document structure
  - Generate mapping suggestions (ML/heuristics)
  - Validate mapping completeness
  - Generate mapping.yaml from wizard selections

**New Frontend Components:**
- `ui/src/components/ImportWizard/`
  - `WizardContainer.tsx` - Stepper/nav
  - `SampleUpload.tsx` - Step 1
  - `StructureTree.tsx` - Step 2
  - `NodeSelector.tsx` - Step 3
  - `PropertyMapper.tsx` - Step 4
  - `RelationshipDefiner.tsx` - Step 5
  - `MappingPreview.tsx` - Step 6
  - `SaveAndApply.tsx` - Step 7
- `ui/src/components/GraphSchemaViewer.tsx` - Standalone viewer

**API Endpoints:**
```python
POST /api/mapping/analyze-sample
  → Parse sample, return structure tree

POST /api/mapping/suggest
  → AI/heuristic suggestions for mapping

POST /api/mapping/validate
  → Validate mapping configuration

POST /api/mapping/generate
  → Generate mapping.yaml from selections

POST /api/mapping/{schema_id}/apply
  → Apply new mapping to schema

GET /api/mapping/{schema_id}/schema
  → Get graph schema (entities, relationships)
```

## Implementation Notes

### Phase 1: Backend Services (8-12 hours)
1. **Sample Analysis Service:**
   - Parse XML/JSON to extract structure
   - Build element tree with types, cardinality
   - Identify potential nodes vs properties (heuristics)
   - Detect associations (elements with refs)

2. **Mapping Generator:**
   - Convert wizard selections to mapping.yaml format
   - Validate completeness
   - Check for circular references
   - Generate default labels and property names

3. **Graph Schema Extractor:**
   - Analyze existing mapping.yaml
   - Extract entity types, properties, relationships
   - Build schema representation for visualization

### Phase 2: UI Components (16-24 hours)
1. **Wizard Framework:**
   - Multi-step wizard with navigation
   - State management (Zustand or Context)
   - Progress indicator
   - Save draft capability

2. **Tree Visualization:**
   - Collapsible tree of XML/JSON structure
   - Icons for elements, attributes, text content
   - Badges for cardinality (1, 0..1, 0..*, 1..*)
   - Highlight selected nodes

3. **Interactive Mapping:**
   - Drag-and-drop for node/property assignment
   - Inline editing of labels
   - Type selection dropdowns
   - Relationship drawing tool

4. **Graph Preview:**
   - D3.js or vis.js graph visualization
   - Sample data flow through graph
   - Zoom, pan, node details
   - Export as image

### Phase 3: Integration & Polish (8-12 hours)
1. **API Integration:**
   - Wire up all wizard steps to backend
   - Handle loading states
   - Error handling and validation feedback

2. **User Experience:**
   - Tooltips and help text
   - Example mappings library
   - Guided tutorial for first-time users
   - Responsive design

3. **Testing:**
   - Unit tests for mapping generator
   - Integration tests for wizard flow
   - E2E test with sample data
   - Accessibility audit

## UI Mockup

**Step 3: Node Selection**
```
┌────────────────────────────────────────────────────────────┐
│ Data Import Wizard - Select Nodes                 [3 of 7] │
├────────────────────────────────────────────────────────────┤
│                                                              │
│  Select which elements should become nodes in the graph:   │
│                                                              │
│  ☐ NEICETransmittalDocument (root)                         │
│    ☑ j:Crash → [CrashNode ▼]                  REQUIRED    │
│      ☑ j:CrashDriver → [DriverNode ▼]                      │
│      ☑ j:CrashVehicle → [VehicleNode ▼]                    │
│      ☐ nc:ActivityDate (property)                          │
│    ☑ j:Charge → [ChargeNode ▼]                             │
│    ☑ j:PersonChargeAssociation → [Use as Relationship ✓]  │
│                                                              │
│  ℹ Tip: Elements with structures:id usually become nodes   │
│                                                              │
│  [◀ Back]                          [Continue ▶] [Cancel]   │
└────────────────────────────────────────────────────────────┘
```

## Related Issues

- Depends on: #1 (augmentation flattening) for clean property extraction
- Depends on: #3 (associations as edges) for relationship mapping
- Enhances: #6 (schema naming) for better organization
- Related to: Graph visualization features (#future)

## Priority

**Low / Future Enhancement** - High value but significant complexity

## Estimated Effort

**Extra Extra Large (XXL)** - ~32-48 hours (4-6 weeks part-time)
- Backend analysis & generation: 8-12 hours
- UI wizard framework: 16-24 hours
- Graph visualization: 8-12 hours
- Testing & polish: 8-12 hours
- Documentation: 4 hours

**Milestone Approach:**
- **M1**: Basic wizard (upload, node selection, save)
- **M2**: Property and relationship mapping
- **M3**: Graph preview and validation
- **M4**: Polish and advanced features

## Additional Context

**Similar Tools:**
- Neo4j Desktop Import Tool
- GraphQL Schema Designer
- Prisma Studio
- Firebase Data Modeler

**Technical Challenges:**
1. **Complex Nesting:** XML/JSON can be deeply nested
2. **Cardinality Detection:** Arrays vs single values
3. **Reference Resolution:** structures:uri, structures:ref
4. **Circular Dependencies:** A→B→A relationships
5. **Performance:** Large documents (1000+ elements)

**Libraries to Consider:**
- **Tree Visualization:** `react-complex-tree`, `rc-tree`
- **Graph Visualization:** `vis-network`, `cytoscape.js`, `react-flow`
- **Form State:** `react-hook-form`, `formik`
- **Drag-and-Drop:** `react-dnd`, `dnd-kit`

**Future Enhancements:**
- **AI-Assisted Mapping:** ML model suggests optimal mappings
- **Mapping Templates:** Pre-built mappings for common IEPDs
- **Collaborative Editing:** Multiple users work on mapping
- **Version Control:** Track mapping changes over time
- **Import/Export:** Share mappings between projects

**User Stories:**
1. As a **data analyst**, I want to map NIEM data to graph without learning YAML
2. As a **developer**, I want to visualize how my mapping affects the graph
3. As a **domain expert**, I want to customize which elements become nodes
4. As a **QA engineer**, I want to validate mapping before ingesting large datasets
