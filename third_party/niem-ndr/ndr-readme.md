# NIEM NDR (Naming and Design Rules) Tools

This directory contains the NIEM NDR validation tools and schematron files needed for validating NIEM schemas and instances.

## Source Repositories

The files in this directory are fetched from two main NIEM source repositories:

### 1. NIEM-NDR (Execution Tools)
- **Repository**: https://github.com/NIEM/NIEM-NDR
- **Purpose**: Provides the core execution tools for running schematron validation
- **Files fetched**:
  - `bin/` - Schematron execution scripts and tools
  - `pkg/` - Supporting packages including Saxon JAR and ISO schematron XSLT files
- **Last fetched**: September 22, 2025

### 2. NIEM Naming Design Rules (Validation Rules)
- **Repository**: https://github.com/niemopen/niem-naming-design-rules/
- **Purpose**: Contains the NIEM 6.0 validation rules and schematron definitions
- **Files fetched**:
  - `rule/` - Individual schematron rule files for specific NDR rules
  - `src/` - Source schematron files and supporting XSLT functions
- **Last fetched**: September 22, 2025

## How to Update

To fetch the latest files from the source repositories:

### Option 1: Manual Download
1. Visit the repositories above
2. Download the required directories/files
3. Replace the corresponding files in this directory
4. Update the "Last updated" dates in this readme

### Option 2: Git Clone (for development)
```bash
# Clone the repositories to temporary directories
git clone https://github.com/NIEM/NIEM-NDR.git temp-niem-ndr
git clone https://github.com/niemopen/niem-naming-design-rules.git temp-ndr-rules

# Copy required files
cp -r temp-niem-ndr/bin ./
cp -r temp-niem-ndr/pkg ./
cp -r temp-ndr-rules/rule ./
cp -r temp-ndr-rules/src ./

## File Structure

```
niem-ndr/
├── bin/                    # Execution tools (from NIEM-NDR)
│   └── schematron         # Main schematron execution script
├── pkg/                    # Supporting packages (from NIEM-NDR)
│   ├── saxon/             # Saxon XSLT processor
│   └── iso-schematron-xslt2/ # ISO schematron XSLT templates
├── rule/                   # Individual NDR rule files (from niemopen/ndr)
├── src/                    # Source schematron and XSLT files (from niemopen/ndr)
│   ├── ndr-functions.xsl  # Core NDR validation functions
│   └── *.sch             # Schematron source files
├── all-complete.sch        # Complete NDR schematron (MUST CREATE LOCALLY)
├── ins-generated.sch       # Instance validation schematron (MUST CREATE LOCALLY)
└── ndr-readme.md          # This file
```

## Usage in Application

The NIEM API uses these tools for:

1. **Schema Validation**: `all-complete.sch` is pre-compiled into XSLT for fast schema validation
2. **Instance Validation**: `ins-generated.sch` is used for validating XML instances
3. **Rule Functions**: `src/ndr-functions.xsl` provides supporting functions for validation

The validation process is handled by `src/niem_api/services/ndr_validator.py` which:
- Pre-compiles schematron files at startup for optimal performance
- Uses Saxon processor for XSLT transformations
- Provides structured validation reports in SVRL format

## Version Compatibility

- **NIEM Version**: 6.0
- **Schematron**: ISO Schematron (XSLT2 implementation)
- **Saxon Version**: 9HE (included in pkg/saxon/)
- **Java Requirement**: OpenJDK 21+ (for Saxon execution)