#!/usr/bin/env python3

import asyncio
import logging
import os
import tempfile
# Use defusedxml for secure XML parsing (prevents XXE attacks)
import defusedxml.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)


class NiemNdrValidator:
    """Python wrapper for NIEM NDR validation tools"""

    def __init__(self, ndr_tools_path: str | None = None):
        """Initialize the validator with path to NDR tools and pre-compiled XSLTs"""
        if ndr_tools_path is None:
            # Default to the mounted third_party directory
            ndr_tools_path = Path("/app/third_party/niem-ndr")

        self.ndr_tools_path = Path(ndr_tools_path)
        self.sch_dir = self.ndr_tools_path / "sch"

        # Map to pre-compiled XSLT files (no compilation needed!)
        self.validation_xslt_paths = {
            'ref': self.sch_dir / 'refTarget-6.0.xsl',
            'ext': self.sch_dir / 'extTarget-6.0.xsl',
            'sub': self.sch_dir / 'subTarget-6.0.xsl',
        }

        # Verify all pre-compiled XSLT files exist
        for xslt_path in self.validation_xslt_paths.values():
            if not xslt_path.exists():
                raise FileNotFoundError(f"Pre-compiled XSLT not found: {xslt_path}")

        logger.info(f"Initialized NIEM NDR validator with pre-compiled XSLTs from {self.sch_dir}")

    def _detect_schema_type(self, xsd_content: str) -> str:
        """
        Detect NIEM schema type from ct:conformanceTargets attribute.

        Parses the XSD content to extract the conformanceTargets attribute
        and determines the schema type based on the fragment identifier.

        Args:
            xsd_content: The XSD file content as string

        Returns:
            Schema type: 'ref', 'ext', 'sub', or 'unknown'
        """
        try:
            # Parse the XSD to find conformanceTargets attribute
            root = ET.fromstring(xsd_content.encode('utf-8'))

            # Define namespace for conformance targets
            ct_ns = "https://docs.oasis-open.org/niemopen/ns/specification/conformanceTargets/6.0/"

            # Get conformanceTargets attribute
            conformance_attr = root.get(f"{{{ct_ns}}}conformanceTargets")

            if not conformance_attr:
                logger.warning("No ct:conformanceTargets attribute found in schema, using fallback")
                return "unknown"

            # Parse space-separated conformance target URIs
            targets = conformance_attr.split()

            # Check for schema type fragment identifiers (priority: ref > ext > sub)
            # Reference schemas are most strict, so prioritize them
            for target in targets:
                if "#ReferenceSchemaDocument" in target:
                    logger.info("Detected ReferenceSchemaDocument conformance target")
                    return "ref"

            for target in targets:
                if "#ExtensionSchemaDocument" in target:
                    logger.info("Detected ExtensionSchemaDocument conformance target")
                    return "ext"

            for target in targets:
                if "#SubsetSchemaDocument" in target:
                    logger.info("Detected SubsetSchemaDocument conformance target")
                    return "sub"

            # Found conformanceTargets but no recognized schema type
            logger.warning(f"Unknown conformance targets: {conformance_attr}, using fallback")
            return "unknown"

        except ET.ParseError as e:
            logger.error(f"Failed to parse XSD for schema type detection: {e}")
            return "unknown"
        except Exception as e:
            logger.error(f"Unexpected error during schema type detection: {e}")
            return "unknown"

    def _generate_composite_schematron(self, schema_type: str) -> Path:
        """
        Generate composite schematron file by merging fragments.

        Combines hdr.sch (header + namespaces), all.sch (common rules),
        and type-specific rules (ref.sch/ext.sch/sub.sch) into a single
        schematron file.

        Args:
            schema_type: Schema type ('ref', 'ext', or 'sub')

        Returns:
            Path to generated composite schematron file

        Raises:
            FileNotFoundError: If required schematron fragments are missing
        """
        try:
            # Define source files
            hdr_file = self.ndr_tools_path / "src" / "hdr.sch"
            all_file = self.ndr_tools_path / "src" / "all.sch"
            type_file = self.ndr_tools_path / "src" / f"{schema_type}.sch"

            # Verify all source files exist
            for file_path in [hdr_file, all_file, type_file]:
                if not file_path.exists():
                    raise FileNotFoundError(f"Required schematron fragment not found: {file_path}")

            # Create output directory
            composite_dir = Path("/tmp/compiled_xslt/composite_schematrons")
            composite_dir.mkdir(parents=True, exist_ok=True)

            # Output path
            output_file = composite_dir / f"{schema_type}_composite.sch"

            # If already generated, return it
            if output_file.exists():
                logger.info(f"Using existing composite schematron: {output_file}")
                return output_file

            logger.info(f"Generating composite schematron for schema type '{schema_type}'...")

            # Read header (contains namespaces and xsl:include)
            with open(hdr_file, encoding='utf-8') as f:
                hdr_content = f.read()

            # Read common rules (all schemas)
            with open(all_file, encoding='utf-8') as f:
                all_content = f.read()

            # Read type-specific rules
            with open(type_file, encoding='utf-8') as f:
                type_content = f.read()

            # Build composite schematron
            # hdr.sch has opening tags and namespaces (no closing </schema>)
            # all.sch and type.sch only have <include> statements (no XML structure)
            composite_content = hdr_content.strip()

            # Add comment separating common rules
            composite_content += "\n\n  <!-- Rules applicable to all conforming schema documents -->\n"
            composite_content += all_content.strip()

            # Add comment separating type-specific rules
            type_name_map = {
                'ref': 'reference',
                'ext': 'extension',
                'sub': 'subset'
            }
            composite_content += (
                f"\n\n  <!-- Rules applicable only to {type_name_map[schema_type]} "
                f"schema documents -->\n"
            )
            composite_content += type_content.strip()

            # Close the schema element
            composite_content += "\n\n</schema>\n"

            # Write composite file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(composite_content)

            logger.info(f"Successfully generated composite schematron: {output_file}")
            return output_file

        except Exception as e:
            logger.error(f"Failed to generate composite schematron for type '{schema_type}': {e}")
            raise

    async def validate_xsd_conformance(self, xsd_content: str) -> dict:
        """
        Validate XSD content against type-specific NIEM NDR rules.

        Detects the schema type from ct:conformanceTargets attribute and applies
        the appropriate validation rules (ref/ext/sub/fallback).

        Args:
            xsd_content: The XSD file content as string

        Returns:
            Dict containing validation results with schema type metadata
        """
        try:
            # Detect schema type before validation
            schema_type = self._detect_schema_type(xsd_content)
            logger.info(f"Detected schema type: {schema_type}")

            # Create temporary file for XSD content
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xsd', delete=False) as temp_file:
                temp_file.write(xsd_content)
                temp_file_path = temp_file.name

            try:
                # Run NDR validation with schema type
                result = await self._run_ndr_validation(temp_file_path, schema_type)
                return result
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"NDR validation failed: {e}")
            return {
                "status": "error",
                "message": f"NDR validation failed: {str(e)}",
                "detected_schema_type": "unknown",
                "conformance_target": "unknown",
                "violations": [],
                "summary": {
                    "total_violations": 0,
                    "error_count": 1,
                    "warning_count": 0,
                    "info_count": 0
                }
            }


    async def validate_xml_conformance(self, xml_content: str, schema_id: str = None) -> dict:
        """
        Validate XML content against NIEM NDR rules using general schematron validation only.

        Note: XML instances don't have conformance targets, so we use the fallback validation.

        Args:
            xml_content: The XML content as string
            schema_id: Ignored - only general NDR validation is performed

        Returns:
            Dict containing validation results
        """
        try:
            # Create temporary file for XML content
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as temp_file:
                temp_file.write(xml_content)
                temp_file_path = temp_file.name

            try:
                # XML instances don't have conformance targets - use subset (most lenient)
                result = await self._run_ndr_validation(temp_file_path, 'sub')
                return result
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"XML NDR validation failed: {e}")
            return {
                "status": "error",
                "message": f"XML NDR validation failed: {str(e)}",
                "detected_schema_type": "unknown",
                "conformance_target": "general",
                "violations": [],
                "summary": {
                    "total_violations": 0,
                    "error_count": 1,
                    "warning_count": 0,
                    "info_count": 0
                }
            }


    async def _run_ndr_validation(self, file_path: str, schema_type: str) -> dict:
        """
        Run the actual NDR validation using pre-compiled type-specific XSLT.

        Args:
            file_path: Path to XSD file to validate
            schema_type: Detected schema type ('ref', 'ext', 'sub', or 'unknown')

        Returns:
            Dict containing validation results with schema type metadata
        """
        logger.info(f"Starting NDR validation for {file_path} with schema type '{schema_type}'")
        try:
            # Handle unknown schema type - fall back to subset (most lenient)
            if schema_type not in self.validation_xslt_paths:
                logger.warning(f"Unknown schema type '{schema_type}', defaulting to subset validation")
                schema_type = 'sub'

            # Select appropriate pre-compiled XSLT
            validation_xslt_path = self.validation_xslt_paths[schema_type]
            logger.info(f"Using validation XSLT: {validation_xslt_path}")

            # Get Saxon JAR path
            saxon_jar = self.ndr_tools_path / "pkg" / "saxon" / "saxon9he.jar"
            if not saxon_jar.exists():
                raise FileNotFoundError(f"Saxon JAR not found: {saxon_jar}")

            # Read source file content for snippet extraction
            try:
                with open(file_path, encoding='utf-8') as f:
                    source_content = f.read()
            except Exception as e:
                logger.warning(f"Could not read source file for snippet extraction: {e}")
                source_content = None

            # Run validation using pre-compiled XSLT
            cmd = [
                "java", "-jar", str(saxon_jar),
                f"-xsl:{validation_xslt_path}",
                file_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            # Parse SVRL output (even if return code is non-zero, there might be useful output)
            svrl_output = stdout.decode('utf-8')
            stderr_output = stderr.decode('utf-8')

            # Debug logging
            logger.debug(f"SVRL stdout length: {len(svrl_output)}")
            logger.debug(f"SVRL stderr: {stderr_output}")
            logger.debug(f"Failed assertion count: {svrl_output.count('<svrl:failed-assert')}")

            # Parse SVRL output with source content for snippet extraction
            result = self._parse_svrl_output(svrl_output, stderr_output, source_content)

            # Add schema type metadata
            result["detected_schema_type"] = schema_type
            result["conformance_target"] = self._get_conformance_target_uri(schema_type)
            result["rules_applied"] = self._get_rule_count(schema_type)

            return result

        except Exception as e:
            logger.error(f"Failed to run NDR validation: {e}")
            raise

    def _get_conformance_target_uri(self, schema_type: str) -> str:
        """Get conformance target URI for schema type."""
        target_map = {
            'ref': 'https://docs.oasis-open.org/niemopen/ns/specification/NDR/6.0/#ReferenceSchemaDocument',
            'ext': 'https://docs.oasis-open.org/niemopen/ns/specification/NDR/6.0/#ExtensionSchemaDocument',
            'sub': 'https://docs.oasis-open.org/niemopen/ns/specification/NDR/6.0/#SubsetSchemaDocument',
        }
        # Default to subset if unknown type
        return target_map.get(schema_type, target_map['sub'])

    def _get_rule_count(self, schema_type: str) -> int:
        """Get approximate rule count for schema type."""
        # Based on pre-compiled XSLT files in sch/ directory
        rule_count_map = {
            'ref': 154,  # refTarget-6.0.xsl - most strict
            'ext': 145,  # extTarget-6.0.xsl - moderate
            'sub': 144,  # subTarget-6.0.xsl - most lenient
        }
        # Default to subset rules if unknown type
        return rule_count_map.get(schema_type, 144)

    def _parse_svrl_output(self, svrl_content: str, stderr_content: str, source_content: str | None = None) -> dict:
        """Parse SVRL (Schematron Validation Report Language) output"""
        try:
            violations = []
            summary = {
                "total_violations": 0,
                "error_count": 0,
                "warning_count": 0,
                "info_count": 0
            }

            if stderr_content.strip():
                logger.warning(f"NDR validation stderr: {stderr_content}")

            if not svrl_content.strip():
                return {
                    "status": "pass",
                    "message": "No NIEM NDR violations found",
                    "violations": violations,
                    "summary": summary
                }

            # Parse SVRL XML
            try:
                root = ET.fromstring(svrl_content)
            except ET.ParseError:
                # If not valid XML, treat as text output
                lines = svrl_content.strip().split('\n')
                for line in lines:
                    if line.strip():
                        violations.append({
                            "type": "error",
                            "rule": "unknown",
                            "message": line.strip(),
                            "location": "unknown"
                        })
                        summary["error_count"] += 1
                        summary["total_violations"] += 1

                status = "fail" if violations else "pass"
                return {
                    "status": status,
                    "message": f"Found {len(violations)} NIEM NDR violations",
                    "violations": violations,
                    "summary": summary
                }

            # Parse SVRL namespace
            ns = {'svrl': 'http://purl.oclc.org/dsdl/svrl'}

            # Extract failed assertions and successful reports
            for failed_assert in root.findall('.//svrl:failed-assert', ns):
                violation = self._extract_violation_from_element(failed_assert, 'error', source_content)
                violations.append(violation)
                summary["error_count"] += 1
                summary["total_violations"] += 1

            for report in root.findall('.//svrl:successful-report', ns):
                violation = self._extract_violation_from_element(report, 'warning', source_content)
                violations.append(violation)
                summary["warning_count"] += 1
                summary["total_violations"] += 1

            status = "fail" if violations else "pass"
            message = f"Found {len(violations)} NIEM NDR violations" if violations else "No NIEM NDR violations found"

            return {
                "status": status,
                "message": message,
                "violations": violations,
                "summary": summary
            }

        except Exception as e:
            logger.error(f"Failed to parse SVRL output: {e}")
            return {
                "status": "error",
                "message": f"Failed to parse validation results: {str(e)}",
                "violations": [],
                "summary": {"total_violations": 0, "error_count": 1, "warning_count": 0, "info_count": 0}
            }

    def _extract_source_snippet_from_xpath(self, source_content: str, xpath_location: str) -> dict | None:
        """
        Extract source code snippet based on XPath location from SVRL output.

        Args:
            source_content: The full XML source file content
            xpath_location: XPath expression like "/*[local-name()='schema'][1]/*[local-name()='complexType'][1]"

        Returns:
            Dict with snippet, line_number, or None if extraction fails
        """
        try:
            import re

            # Parse XPath to extract element types and indices
            # Example: /*[local-name()='schema'][1]/*[local-name()='complexType'][2]
            # We want to find: schema -> 2nd complexType child

            # Extract path components
            path_pattern = r"\*\[local-name\(\)='([^']+)'\]\[(\d+)\]"
            matches = re.findall(path_pattern, xpath_location)

            if not matches:
                logger.debug(f"Could not parse XPath location: {xpath_location}")
                return None

            # Split source into lines for line-by-line processing
            lines = source_content.split('\n')

            # Find the target element by walking the XPath
            # Start with the root element (skip schema since it's implicit)
            target_element_name = matches[-1][0] if len(matches) > 1 else matches[0][0]
            target_index = int(matches[-1][1]) if len(matches) > 1 else int(matches[0][1])

            # Find all occurrences of the target element in the source
            element_pattern = f"<(xs:|xsd:)?{target_element_name}[\\s>]"
            occurrences = []

            for line_num, line in enumerate(lines, start=1):
                if re.search(element_pattern, line):
                    occurrences.append(line_num)

            # Get the nth occurrence (XPath indices are 1-based)
            if target_index <= len(occurrences):
                error_line = occurrences[target_index - 1]

                # Extract context window (2 lines before + error line + 2 lines after)
                context_start = max(0, error_line - 3)  # -3 because lines are 0-indexed
                context_end = min(len(lines), error_line + 2)

                # Build snippet with line numbers
                snippet_lines = []
                for i in range(context_start, context_end):
                    line_number = i + 1
                    prefix = "> " if line_number == error_line else "  "
                    snippet_lines.append(f"{prefix}{line_number:3}  {lines[i]}")

                return {
                    "snippet": '\n'.join(snippet_lines),
                    "line_number": error_line
                }
            else:
                logger.debug(f"Could not find occurrence {target_index} of {target_element_name}")
                return None

        except Exception as e:
            logger.debug(f"Failed to extract source snippet: {e}")
            return None

    def _extract_violation_from_element(self, element, violation_type: str, source_content: str | None = None) -> dict:
        """Extract violation details from SVRL element"""
        ns = {'svrl': 'http://purl.oclc.org/dsdl/svrl'}

        # Extract basic information
        test = element.get('test', '')
        location = element.get('location', '')

        # Extract message text
        text_elements = element.findall('.//svrl:text', ns)
        message = ' '.join([elem.text or '' for elem in text_elements]).strip()

        # Extract rule ID if available
        rule_context = element.get('id', '')

        # Build base violation dict
        violation = {
            "type": violation_type,
            "rule": rule_context or test,
            "message": message or f"Violation at {location}",
            "location": location
        }

        # Add source snippet if source content is available
        if source_content and location:
            snippet_data = self._extract_source_snippet_from_xpath(source_content, location)
            if snippet_data:
                violation["source_snippet"] = snippet_data

        return violation

    def get_conformance_target_description(self) -> str:
        """Get description for the comprehensive conformance target"""
        return "Comprehensive NIEM NDR - All applicable schema validation rules"


# Convenience functions for easy import
async def validate_niem_conformance(xsd_content: str) -> dict:
    """
    Convenience function to validate XSD content against comprehensive NIEM NDR rules

    Args:
        xsd_content: The XSD file content as string

    Returns:
        Dict containing validation results
    """
    validator = NiemNdrValidator()
    return await validator.validate_xsd_conformance(xsd_content)

