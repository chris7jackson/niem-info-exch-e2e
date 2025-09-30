#!/usr/bin/env python3

import logging
import re
from pathlib import Path
from typing import Dict, Set, Optional, Any
from xml.etree import ElementTree as ET

from .element_level_treeshaker import ElementLevelTreeshaker, create_element_level_treeshaker

logger = logging.getLogger(__name__)

NIEM_XSD_LOCAL_PATH = Path(__file__).parent.parent.parent.parent / "third_party" / "niem-xsd"

class NIEMDependencyResolver:
    """
    Resolves NIEM schema dependencies using local third_party files.

    Supports both file-level treeshaking (default) and element-level treeshaking
    for maximum size reduction while maintaining schema correctness.
    """

    def __init__(self, enable_element_treeshaking: bool = True):
        self._cache: Dict[str, str] = {}
        self._local_xsd_path = NIEM_XSD_LOCAL_PATH
        self._namespace_to_file_cache: Dict[str, str] = {}
        self._enable_element_treeshaking = enable_element_treeshaking
        self._element_treeshaker: Optional[ElementLevelTreeshaker] = None

        if self._enable_element_treeshaking:
            self._element_treeshaker = create_element_level_treeshaker()
            logger.info("Element-level treeshaking enabled for maximum size reduction")

    def _extract_schema_locations(self, xsd_content: str) -> Set[str]:
        """Extract schemaLocation paths from XSD imports and namespace URIs from xmlns declarations"""
        schema_locations = set()

        try:
            # Parse XML to find xs:import elements and xmlns declarations
            root = ET.fromstring(xsd_content)

            # Find all xs:import elements with schemaLocation
            for elem in root.iter():
                if elem.tag.endswith('}import') or elem.tag == 'import':
                    schema_location = elem.get('schemaLocation')
                    if schema_location:
                        schema_locations.add(schema_location)

            # Extract xmlns namespace declarations from root element
            for key, value in root.attrib.items():
                # Look for xmlns:prefix or xmlns attributes
                if key.startswith('{http://www.w3.org/2000/xmlns/}') or key == 'xmlns':
                    # This is a namespace URI that might correspond to a NIEM schema
                    namespace_uri = value
                    if self._is_niem_namespace(namespace_uri):
                        # Convert namespace URI to schema file path
                        file_path = self._namespace_uri_to_file_path(namespace_uri)
                        schema_locations.add(file_path)
                        logger.debug(f"Found NIEM namespace dependency: {namespace_uri} -> {file_path}")

        except ET.ParseError as e:
            logger.error(f"Failed to parse XSD for dependency extraction: {e}")

            # Fallback to regex parsing for both schemaLocation and xmlns
            # Extract schemaLocation attributes
            import_pattern = r'schemaLocation\s*=\s*["\']([^"\']+)["\']'
            for match in re.finditer(import_pattern, xsd_content):
                schema_locations.add(match.group(1))

            # Extract xmlns declarations
            xmlns_pattern = r'xmlns(?::[^=\s]+)?\s*=\s*["\']([^"\']+)["\']'
            for match in re.finditer(xmlns_pattern, xsd_content):
                namespace_uri = match.group(1)
                if self._is_niem_namespace(namespace_uri):
                    # Convert namespace URI to schema file path
                    file_path = self._namespace_uri_to_file_path(namespace_uri)
                    schema_locations.add(file_path)
                    logger.debug(f"Found NIEM namespace dependency (regex): {namespace_uri} -> {file_path}")

        return schema_locations

    def _is_niem_namespace(self, namespace_uri: str) -> bool:
        """Check if a namespace URI corresponds to a NIEM schema"""
        niem_patterns = [
            'https://docs.oasis-open.org/niemopen/ns/model/niem-core/',
            'https://docs.oasis-open.org/niemopen/ns/model/domains/',
            'https://docs.oasis-open.org/niemopen/ns/model/adapters/',
            'https://docs.oasis-open.org/niemopen/ns/model/structures/',
            'https://docs.oasis-open.org/niemopen/ns/model/appinfo/',
            'https://docs.oasis-open.org/niemopen/ns/model/codes/'
        ]

        return any(namespace_uri.startswith(pattern) for pattern in niem_patterns)

    def _build_namespace_to_file_mapping(self) -> Dict[str, str]:
        """Dynamically build mapping from namespace URIs to file paths by scanning NIEM directory"""
        if self._namespace_to_file_cache:
            return self._namespace_to_file_cache

        logger.info("Building dynamic namespace to file mapping from NIEM directory")

        if not self._local_xsd_path.exists():
            logger.warning(f"NIEM directory not found: {self._local_xsd_path}")
            return {}

        # Scan all XSD files in the NIEM directory
        for xsd_file in self._local_xsd_path.rglob("*.xsd"):
            try:
                with open(xsd_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract targetNamespace from each schema
                root = ET.fromstring(content)
                target_namespace = root.get('targetNamespace')

                if target_namespace and self._is_niem_namespace(target_namespace):
                    # Convert absolute path to relative path from NIEM directory
                    relative_path = xsd_file.relative_to(self._local_xsd_path)
                    self._namespace_to_file_cache[target_namespace] = str(relative_path)
                    logger.debug(f"Mapped namespace: {target_namespace} -> {relative_path}")

            except Exception as e:
                logger.warning(f"Failed to parse {xsd_file} for namespace mapping: {e}")

        logger.info(f"Built namespace mapping for {len(self._namespace_to_file_cache)} NIEM schemas")
        return self._namespace_to_file_cache

    def _namespace_uri_to_file_path(self, namespace_uri: str) -> str:
        """Convert a NIEM namespace URI to the corresponding schema file path"""
        namespace_mapping = self._build_namespace_to_file_mapping()
        return namespace_mapping.get(namespace_uri, namespace_uri)


    def _extract_imported_namespaces(self, xsd_content: str) -> Set[str]:
        """Extract namespace URIs from xs:import elements and xsi:schemaLocation."""
        imported_namespaces = set()

        try:
            root = ET.fromstring(xsd_content)

            # Find all xs:import elements
            for elem in root.iter():
                if elem.tag.endswith('}import') or elem.tag == 'import':
                    namespace = elem.get('namespace')
                    if namespace:
                        imported_namespaces.add(namespace)

            # Also check xsi:schemaLocation in root element
            schema_location = root.get('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation')
            if schema_location:
                # xsi:schemaLocation format: "namespace1 location1 namespace2 location2"
                parts = schema_location.split()
                for i in range(0, len(parts), 2):
                    if i < len(parts):
                        namespace_uri = parts[i]
                        imported_namespaces.add(namespace_uri)

        except ET.ParseError as e:
            logger.warning(f"Failed to parse XSD for import extraction: {e}")
            # Fallback to regex parsing
            import_pattern = r'<xs:import[^>]+namespace\s*=\s*["\']([^"\']+)["\']'
            for match in re.finditer(import_pattern, xsd_content):
                imported_namespaces.add(match.group(1))

            # Also parse xsi:schemaLocation with regex
            schema_location_pattern = r'xsi:schemaLocation\s*=\s*["\']([^"\']+)["\']'
            for match in re.finditer(schema_location_pattern, xsd_content):
                schema_location = match.group(1)
                parts = schema_location.split()
                for i in range(0, len(parts), 2):
                    if i < len(parts):
                        namespace_uri = parts[i]
                        imported_namespaces.add(namespace_uri)

        return imported_namespaces

    def _extract_namespace_declarations(self, xsd_content: str) -> Dict[str, str]:
        """Extract namespace prefix to URI mappings from schema root element."""
        namespace_map = {}

        try:
            root = ET.fromstring(xsd_content)

            # Get all namespace declarations (xmlns:prefix="uri")
            for key, value in root.attrib.items():
                if key.startswith('{http://www.w3.org/2000/xmlns/}'):
                    # Remove namespace prefix to get the local prefix
                    prefix = key.split('}')[1] if '}' in key else ''
                    namespace_map[prefix] = value
                elif key == 'xmlns':
                    # Default namespace
                    namespace_map[''] = value

            # ElementTree doesn't always capture xmlns attributes correctly, so also use regex
            xmlns_pattern = r'xmlns:([^=\s]+)\s*=\s*["\']([^"\']+)["\']'
            for match in re.finditer(xmlns_pattern, xsd_content):
                prefix, uri = match.groups()
                namespace_map[prefix] = uri

        except ET.ParseError as e:
            logger.warning(f"Failed to parse XSD for namespace extraction: {e}")
            # Fallback to regex parsing only
            xmlns_pattern = r'xmlns:([^=\s]+)\s*=\s*["\']([^"\']+)["\']'
            for match in re.finditer(xmlns_pattern, xsd_content):
                prefix, uri = match.groups()
                namespace_map[prefix] = uri

        return namespace_map

    def _find_used_namespace_prefixes(self, xsd_content: str) -> Set[str]:
        """Find all namespace prefixes that are actually used in element/type references."""
        used_prefixes = set()

        # Pattern to find prefixed element/type references like "nc:Person", "j:Crash", etc.
        prefix_usage_patterns = [
            r'ref\s*=\s*["\']([^:"\'\s]+):',  # ref="prefix:ElementName"
            r'type\s*=\s*["\']([^:"\'\s]+):',  # type="prefix:TypeName"
            r'base\s*=\s*["\']([^:"\'\s]+):',  # base="prefix:BaseType"
            r'substitutionGroup\s*=\s*["\']([^:"\'\s]+):',  # substitutionGroup="prefix:Element"
            r'<([^:>\s]+):',  # <prefix:ElementName> (element declarations/usage)
            r'</([^:>\s]+):',  # </prefix:ElementName> (closing tags)
        ]

        for pattern in prefix_usage_patterns:
            for match in re.finditer(pattern, xsd_content):
                prefix = match.group(1)
                if prefix and prefix != 'xs':  # Exclude XML Schema namespace
                    used_prefixes.add(prefix)

        logger.debug(f"Found used namespace prefixes: {used_prefixes}")
        return used_prefixes

    def _resolve_transitive_dependencies(self, required_files: Set[str], niem_base_path: Path) -> Set[str]:
        """
        Recursively resolve transitive dependencies by analyzing imports in required NIEM schemas.

        Args:
            required_files: Set of initially required NIEM schema files
            niem_base_path: Path to NIEM schema base directory

        Returns:
            Set of all required files including transitive dependencies
        """
        namespace_mapping = self._build_namespace_to_file_mapping()

        all_required = set(required_files)
        to_process = set(required_files)
        processed = set()

        while to_process:
            current_file = to_process.pop()
            if current_file in processed:
                continue

            processed.add(current_file)
            logger.debug(f"Processing transitive dependencies for: {current_file}")

            # Read the NIEM schema file
            schema_file_path = niem_base_path / current_file
            if not schema_file_path.exists():
                logger.warning(f"NIEM schema not found for transitive analysis: {schema_file_path}")
                continue

            try:
                with open(schema_file_path, 'r', encoding='utf-8') as f:
                    schema_content = f.read()

                # Extract imports from this NIEM schema
                imported_namespaces = self._extract_imported_namespaces(schema_content)

                # Extract namespace declarations and usage
                namespace_prefixes = self._extract_namespace_declarations(schema_content)
                used_prefixes = self._find_used_namespace_prefixes(schema_content)

                logger.debug(f"  Found {len(imported_namespaces)} imports and {len(used_prefixes)} used prefixes in {current_file}")

                # Find additional NIEM dependencies
                for prefix in used_prefixes:
                    if prefix in namespace_prefixes:
                        namespace_uri = namespace_prefixes[prefix]
                        if namespace_uri in namespace_mapping:
                            dep_file = namespace_mapping[namespace_uri]
                            if dep_file not in all_required:
                                logger.info(f"Transitive dependency: {current_file} -> {dep_file}")
                                all_required.add(dep_file)
                                to_process.add(dep_file)

                # Also check explicit imports (include if imported AND namespace prefix is used)
                for namespace_uri in imported_namespaces:
                    if namespace_uri in namespace_mapping:
                        dep_file = namespace_mapping[namespace_uri]
                        if dep_file not in all_required:
                            # Find the prefix for this namespace URI
                            namespace_prefix = None
                            for prefix, uri in namespace_prefixes.items():
                                if uri == namespace_uri:
                                    namespace_prefix = prefix
                                    break

                            # Include if the corresponding prefix is actually used
                            if namespace_prefix and namespace_prefix in used_prefixes:
                                logger.info(f"Transitive import (used): {current_file} -> {dep_file} (prefix: {namespace_prefix})")
                                all_required.add(dep_file)
                                to_process.add(dep_file)
                            else:
                                logger.debug(f"Skipping unused import: {current_file} -> {dep_file} (prefix: {namespace_prefix}, used: {namespace_prefix in used_prefixes if namespace_prefix else 'no prefix'})")

            except Exception as e:
                logger.warning(f"Failed to analyze transitive dependencies for {current_file}: {e}")

        logger.info(f"Transitive analysis: {len(required_files)} direct -> {len(all_required)} total dependencies")
        return all_required

    def resolve_niem_dependencies(self, uploaded_schemas: Dict[str, str], target_dir: Path) -> Set[str]:
        """
        Analyze uploaded schemas to determine which NIEM dependencies are actually used.

        Supports both file-level treeshaking (backward compatible) and element-level
        treeshaking for maximum size reduction.

        Args:
            uploaded_schemas: Dict mapping filename to XSD content for all uploaded files
            target_dir: Directory where NIEM schemas should be copied

        Returns:
            Set of NIEM schema file paths that were copied
        """
        logger.info(f"Analyzing NIEM dependencies for {len(uploaded_schemas)} schemas")

        if self._enable_element_treeshaking and self._element_treeshaker:
            return self._resolve_with_element_treeshaking(uploaded_schemas, target_dir)
        else:
            return self._resolve_with_file_treeshaking(uploaded_schemas, target_dir)

    def _resolve_with_element_treeshaking(self, uploaded_schemas: Dict[str, str], target_dir: Path) -> Set[str]:
        """
        Resolve dependencies using element-level treeshaking for maximum size reduction.

        This method analyzes which specific XML Schema elements are used and generates
        minimal schema files containing only those elements and their dependencies.

        Args:
            uploaded_schemas: Dictionary mapping filename to schema content
            target_dir: Target directory for minimal schemas

        Returns:
            Set of schema file paths that were generated
        """
        logger.info("Using element-level treeshaking for maximum size reduction")

        try:
            # Load all available NIEM schemas
            niem_schemas = self._load_all_niem_schemas()
            logger.info(f"Loaded {len(niem_schemas)} NIEM schemas for element analysis")

            # Perform element-level treeshaking analysis
            treeshaking_result = self._element_treeshaker.analyze_and_treeshake(
                uploaded_schemas=uploaded_schemas,
                niem_schemas=niem_schemas,
                niem_base_path=self._local_xsd_path
            )

            # Extract results
            minimal_schemas = treeshaking_result['minimal_schemas']
            statistics = treeshaking_result['statistics']

            # Log reduction statistics
            logger.info(f"Element-level treeshaking completed:")
            logger.info(f"  Processing time: {statistics['processing_time_seconds']:.2f}s")
            logger.info(f"  Original elements: {statistics['original_element_count']}")
            logger.info(f"  Required elements: {statistics['required_element_count']}")
            logger.info(f"  Element reduction: {statistics['element_reduction_percent']:.1f}%")
            logger.info(f"  Schemas generated: {len(minimal_schemas)}")

            # Write minimal schemas to target directory
            copied_files = set()
            niem_target_dir = target_dir / "niem"

            for schema_path, minimal_content in minimal_schemas.items():
                target_file = niem_target_dir / schema_path
                target_file.parent.mkdir(parents=True, exist_ok=True)

                # Write the minimal schema content
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write(minimal_content)

                copied_files.add(schema_path)
                logger.info(f"Generated minimal schema: {target_file}")

            logger.info(f"Element-level treeshaking generated {len(copied_files)} minimal schemas")
            return copied_files

        except Exception as e:
            logger.error(f"Element-level treeshaking failed: {e}")
            logger.info("Falling back to file-level treeshaking")
            return self._resolve_with_file_treeshaking(uploaded_schemas, target_dir)

    def _resolve_with_file_treeshaking(self, uploaded_schemas: Dict[str, str], target_dir: Path) -> Set[str]:
        """
        Resolve dependencies using file-level treeshaking (original implementation).

        This method performs file-level dependency analysis and copies complete
        schema files that are required.

        Args:
            uploaded_schemas: Dictionary mapping filename to schema content
            target_dir: Target directory for schema files

        Returns:
            Set of schema file paths that were copied
        """
        logger.info("Using file-level treeshaking")

        namespace_mapping = self._build_namespace_to_file_mapping()

        # First pass: Find directly used NIEM schemas
        required_niem_files = set()

        for filename, content in uploaded_schemas.items():
            logger.debug(f"Analyzing schema: {filename}")

            # Extract imports from this schema
            imported_namespaces = self._extract_imported_namespaces(content)

            # Extract namespace prefixes and their usage
            namespace_prefixes = self._extract_namespace_declarations(content)
            used_prefixes = self._find_used_namespace_prefixes(content)

            # Determine which NIEM namespaces are actually used
            for prefix in used_prefixes:
                if prefix in namespace_prefixes:
                    namespace_uri = namespace_prefixes[prefix]
                    if namespace_uri in namespace_mapping:
                        required_file = namespace_mapping[namespace_uri]
                        required_niem_files.add(required_file)
                        logger.info(f"Schema {filename} uses NIEM namespace {prefix}:{namespace_uri} -> {required_file}")

            # Also include explicitly imported NIEM namespaces
            for namespace_uri in imported_namespaces:
                if namespace_uri in namespace_mapping:
                    required_file = namespace_mapping[namespace_uri]
                    required_niem_files.add(required_file)
                    logger.info(f"Schema {filename} imports NIEM namespace {namespace_uri} -> {required_file}")

        # Second pass: Find transitive dependencies
        niem_base_path = self._local_xsd_path
        if niem_base_path and niem_base_path.exists():
            logger.info(f"Analyzing transitive NIEM dependencies from {len(required_niem_files)} direct dependencies...")
            logger.info(f"Direct dependencies: {sorted(list(required_niem_files))}")
            required_niem_files = self._resolve_transitive_dependencies(required_niem_files, niem_base_path)
            logger.info(f"After transitive analysis: {sorted(list(required_niem_files))}")
        else:
            logger.warning(f"NIEM base path does not exist: {niem_base_path}")

        logger.info(f"File-level treeshaking complete: {len(required_niem_files)} NIEM schemas required out of {len(namespace_mapping)} available")
        logger.info(f"Required NIEM files: {sorted(list(required_niem_files))}")

        # Copy required NIEM files to target directory
        copied_files = set()

        if niem_base_path.exists():
            for required_file in required_niem_files:
                source_file = niem_base_path / required_file
                if source_file.exists():
                    # Create target path with niem/ prefix
                    target_file = target_dir / "niem" / required_file
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                    # Copy the NIEM schema file
                    import shutil
                    shutil.copy2(source_file, target_file)
                    copied_files.add(str(required_file))
                    logger.info(f"Copied NIEM schema: {source_file} -> {target_file}")
                else:
                    logger.warning(f"Required NIEM schema not found: {source_file}")
        else:
            logger.warning(f"NIEM base directory not found: {niem_base_path}")

        logger.info(f"Copied {len(copied_files)} NIEM schema files")
        return copied_files

    def _load_all_niem_schemas(self) -> Dict[str, str]:
        """
        Load all available NIEM schema files for element analysis.

        Returns:
            Dictionary mapping relative path to schema content
        """
        niem_schemas = {}

        if not self._local_xsd_path.exists():
            logger.warning(f"NIEM XSD path does not exist: {self._local_xsd_path}")
            return niem_schemas

        try:
            for xsd_file in self._local_xsd_path.rglob("*.xsd"):
                relative_path = xsd_file.relative_to(self._local_xsd_path)

                try:
                    with open(xsd_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        niem_schemas[str(relative_path)] = content
                except Exception as e:
                    logger.warning(f"Failed to read NIEM schema {xsd_file}: {e}")

            logger.debug(f"Loaded {len(niem_schemas)} NIEM schema files")

        except Exception as e:
            logger.error(f"Failed to load NIEM schemas: {e}")

        return niem_schemas




# Global resolver instance with element-level treeshaking enabled
_resolver = NIEMDependencyResolver(enable_element_treeshaking=True)


def resolve_niem_schema_dependencies(uploaded_schemas: Dict[str, str], target_dir: Path) -> Set[str]:
    """Convenience function to resolve NIEM dependencies and copy required schemas"""
    return _resolver.resolve_niem_dependencies(uploaded_schemas, target_dir)

def get_treeshaking_statistics(required_files: Set[str]) -> Dict:
    """Generate statistics about treeshaking benefits."""
    namespace_mapping = _resolver._build_namespace_to_file_mapping()
    total_files = len(namespace_mapping)
    required_count = len(required_files)
    savings_percent = ((total_files - required_count) / total_files) * 100 if total_files > 0 else 0

    return {
        "total_niem_files": total_files,
        "required_files": required_count,
        "eliminated_files": total_files - required_count,
        "space_savings_percent": round(savings_percent, 1),
        "required_file_list": sorted(list(required_files))
    }