# Schema Browser - User Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Understanding the Interface](#understanding-the-interface)
4. [Navigating the Graph](#navigating-the-graph)
5. [Using Filters](#using-filters)
6. [Expanding and Collapsing Nodes](#expanding-and-collapsing-nodes)
7. [Finding Relationships](#finding-relationships)
8. [Exporting Diagrams](#exporting-diagrams)
9. [Tips and Tricks](#tips-and-tricks)
10. [Troubleshooting](#troubleshooting)

---

## Introduction

The Schema Browser is a visual tool for exploring NIEM (National Information Exchange Model) schemas. It displays schema types, properties, and relationships as an interactive graph, making it easy to understand complex schema structures.

### Who Should Use This Guide
- IEPD Developers building information exchanges
- Schema Architects designing data models
- Data Analysts understanding NIEM structure
- Anyone working with NIEM schemas

### What You'll Learn
- How to navigate schema graphs
- How to find relationships between types
- How to filter and search schemas
- How to export diagrams for documentation

---

## Getting Started

### Accessing the Schema Browser

1. Navigate to the NIEM application
2. Click **"Schema Browser"** in the main navigation
3. Select a schema from the dropdown menu
4. The graph will load automatically

### First Time Setup

**No setup required!** The Schema Browser works immediately after a schema is uploaded.

### System Requirements

- **Browser**: Chrome 90+, Firefox 88+, Safari 14+, or Edge 90+
- **Screen**: Minimum 1024px width (desktop or laptop)
- **Connection**: Active internet connection

---

## Understanding the Interface

### Layout Overview

The Schema Browser has three main sections:

```
┌─────────────────────────────────────────────────┐
│  1. FILTERS      2. GRAPH CANVAS    3. DETAILS  │
│  (Left)          (Center)           (Right)     │
└─────────────────────────────────────────────────┘
```

### 1. Filters Panel (Left)

**Search Box**
- Type to search for types by name
- Matching nodes highlight in yellow
- Shows result count

**Namespace Filters**
- ☑ **NIEM Core (nc)** - Blue nodes, core NIEM types
- ☑ **Justice Domain (j)** - Green nodes, justice-specific types
- ☑ **Extension (exch)** - Orange nodes, your custom types
- ☐ **Code Tables** - Purple nodes, enumeration codes

**Type Filters**
- ☑ **Classes** - Rectangle nodes (e.g., PersonType)
- ☑ **Associations** - Diamond nodes (e.g., CrashDriver)
- ☑ **Properties** - Circle nodes (e.g., PersonName)

**Depth Slider**
- Controls how many levels deep to show
- Slide right to show more levels (1-10)

**Clear Filters Button**
- Resets all filters to defaults

### 2. Graph Canvas (Center)

**The Interactive Graph**
- Displays nodes (boxes/circles) and edges (arrows)
- Zoom with mouse wheel
- Pan by dragging canvas
- Click nodes to select

**Controls Below Graph**
- **[Fit to Screen]** - Auto-zoom to show all nodes
- **[Reset View]** - Return to initial zoom/pan
- **[Expand All]** - Expand all nodes to 3 levels
- **[Collapse All]** - Collapse to root level only
- **[Export PNG]** - Save diagram as image
- **[Export SVG]** - Save as scalable vector

**Layout Selector**
- **Tree** - Hierarchical top-down layout
- **Radial** - Circular layout
- **Force** - Physics-based clustering
- **Network** - Full graph view

### 3. Detail Panel (Right)

**Appears when you click a node**

Shows:
- Full qualified name (e.g., `nc:PersonType`)
- Namespace information
- Type category (ObjectType, AssociationType, etc.)
- Documentation/definition
- List of properties
- "Used In" count (how many other types reference this)
- Augmentations (if applicable)
- Base type (if extends another type)

**Quick Actions**
- **[View in Tree]** - Switch to tree graph mode
- **[View in Network]** - Switch to network mode
- **[X Close]** - Hide detail panel

---

## Navigating the Graph

### Basic Navigation

| Action | How To |
|--------|--------|
| **Zoom In** | Scroll mouse wheel up |
| **Zoom Out** | Scroll mouse wheel down |
| **Pan** | Click and drag canvas |
| **Select Node** | Single click on node |
| **Multi-Select** | Hold Ctrl + click nodes |
| **Deselect** | Click on empty canvas |

### View Modes

**Tree Graph Mode**
- Shows hierarchical parent-child relationships
- Good for: Understanding structure, browsing by category
- Default layout: Top-down tree

**Network Graph Mode**
- Shows all relationships (properties, associations, augmentations)
- Good for: Finding connections, exploring dependencies
- Default layout: Force-directed (physics simulation)

### Reading the Graph

**Node Colors**
- 🔵 **Blue** = NIEM Core types (nc namespace)
- 🟢 **Green** = NIEM Domain types (j, hs, etc.)
- 🟠 **Orange** = Extension/IEPD types (your custom types)
- 🟣 **Purple** = Code/enumeration types

**Node Shapes**
- **Rectangle** = Class/ObjectType
- **Diamond** = Association (relates two types)
- **Circle** = Property
- **Hexagon** = Augmentation

**Node Size**
- **Larger** = More connections (heavily used type)
- **Smaller** = Fewer connections (leaf type)

**Edge Styles**
- **Solid arrow** → Property relationship
- **Dashed arrow** ⇢ Association
- **Dotted arrow** ⋯> Augmentation
- **Bold arrow** ━> Type extension/inheritance

**Edge Labels**
- Show property or relationship name
- Example: `PersonName`, `CrashDriver`

---

## Using Filters

### Searching for Types

1. Type a search term in the search box (e.g., "person")
2. Matching nodes highlight in **yellow**
3. Result count shows: "Found 12 nodes matching 'person'"
4. Clear search by deleting text

**Search Tips:**
- Search is case-insensitive
- Partial matches work (e.g., "crash" finds "CrashType", "CrashDriver")
- Search searches node names only, not documentation

### Filtering by Namespace

**To focus on your IEPD extensions:**
1. Uncheck **NIEM Core (nc)**
2. Uncheck **Justice Domain (j)**
3. Leave only **Extension (exch)** checked
4. Graph shows only your custom types

**To see only NIEM standard types:**
1. Check **NIEM Core** and **Domain** boxes
2. Uncheck **Extension**
3. Graph shows only standard NIEM types

### Filtering by Type

**To see only classes (no properties):**
1. Check **Classes**
2. Uncheck **Associations** and **Properties**
3. Graph shows simplified structure with just type definitions

**To see only associations (relationships):**
1. Check **Associations**
2. Uncheck **Classes** and **Properties**
3. Graph shows how types relate to each other

### Using the Depth Slider

**Problem**: Graph is too large and overwhelming

**Solution**: Reduce depth
1. Move slider to left (e.g., depth = 2)
2. Graph shows only 2 levels of hierarchy
3. Gradually increase depth to explore deeper

**Example:**
- Depth 1: Shows only top-level types
- Depth 2: Shows types and their immediate properties
- Depth 3: Shows properties and their sub-properties

---

## Expanding and Collapsing Nodes

### Double-Click Expand/Collapse

**To expand a node:**
1. Double-click on the node
2. Its children appear with animation
3. Node shows **[-]** indicator

**To collapse a node:**
1. Double-click the expanded node again
2. Children disappear
3. Node shows **[+]** indicator

### Expand All / Collapse All

**Expand All Button**
- Click **[Expand All]** below the graph
- All nodes expand to 3 levels deep
- Useful for: Seeing full schema structure

**Collapse All Button**
- Click **[Collapse All]** below the graph
- All nodes collapse to root level
- Useful for: Starting fresh, reducing clutter

### Right-Click Context Menu

Right-click on a node to see options:
- **Expand Children** - Show direct children only
- **Collapse Children** - Hide direct children
- **Expand All Descendants** - Show all descendants (full subtree)
- **Show Only This** - Hide everything except this node and its connections

### Progressive Exploration Workflow

1. Start with **Collapse All**
2. Double-click a type you're interested in (e.g., `PersonType`)
3. See its properties expand
4. Double-click a property (e.g., `PersonName`)
5. See its sub-properties
6. Continue drilling down as needed

---

## Finding Relationships

### Understanding Relationships in NIEM

**Property Relationships**
- Show what properties a type has
- Example: `PersonType` has property `PersonName`
- Displayed as solid arrows

**Associations**
- Show explicit relationships between entities
- Example: `CrashDriver` associates `CrashType` with `PersonType`
- Displayed as dashed arrows
- Often have their own properties

**Augmentations**
- Show where types are extended with custom properties
- Example: `PersonAugmentation` adds custom fields to NIEM's `PersonType`
- Displayed as dotted arrows

### Path Finding Feature

**Use Case**: "How does CrashType relate to PersonBirthDate?"

**Steps:**
1. Click on `CrashType` node
2. Hold **Ctrl** and click `PersonBirthDate` node
3. Click **[Find Path]** button (appears when 2 nodes selected)
4. Shortest path highlights in green
5. Path description shows: "4-hop path via association → property → property"

**Interpreting the Path:**
```
CrashType
   → CrashDriver (association)
   → PersonType (property)
   → PersonBirthDate (property)
```

**To clear path:**
- Click **[Clear Path]** button
- Or click on empty canvas

### Common Use Cases

**Use Case 1: Finding Properties of a Type**
1. Search for the type (e.g., "PersonType")
2. Double-click to expand
3. See all properties listed as children

**Use Case 2: Finding What Uses a Type**
1. Click the type node
2. Look at Detail Panel on right
3. See "Used In" section with count and list
4. Click an item to navigate to that type

**Use Case 3: Understanding an Association**
1. Filter to show only Associations (diamond nodes)
2. Click on an association (e.g., `CrashDriver`)
3. See source and target in Detail Panel
4. See what the association connects

---

## Exporting Diagrams

### Export as PNG Image

**Steps:**
1. Adjust view (zoom, pan, filters) to show what you want
2. Click **[Export PNG]** button
3. Image downloads automatically (1920x1080 resolution)
4. Use in documentation, presentations, reports

**Tips:**
- Use "Fit to Screen" before exporting for best framing
- Apply filters to simplify diagram for clarity
- Export multiple views (tree, network) for comparison

### Export as SVG Vector

**Steps:**
1. Click **[Export SVG]** button
2. SVG file downloads
3. Open in vector editors (Illustrator, Inkscape, etc.)
4. Edit, resize, or annotate as needed

**Advantages of SVG:**
- Scalable to any size without quality loss
- Editable text and shapes
- Smaller file size than PNG

### Copy Shareable Link

**Steps:**
1. Set up your desired view (filters, layout, zoom)
2. Click **[Copy Link]** button (if available)
3. Paste link in email, chat, documentation
4. Anyone with link sees the same filtered view

**Use Cases:**
- Share specific view with team members
- Bookmark frequently used filter combinations
- Include in documentation with "View Live" links

### Export Subgraph Data

**Steps:**
1. Apply filters to show only nodes you want
2. Click **[Export Data]** button
3. JSON file downloads with filtered graph
4. Use in custom tools or scripts

---

## Tips and Tricks

### Performance Optimization

**For Large Schemas (1000+ types):**
- Start with Depth = 1
- Use namespace filters to show one namespace at a time
- Use Search instead of Expand All
- Close Detail Panel when not needed

### Efficient Exploration

**Top-Down Approach (Recommended):**
1. Start with Tree Graph mode
2. Collapse All
3. Expand only namespaces you care about
4. Drill down into specific types

**Bottom-Up Approach:**
1. Search for a specific type you know
2. Click to see details
3. Use "Used In" to find related types
4. Explore connections from there

### Layout Selection Guide

| Layout | Best For | When To Use |
|--------|----------|-------------|
| **Tree** | Clear hierarchy | Understanding parent-child relationships |
| **Radial** | Space efficiency | Schemas with wide, shallow structures |
| **Force** | Natural clustering | Finding related groups of types |
| **Network** | Full view | Seeing all relationships at once |

### Keyboard Shortcuts (if implemented)

| Key | Action |
|-----|--------|
| `Space` | Fit to screen |
| `Escape` | Deselect all / Close detail panel |
| `Ctrl + F` | Focus search box |
| `Ctrl + A` | Select all visible nodes |
| `+` / `-` | Zoom in / out |
| `Arrow Keys` | Pan canvas |

---

## Troubleshooting

### Problem: Graph is too cluttered

**Solution 1**: Use Depth Slider
- Reduce depth to 1 or 2
- Only essential levels show

**Solution 2**: Apply Namespace Filters
- Uncheck namespaces you don't need
- Focus on specific domain

**Solution 3**: Collapse All
- Reset to root level
- Expand only what you need

### Problem: Can't find a specific type

**Solution 1**: Use Search
- Type the type name in search box
- Matching nodes highlight

**Solution 2**: Check Filters
- Make sure namespace containing the type is checked
- Make sure type filter is enabled (e.g., Classes)

**Solution 3**: Increase Depth
- Type might be hidden due to depth limit
- Move slider to right

### Problem: Graph won't load

**Possible Causes:**
1. Schema not uploaded yet → Upload schema first
2. Browser compatibility → Use Chrome, Firefox, Safari, or Edge
3. Network issue → Check internet connection
4. CMF parsing error → Check browser console for errors

**Solution**: Refresh page, check schema selector dropdown

### Problem: Export button doesn't work

**Solution:**
- Check browser popup blocker settings
- Allow downloads from the site
- Try different export format (PNG vs SVG)

### Problem: Detail panel not showing

**Solution:**
- Click directly on a node (not edge or background)
- Make sure node is visible (not filtered out)
- Check if panel is hidden off-screen (resize browser window)

### Problem: Performance is slow

**Causes:**
- Very large schema (5000+ types)
- All nodes expanded
- Too many filters active

**Solutions:**
- Reduce depth
- Collapse unnecessary branches
- Use namespace filters to reduce visible nodes
- Close other browser tabs
- Try Tree layout instead of Force layout

---

## Example Workflows

### Workflow 1: Understanding CrashDriver IEPD

**Goal**: Understand what types are used in CrashDriver exchange

**Steps:**
1. Select "CrashDriver IEPD" schema
2. Switch to Tree Graph mode
3. Apply filters: Check only "Extension (exch)"
4. See your custom extension types (e.g., `CrashDriverInfoType`)
5. Double-click `CrashDriverInfoType` to see properties
6. For each property, click to see detail panel
7. Note which NIEM types are referenced (shown in different colors)

**Result**: Clear understanding of IEPD structure and NIEM dependencies

### Workflow 2: Finding Reusable NIEM Types

**Goal**: Find if NIEM already has a type for "driver license number"

**Steps:**
1. Select a NIEM schema (Core or Justice domain)
2. Type "license" in search box
3. See highlighted nodes: `DriverLicense`, `DriverLicenseIdentification`, etc.
4. Click each to see Detail Panel
5. Check properties to find `DriverLicenseCardIdentification`
6. Export PNG of relevant section for documentation

**Result**: Found reusable NIEM type, no need to create custom type

### Workflow 3: Documenting Schema for Stakeholders

**Goal**: Create visual documentation of schema structure

**Steps:**
1. Load your schema
2. Tree Graph mode, Collapse All
3. Expand to Depth 2
4. Apply filter: Show only Extension namespace
5. Click [Fit to Screen]
6. Click [Export PNG]
7. Add to PowerPoint/Word document
8. Repeat for Network Graph mode
9. Include both views in documentation

**Result**: Professional visual schema documentation

---

## Glossary

| Term | Definition |
|------|------------|
| **Node** | A box or shape representing a type, property, or association |
| **Edge** | An arrow connecting two nodes, showing a relationship |
| **Namespace** | A collection of related types (e.g., NIEM Core, Justice) |
| **Class** | A type definition (e.g., PersonType, VehicleType) |
| **Property** | A field within a type (e.g., PersonName, PersonBirthDate) |
| **Association** | An explicit relationship type (e.g., CrashDriver) |
| **Augmentation** | A mechanism to extend NIEM types with custom properties |
| **CMF** | Common Model Format - NIEM's canonical model format |
| **IEPD** | Information Exchange Package Documentation |
| **Cardinality** | How many times a property can appear ([1..1], [0..unbounded]) |
| **Depth** | How many levels deep in the hierarchy to show |

---

## Additional Resources

- **NIEM Documentation**: https://niem.github.io/
- **CMF Specification**: https://docs.oasis-open.org/niemopen/
- **Report Issues**: Contact system administrator or file bug report
- **Training Videos**: (Link to video tutorials if available)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | January 7, 2025 | Initial release - CMF graph visualization |

---

## Feedback

We welcome your feedback! If you encounter issues or have suggestions for improvements, please contact the development team.
