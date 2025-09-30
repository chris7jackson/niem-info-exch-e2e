"""
NIEM Schema Processing Domain

Handles NIEM schema operations:
- Tree shaking (element-level dependency analysis)
- Dependency resolution (fetching required NIEM schemas)
- Validation (NIEM Naming & Design Rules conformance)
- Mapping generation (CMF to YAML mapping)
- Mapping validation (coverage analysis)
"""

from .treeshaker import ElementLevelTreeshaker, create_element_level_treeshaker
from .resolver import resolve_niem_schema_dependencies, get_treeshaking_statistics
from .validator import NiemNdrValidator, validate_niem_conformance
from .mapping import (
    generate_mapping_from_cmf_content,
    generate_mapping_from_cmf_file,
    validate_mapping_coverage_from_data
)

__all__ = [
    # Treeshaker
    'ElementLevelTreeshaker',
    'create_element_level_treeshaker',
    # Resolver
    'resolve_niem_schema_dependencies',
    'get_treeshaking_statistics',
    # Validator
    'NiemNdrValidator',
    'validate_niem_conformance',
    # Mapping
    'generate_mapping_from_cmf_content',
    'generate_mapping_from_cmf_file',
    'validate_mapping_coverage_from_data',
]
