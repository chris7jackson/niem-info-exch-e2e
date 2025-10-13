# NIEM CMF Tool

## Attribution
- **Source Repository:** https://github.com/niemopen/cmftool
- **License:** Apache License 2.0 (see LICENSE file in this directory)
- **Current Version:** v1.0-alpha.8
- **Date Added:** September 23, 2025
- **Modifications:** None - vendored as-is from official release

## Purpose
The CMF (Common Model Format) tool is used for working with NIEM schemas and models, providing conversion and validation capabilities for NIEM-based information exchanges.

## Prerequisites
- Java Runtime Environment (JRE) required

## Update Instructions
To update to a newer version:

1. Download latest release from https://github.com/niemopen/cmftool/releases
2. Extract to new versioned directory: `third_party/niem-cmf/cmftool-X.Y.Z/`
3. Update "Current Version" and "Date Added" in this README
4. Update any API integration code in `api/src/niem_api/clients/cmf_client.py` if needed
5. Test validation pipeline with sample data in `samples/CrashDriver-cmf/`

## Usage
This tool is integrated into the NIEM validation pipeline via `api/src/niem_api/clients/cmf_client.py`. Direct usage via command line is also supported through the binaries in `cmftool-1.0-alpha.8/bin/`.

## Future Improvements
Consider migrating to git submodule for easier version tracking and updates (see backlog).
