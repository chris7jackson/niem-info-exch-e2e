# NIEM NDR (Naming and Design Rules) Tools

## Attribution

This directory contains NIEM NDR validation tools and schematron files from two NIEM Open source repositories.

- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0) - see LICENSE file
- **NIEM Version:** 6.0
- **Date Added:** September 22, 2025
- **Production Deployment:** Embedded in Docker image (no external volume mounts required)

## Source Repositories

The files in this directory are fetched from two main NIEM source repositories:

### 1. NIEM-NDR (Execution Tools)
- **Repository:** https://github.com/NIEM/NIEM-NDR
- **Purpose:** Provides the core execution tools for running schematron validation
- **Files fetched:**
  - `bin/` - Schematron execution scripts and tools
  - `pkg/` - Supporting packages including Saxon JAR and ISO schematron XSLT files
- **Last Updated:** September 22, 2025

### 2. NIEM Naming Design Rules (Validation Rules)
- **Repository:** https://github.com/niemopen/niem-naming-design-rules/
- **Purpose:** Contains the NIEM 6.0 validation rules and schematron definitions
- **Files fetched:**
  - `rule/` - Individual schematron rule files for specific NDR rules (159 files)
  - `src/` - Source schematron files and supporting XSLT functions
- **Last Updated:** September 22, 2025

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

**Step 3: Rebuild Docker image**
```bash
# Rebuild the API Docker image to embed the updated tools
cd "$PROJECT_ROOT"
docker compose build api
```

**Step 4: Test the updated rules**
```bash
# Run API validation tests to ensure compatibility
cd "$PROJECT_ROOT/api"
pytest tests/integration/test_schema_validation.py -v
```

**Step 5: Update this README**
- Update "Last Updated" dates above
- Document any breaking changes or new requirements

## File Structure

```
niem-ndr/
├── LICENSE                           # CC BY 4.0 license
├── ndr-readme.md                     # This file
├── bin/                              # Execution tools (from NIEM-NDR)
│   └── schematron                    # Main schematron execution script
├── pkg/                              # Supporting packages (from NIEM-NDR)
│   ├── saxon/                        # Saxon XSLT processor
│   └── iso-schematron-xslt2/         # ISO schematron XSLT templates
├── sch/                              # Pre-compiled XSLT validation files
│   ├── refTarget-6.0.xsl             # Reference schema validation
│   ├── extTarget-6.0.xsl             # Extension schema validation
│   ├── subTarget-6.0.xsl             # Subset schema validation
│   ├── hdr.sch                       # Header schematron fragment
│   ├── all.sch                       # Common schematron fragment
│   └── *.sch                         # Type-specific schematron fragments
└── src/                              # Source schematron and XSLT files (from niemopen/ndr)
    ├── ndr-functions.xsl             # Core NDR validation functions
    └── *.sch                         # Schematron source templates
```

## Usage in Application

The NIEM API uses these tools for schema validation:

**Integration Point:** `api/src/niem_api/services/domain/schema/validator.py`

The NDR validator:
1. **Uses pre-compiled XSLT files** (refTarget-6.0.xsl, extTarget-6.0.xsl, subTarget-6.0.xsl) for optimal performance
2. **Dynamically generates** composite schematron from source fragments (hdr.sch, all.sch, type-specific .sch) based on schema conformance targets
3. **Uses Saxon processor** (Java-based XSLT 2.0 engine) for transformations
4. **Returns** structured validation reports in SVRL (Schematron Validation Report Language) format

**Validation Flow:**
```
XSD Upload → Detect Conformance Target → Load Pre-compiled XSLT → Saxon Transform → SVRL Report → API Response
```

## Version Compatibility

- **NIEM Version:** 6.0
- **Schematron:** ISO Schematron (XSLT2 implementation)
- **Saxon Version:** 9HE (included in pkg/saxon/)
- **Java Requirement:** OpenJDK 21+ (for Saxon execution)
- **Validation Targets:** Reference (REF), Extension (EXT), and Subset (SUB) schemas

## Future Improvements

Consider migrating to git submodules for easier version tracking and updates (see backlog).