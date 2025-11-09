"""
NIEM Schema Processing Domain

Handles NIEM schema operations:
- Schema validation (dependency checking within uploaded files)
- Validation (NIEM Naming & Design Rules conformance via scheval)
- Mapping generation (CMF to YAML mapping)
- Mapping validation (coverage analysis)
"""

from .mapping import (
    generate_mapping_from_cmf_content,
    generate_mapping_from_cmf_file,
)
from .resolver import validate_schema_dependencies

__all__ = [
    # Schema validation
    "validate_schema_dependencies",
    # Mapping
    "generate_mapping_from_cmf_content",
    "generate_mapping_from_cmf_file",
]
