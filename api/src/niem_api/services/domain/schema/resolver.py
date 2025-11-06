#!/usr/bin/env python3

import logging
import re
from pathlib import Path
# Use defusedxml for secure XML parsing (prevents XXE attacks)
from defusedxml import ElementTree as ET

logger = logging.getLogger(__name__)


class SchemaValidator:
    """
    Validates that all schema dependencies exist within uploaded files.

    This validator ensures that all xs:import statements and namespace references
    in uploaded schemas can be resolved to other uploaded files, without fetching
    from external sources.
    """

    def __init__(self):
        pass

    def _extract_schema_imports(self, xsd_content: str) -> set[str]:
        """Extract schemaLocation paths from XSD imports"""
        schema_locations = set()

        try:
            root = ET.fromstring(xsd_content)

            # Find all xs:import elements with schemaLocation
            for elem in root.iter():
                if elem.tag.endswith('}import') or elem.tag == 'import':
                    schema_location = elem.get('schemaLocation')
                    if schema_location:
                        schema_locations.add(schema_location)

        except ET.ParseError as e:
            logger.error(f"Failed to parse XSD for import extraction: {e}")

            # Fallback to regex parsing
            import_pattern = r'schemaLocation\s*=\s*["\']([^"\']+)["\']'
            for match in re.finditer(import_pattern, xsd_content):
                schema_locations.add(match.group(1))

        return schema_locations

    def _extract_imported_namespaces(self, xsd_content: str) -> set[str]:
        """Extract namespace URIs from xs:import elements"""
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

    def _extract_namespace_declarations(self, xsd_content: str) -> dict[str, str]:
        """Extract namespace prefix to URI mappings from schema root element"""
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

    def _find_used_namespace_prefixes(self, xsd_content: str) -> set[str]:
        """Find all namespace prefixes that are actually used in element/type references"""
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

    def validate_uploaded_schemas(self, uploaded_schemas: dict[str, str]) -> dict[str, any]:
        """
        Validate that all dependencies in uploaded schemas can be resolved within the uploaded files.

        Args:
            uploaded_schemas: Dict mapping filename to XSD content for all uploaded files

        Returns:
            Dict with validation results including per-file details
        """
        logger.info(f"Validating dependencies for {len(uploaded_schemas)} uploaded schemas")

        # Build a map of target namespaces to filenames from uploaded schemas
        namespace_to_file = {}
        for filename, content in uploaded_schemas.items():
            try:
                root = ET.fromstring(content)
                target_namespace = root.get('targetNamespace')
                if target_namespace:
                    namespace_to_file[target_namespace] = filename
                    logger.debug(f"Mapped namespace {target_namespace} -> {filename}")
            except ET.ParseError:
                logger.warning(f"Failed to parse {filename} for targetNamespace")

        # Track per-file validation details
        file_details = []
        total_missing_count = 0

        # Validate each uploaded schema
        for filename, content in uploaded_schemas.items():
            logger.debug(f"Validating dependencies in {filename}")

            file_imports = []
            file_namespaces = []

            # Check schemaLocation imports
            schema_imports = self._extract_schema_imports(content)
            imported_namespaces_set = self._extract_imported_namespaces(content)

            for schema_location in schema_imports:
                # Normalize the path (convert backslashes to forward slashes)
                normalized_location = schema_location.replace('\\', '/')
                import_filename = Path(schema_location).name

                # Check if this file exists in uploaded schemas
                found = False

                # First, try exact match with schema location (handles relative paths like niem/domains/justice.xsd)
                if normalized_location in uploaded_schemas:
                    found = True
                # Second, try matching just the basename (backwards compatibility)
                elif import_filename in uploaded_schemas:
                    found = True
                else:
                    # Also check if any uploaded schema path ends with this import path
                    for uploaded_name in uploaded_schemas.keys():
                        normalized_uploaded = uploaded_name.replace('\\', '/')

                        # Check various matching patterns
                        if normalized_uploaded.endswith(normalized_location):
                            found = True
                            break
                        elif normalized_uploaded.endswith(import_filename):
                            found = True
                            break

                        # Special handling: If the uploaded path contains .xsd in folder names,
                        # try to match by comparing the final path components
                        # Example: "model.xsd/niem/domains/justice.xsd" should match import "../niem/domains/justice.xsd"
                        if '.xsd/' in normalized_uploaded:
                            # Extract the path after any folder containing .xsd
                            # This handles cases like "model.xsd/niem/domains/justice.xsd"
                            parts = normalized_uploaded.split('.xsd/')
                            if len(parts) > 1:
                                # Get everything after the .xsd/ folder
                                path_after_xsd_folder = parts[-1]
                                # Check if this matches our import location
                                if path_after_xsd_folder == normalized_location.lstrip('../'):
                                    found = True
                                    break
                                # Also check if import path ends with this
                                if normalized_location.endswith(path_after_xsd_folder):
                                    found = True
                                    break

                # Get namespace for this import
                import_namespace = ""
                for ns in imported_namespaces_set:
                    # Try to match namespace to this import
                    import_namespace = ns
                    break

                status = 'satisfied' if found else 'missing'
                if not found:
                    total_missing_count += 1

                file_imports.append({
                    'schema_location': schema_location,
                    'namespace': import_namespace,
                    'status': status,
                    'expected_filename': import_filename
                })

                if not found:
                    logger.warning(f"{filename} imports {schema_location} which is not in uploaded files")

            # Check namespace references
            namespace_prefixes = self._extract_namespace_declarations(content)
            used_prefixes = self._find_used_namespace_prefixes(content)

            # Check that used namespace prefixes have corresponding uploaded schemas
            for prefix in used_prefixes:
                if prefix in namespace_prefixes:
                    namespace_uri = namespace_prefixes[prefix]

                    # Skip standard XML/XSD namespaces
                    standard_namespaces = [
                        'http://www.w3.org/2001/XMLSchema',
                        'http://www.w3.org/2001/XMLSchema-instance',
                        'http://www.w3.org/XML/1998/namespace'
                    ]

                    if namespace_uri in standard_namespaces:
                        continue

                    status = 'satisfied' if namespace_uri in namespace_to_file else 'missing'
                    if status == 'missing':
                        total_missing_count += 1

                    file_namespaces.append({
                        'prefix': prefix,
                        'namespace_uri': namespace_uri,
                        'status': status
                    })

                    if status == 'missing':
                        logger.warning(
                            f"{filename} uses prefix {prefix}:{namespace_uri} but no uploaded "
                            f"schema provides this namespace"
                        )

            file_details.append({
                'filename': filename,
                'imports': file_imports,
                'namespaces_used': file_namespaces
            })

        # Determine if validation passed
        validation_passed = total_missing_count == 0

        # Build legacy missing lists for backward compatibility
        missing_imports = []
        missing_namespaces = []
        for file_info in file_details:
            for imp in file_info['imports']:
                if imp['status'] == 'missing':
                    missing_imports.append({
                        'source_file': file_info['filename'],
                        'schema_location': imp['schema_location'],
                        'expected_filename': imp['expected_filename']
                    })
            for ns in file_info['namespaces_used']:
                if ns['status'] == 'missing':
                    missing_namespaces.append({
                        'source_file': file_info['filename'],
                        'prefix': ns['prefix'],
                        'namespace_uri': ns['namespace_uri']
                    })

        result = {
            'valid': validation_passed,
            'total_schemas': len(uploaded_schemas),
            'namespace_mappings': namespace_to_file,
            'missing_imports': missing_imports,
            'missing_namespaces': missing_namespaces,
            'file_details': file_details,
            'total_missing_count': total_missing_count,
            'summary': self._build_validation_summary(missing_imports, missing_namespaces)
        }

        logger.info(f"Validation result: {'PASS' if result['valid'] else 'FAIL'} - {result['summary']}")
        return result

    def _build_validation_summary(self, missing_imports: list, missing_namespaces: list) -> str:
        """Build a human-readable validation summary"""
        if not missing_imports and not missing_namespaces:
            return "All dependencies resolved successfully"

        parts = []
        if missing_imports:
            parts.append(f"{len(missing_imports)} missing schema imports")
        if missing_namespaces:
            parts.append(f"{len(missing_namespaces)} unresolved namespaces")

        return ", ".join(parts)


# Global validator instance
_validator = SchemaValidator()


def validate_schema_dependencies(uploaded_schemas: dict[str, str]) -> dict[str, any]:
    """
    Convenience function to validate that all schema dependencies exist within uploaded files.

    Args:
        uploaded_schemas: Dict mapping filename to XSD content

    Returns:
        Dict with validation results
    """
    return _validator.validate_uploaded_schemas(uploaded_schemas)
