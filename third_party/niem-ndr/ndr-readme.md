# NIEM NDR (Naming and Design Rules) Tools

## Attribution

This directory contains NIEM NDR validation tools and schematron files from two NIEM Open source repositories.

- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0) - see LICENSE file
- **NIEM Version:** 6.0
- **Date Added:** September 22, 2024
- **Modifications:** Custom `all-complete.sch` created locally (see below)

## Source Repositories

The files in this directory are fetched from two main NIEM source repositories:

### 1. NIEM-NDR (Execution Tools)
- **Repository:** https://github.com/NIEM/NIEM-NDR
- **Purpose:** Provides the core execution tools for running schematron validation
- **Files fetched:**
  - `bin/` - Schematron execution scripts and tools
  - `pkg/` - Supporting packages including Saxon JAR and ISO schematron XSLT files
- **Last Updated:** September 22, 2024

### 2. NIEM Naming Design Rules (Validation Rules)
- **Repository:** https://github.com/niemopen/niem-naming-design-rules/
- **Purpose:** Contains the NIEM 6.0 validation rules and schematron definitions
- **Files fetched:**
  - `rule/` - Individual schematron rule files for specific NDR rules (159 files)
  - `src/` - Source schematron files and supporting XSLT functions
- **Last Updated:** September 22, 2024

## Custom Files (Local Modifications)

### all-complete.sch
This is a **custom-created** comprehensive schematron file that aggregates 143 individual NDR validation rules from the `rule/` directory. This file is NOT from upstream and must be maintained locally.

**Purpose:** Provides a single schematron file for complete NIEM 6.0 schema validation
**Rule Count:** 143 includes (out of 159 available rules)
**Location:** `third_party/niem-ndr/all-complete.sch`
**Used By:** `api/src/niem_api/services/domain/schema/validator.py`

## How to Update

### Updating from Source Repositories

To fetch the latest files from the source repositories:

**Step 1: Clone the repositories**
```bash
# Navigate to a temporary directory
cd /tmp

# Clone both source repositories
git clone https://github.com/NIEM/NIEM-NDR.git
git clone https://github.com/niemopen/niem-naming-design-rules.git
```

**Step 2: Copy required files**
```bash
# From your project root
PROJECT_ROOT="/Users/cjackson/Workspace/GraphRAG/niem-info-exch-e2e"
NDR_DIR="$PROJECT_ROOT/third_party/niem-ndr"

# Copy execution tools
cp -r /tmp/NIEM-NDR/bin "$NDR_DIR/"
cp -r /tmp/NIEM-NDR/pkg "$NDR_DIR/"

# Copy validation rules
cp -r /tmp/niem-naming-design-rules/rule "$NDR_DIR/"
cp -r /tmp/niem-naming-design-rules/src "$NDR_DIR/"
```

**Step 3: Update all-complete.sch** (if new rules added)
```bash
# Check for new rule files
ls "$NDR_DIR/rule/" | wc -l  # Compare with current count (159)

# If new rules exist, update all-complete.sch manually:
# 1. Open all-complete.sch in editor
# 2. Add new <include href="rule/X-Y.xml"/> entries
# 3. Maintain numerical order for readability
# 4. Update rule count in this README
```

**Step 4: Test the updated rules**
```bash
# Run API validation tests to ensure compatibility
cd "$PROJECT_ROOT/api"
pytest tests/integration/test_schema_validation.py -v
```

**Step 5: Update this README**
- Update "Last Updated" dates above
- Update rule count if changed
- Document any breaking changes or new requirements

### Regenerating all-complete.sch from Scratch

If you need to rebuild `all-complete.sch` completely:

1. **List all available rules:**
   ```bash
   ls third_party/niem-ndr/rule/
   ```

2. **Create the schematron header:**
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <schema xmlns="http://purl.oclc.org/dsdl/schematron"
           queryBinding="xslt2">
     <ns prefix="xs" uri="http://www.w3.org/2001/XMLSchema"/>
     <!-- Add other namespace declarations -->

     <xsl:include href="src/ndr-functions.xsl"/>
   </schema>
   ```

3. **Add include statements for each rule file:**
   ```xml
   <include href="rule/7-2a.xml"/>
   <include href="rule/7-2b.xml"/>
   <!-- ... continue for all rules ... -->
   ```

4. **Verify rule coverage** matches your validation requirements

**Note:** The current `all-complete.sch` includes 143 out of 159 available rules. Some rules may be excluded intentionally for compatibility or performance reasons.

## File Structure

```
niem-ndr/
├── LICENSE                           # CC BY 4.0 license
├── ndr-readme.md                     # This file
├── all-complete.sch                  # ⚠️ CUSTOM: Complete NDR schematron (143 rules)
├── bin/                              # Execution tools (from NIEM-NDR)
│   └── schematron                    # Main schematron execution script
├── pkg/                              # Supporting packages (from NIEM-NDR)
│   ├── saxon/                        # Saxon XSLT processor
│   └── iso-schematron-xslt2/         # ISO schematron XSLT templates
├── rule/                             # Individual NDR rule files (from niemopen/ndr)
│   ├── 7-2a.xml                      # Example: Component naming rule
│   ├── 7-2b.xml
│   └── ... (159 total rule files)
└── src/                              # Source schematron and XSLT files (from niemopen/ndr)
    ├── ndr-functions.xsl             # Core NDR validation functions
    └── *.sch                         # Schematron source templates
```

⚠️ **CUSTOM FILE:** `all-complete.sch` is created and maintained locally

## Usage in Application

The NIEM API uses these tools for schema validation:

**Integration Point:** `api/src/niem_api/services/domain/schema/validator.py`

The NDR validator:
1. **Pre-compiles** `all-complete.sch` into XSLT at startup for optimal performance
2. **Uses Saxon processor** (Java-based XSLT 2.0 engine) for transformations
3. **Generates** instance schematron dynamically based on uploaded schemas
4. **Returns** structured validation reports in SVRL (Schematron Validation Report Language) format

**Validation Flow:**
```
XSD Upload → NDR Validator → all-complete.sch → Saxon XSLT → SVRL Report → API Response
```

## Version Compatibility

- **NIEM Version:** 6.0
- **Schematron:** ISO Schematron (XSLT2 implementation)
- **Saxon Version:** 9HE (included in pkg/saxon/)
- **Java Requirement:** OpenJDK 21+ (for Saxon execution)
- **NDR Rules:** 143 active rules (from 159 available)

## Future Improvements

Consider migrating to git submodules for easier version tracking and updates (see backlog).