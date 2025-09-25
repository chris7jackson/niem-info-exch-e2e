#!/usr/bin/env python3

import logging
import re
import tempfile
import aiohttp
from pathlib import Path
from typing import Dict, Set, List, Optional
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

NIEM_MODEL_BASE_URL = "https://raw.githubusercontent.com/niemopen/niem-model/main/xsd"
NIEM_VERSION = "6.0"

class NIEMDependencyResolver:
    """Resolves NIEM schema dependencies by fetching from GitHub repository"""

    def __init__(self):
        self._cache: Dict[str, str] = {}

    async def resolve_schema_dependencies(self, main_schema_content: str, schema_name: str = "schema.xsd") -> Dict[str, str]:
        """
        Resolve all NIEM dependencies for a schema and return a dict of filename -> content

        Args:
            main_schema_content: The main XSD content
            schema_name: Name for the main schema file

        Returns:
            Dict mapping filenames to their XSD content
        """
        logger.info("Starting NIEM dependency resolution")

        # Start with the main schema
        resolved_schemas = {schema_name: main_schema_content}

        # Find all dependencies recursively
        await self._resolve_dependencies_recursive(main_schema_content, resolved_schemas)

        logger.info(f"Resolved {len(resolved_schemas)} schemas total")
        return resolved_schemas

    async def _resolve_dependencies_recursive(self, xsd_content: str, resolved_schemas: Dict[str, str]):
        """Recursively resolve all schema dependencies"""
        dependencies = self._extract_schema_locations(xsd_content)

        for dep_path in dependencies:
            if self._is_niem_schema(dep_path) and dep_path not in resolved_schemas:
                try:
                    dep_content = await self._fetch_niem_schema(dep_path)
                    resolved_schemas[dep_path] = dep_content

                    # Recursively resolve dependencies of this dependency
                    await self._resolve_dependencies_recursive(dep_content, resolved_schemas)

                except Exception as e:
                    logger.warning(f"Failed to resolve dependency {dep_path}: {e}")

    def _extract_schema_locations(self, xsd_content: str) -> Set[str]:
        """Extract schemaLocation paths from XSD imports"""
        schema_locations = set()

        try:
            # Parse XML to find xs:import elements
            root = ET.fromstring(xsd_content)

            # Find all xs:import elements
            for elem in root.iter():
                if elem.tag.endswith('}import') or elem.tag == 'import':
                    schema_location = elem.get('schemaLocation')
                    if schema_location:
                        schema_locations.add(schema_location)

        except ET.ParseError as e:
            logger.error(f"Failed to parse XSD for dependency extraction: {e}")

            # Fallback to regex parsing
            import_pattern = r'schemaLocation\s*=\s*["\']([^"\']+)["\']'
            for match in re.finditer(import_pattern, xsd_content):
                schema_locations.add(match.group(1))

        return schema_locations

    def _is_niem_schema(self, schema_path: str) -> bool:
        """Check if a schema path refers to a NIEM schema that can be fetched"""
        niem_patterns = [
            'niem/',
            'domains/',
            'utility/',
            'adapters/',
            'codes/',
            'external/',
            'auxiliary/'
        ]
        return any(pattern in schema_path for pattern in niem_patterns)

    async def _fetch_niem_schema(self, schema_path: str) -> str:
        """Fetch NIEM schema content from GitHub repository"""

        # Check cache first
        if schema_path in self._cache:
            logger.debug(f"Using cached schema: {schema_path}")
            return self._cache[schema_path]

        # Convert schema path to GitHub URL
        github_url = self._convert_to_github_url(schema_path)

        logger.info(f"Fetching NIEM schema: {schema_path} from {github_url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(github_url) as response:
                if response.status == 200:
                    content = await response.text()
                    self._cache[schema_path] = content
                    return content
                else:
                    raise Exception(f"Failed to fetch {github_url}: HTTP {response.status}")

    def _convert_to_github_url(self, schema_path: str) -> str:
        """Convert a schema location path to GitHub raw URL"""

        # Remove leading 'niem/' if present since the base URL already includes 'xsd'
        if schema_path.startswith('niem/'):
            relative_path = schema_path[5:]  # Remove 'niem/' prefix
        else:
            relative_path = schema_path

        return f"{NIEM_MODEL_BASE_URL}/{relative_path}"

    def create_temp_schema_directory(self, resolved_schemas: Dict[str, str]) -> Path:
        """Create a temporary directory with all resolved schemas"""
        temp_dir = Path(tempfile.mkdtemp(prefix="niem_schemas_"))

        for filename, content in resolved_schemas.items():
            # Create subdirectories if needed
            file_path = temp_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the schema content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        logger.info(f"Created temporary schema directory: {temp_dir}")
        return temp_dir


# Global resolver instance
_resolver = NIEMDependencyResolver()

async def resolve_niem_dependencies(schema_content: str, schema_name: str = "schema.xsd") -> Dict[str, str]:
    """Convenience function to resolve NIEM dependencies"""
    return await _resolver.resolve_schema_dependencies(schema_content, schema_name)

async def create_resolved_schema_directory(schema_content: str, schema_name: str = "schema.xsd") -> Path:
    """Create a temporary directory with schema and all resolved dependencies"""
    resolved_schemas = await resolve_niem_dependencies(schema_content, schema_name)
    return _resolver.create_temp_schema_directory(resolved_schemas)