"""
NIEM Schema Processing Domain

Handles NIEM schema operations:
- Schema validation (dependency checking within uploaded files)
- Validation (NIEM Naming & Design Rules conformance)
- Mapping generation (CMF to YAML mapping)
- Mapping validation (coverage analysis)
"""

from .mapping import (
    generate_mapping_from_cmf_content,
    generate_mapping_from_cmf_file,
)
from .resolver import validate_schema_dependencies
from .validator import NiemNdrValidator, validate_niem_conformance

__all__ = [
    # Schema validation
    'validate_schema_dependencies',
    # NDR Validator
    'NiemNdrValidator',
    'validate_niem_conformance',
    # Mapping
    'generate_mapping_from_cmf_content',
    'generate_mapping_from_cmf_file',
]
