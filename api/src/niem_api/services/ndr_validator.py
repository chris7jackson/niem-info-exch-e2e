#!/usr/bin/env python3

import asyncio
import logging
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class NiemNdrValidator:
    """Python wrapper for NIEM NDR validation tools"""

    def __init__(self, ndr_tools_path: Optional[str] = None):
        """Initialize the validator with path to NDR tools"""
        if ndr_tools_path is None:
            # Default to the mounted third_party directory
            ndr_tools_path = Path("/app/third_party/niem-ndr")

        self.ndr_tools_path = Path(ndr_tools_path)
        self.schematron_bin = self.ndr_tools_path / "bin" / "schematron"
        self.validation_xslt_path = None  # Will be set after pre-compilation

        if not self.schematron_bin.exists():
            raise FileNotFoundError(f"NDR schematron tool not found at {self.schematron_bin}")

        # Pre-compile the schematron at initialization
        self._precompile_schematron()

        # Pre-generate instance validation schematron at initialization
        self._pregenerate_instance_schematron()

    def _precompile_schematron(self):
        """Pre-compile the schematron into validation XSLT for reuse"""
        try:
            # Create persistent directory for compiled XSLT in /tmp (writable)
            compiled_dir = Path("/tmp/compiled_xslt")
            compiled_dir.mkdir(exist_ok=True)

            # Path for the final validation XSLT
            validation_xslt_file = compiled_dir / "niem_ndr_validation.xsl"

            # If already compiled, reuse it
            if validation_xslt_file.exists():
                logger.info(f"Using existing pre-compiled NIEM NDR validation XSLT: {validation_xslt_file}")
                self.validation_xslt_path = validation_xslt_file
                return

            logger.info("Pre-compiling NIEM NDR schematron for optimal performance...")

            # Saxon and schematron paths
            saxon_jar = self.ndr_tools_path / "pkg" / "saxon" / "saxon9he.jar"
            if not saxon_jar.exists():
                raise FileNotFoundError(f"Saxon JAR not found: {saxon_jar}")

            schematron_file = self.ndr_tools_path / "all-complete.sch"
            if not schematron_file.exists():
                raise FileNotFoundError(f"Comprehensive schematron file not found: {schematron_file}")

            # ISO schematron XSLT files
            iso_dir = self.ndr_tools_path / "pkg" / "iso-schematron-xslt2"
            include_xsl = iso_dir / "iso_dsdl_include.xsl"
            abstract_xsl = iso_dir / "iso_abstract_expand.xsl"
            svrl_xsl = iso_dir / "iso_svrl_for_xslt2.xsl"

            # Intermediate files
            include_file = compiled_dir / "niem_ndr_include.xml"
            abstract_file = compiled_dir / "niem_ndr_abstract.xml"

            # Step 1: Include processing
            import subprocess
            cmd1 = [
                "java", "-jar", str(saxon_jar),
                f"-o:{include_file}",
                f"-xsl:{include_xsl}",
                str(schematron_file)
            ]

            result1 = subprocess.run(cmd1, capture_output=True, text=True)
            if result1.returncode != 0:
                raise Exception(f"Include processing failed: {result1.stderr}")

            # Step 2: Abstract expansion
            cmd2 = [
                "java", "-jar", str(saxon_jar),
                f"-o:{abstract_file}",
                f"-xsl:{abstract_xsl}",
                str(include_file)
            ]

            result2 = subprocess.run(cmd2, capture_output=True, text=True)
            if result2.returncode != 0:
                raise Exception(f"Abstract expansion failed: {result2.stderr}")

            # Step 3: Generate SVRL XSLT (final validation XSLT)
            cmd3 = [
                "java", "-jar", str(saxon_jar),
                f"-o:{validation_xslt_file}",
                f"-xsl:{svrl_xsl}",
                str(abstract_file),
                "allow-foreign=true",
                "full-path-notation=4"
            ]

            result3 = subprocess.run(cmd3, capture_output=True, text=True)
            if result3.returncode != 0:
                raise Exception(f"SVRL XSLT generation failed: {result3.stderr}")

            # Copy required source files to the compiled directory for includes
            src_dir = compiled_dir / "src"
            src_dir.mkdir(exist_ok=True)

            # Copy ndr-functions.xsl and other required files
            ndr_src_dir = self.ndr_tools_path / "src"
            if ndr_src_dir.exists():
                import shutil
                # Copy specific required files
                required_files = ["ndr-functions.xsl", "xsltpp.xsl"]
                for filename in required_files:
                    src_file = ndr_src_dir / filename
                    if src_file.exists():
                        shutil.copy2(src_file, src_dir / filename)
                        logger.info(f"Copied {filename} to compiled src directory")
                    else:
                        logger.warning(f"Required file {filename} not found in {ndr_src_dir}")

                # Also copy any other .xsl files that might be needed
                for src_file in ndr_src_dir.iterdir():
                    if src_file.suffix == '.xsl' and src_file.name not in required_files:
                        shutil.copy2(src_file, src_dir / src_file.name)
                        logger.debug(f"Copied additional file {src_file.name} to compiled src directory")

            # Clean up intermediate files
            include_file.unlink(missing_ok=True)
            abstract_file.unlink(missing_ok=True)

            self.validation_xslt_path = validation_xslt_file
            logger.info(f"Successfully pre-compiled NIEM NDR validation XSLT: {validation_xslt_file}")

        except Exception as e:
            logger.error(f"Failed to pre-compile schematron: {e}")
            raise

    def _pregenerate_instance_schematron(self):
        """Pre-generate the base instance validation schematron template at initialization"""
        try:
            # Create persistent directory for instance schematron templates in /tmp (writable)
            instance_sch_dir = Path("/tmp/compiled_xslt/instance_schematrons")
            instance_sch_dir.mkdir(parents=True, exist_ok=True)

            # Path for the base instance schematron template
            self.base_instance_schematron_path = instance_sch_dir / "base_instance_template.sch"

            # If already generated, reuse it
            if self.base_instance_schematron_path.exists():
                logger.info(f"Using existing base instance schematron template: {self.base_instance_schematron_path}")
                return

            logger.info("Pre-generating base instance schematron template...")

            # Read the base all-complete.sch template
            base_schematron = self.ndr_tools_path / "all-complete.sch"
            if not base_schematron.exists():
                raise FileNotFoundError(f"Base schematron template not found: {base_schematron}")

            with open(base_schematron, 'r', encoding='utf-8') as f:
                schematron_content = f.read()

            # Create the base instance schematron template with placeholder for schema-specific rules
            instance_schematron = self._create_base_instance_schematron(schematron_content)

            # Write the base instance schematron template
            with open(self.base_instance_schematron_path, 'w', encoding='utf-8') as f:
                f.write(instance_schematron)

            logger.info(f"Successfully pre-generated base instance schematron template: {self.base_instance_schematron_path}")

        except Exception as e:
            logger.error(f"Failed to pre-generate instance schematron: {e}")
            # Set fallback path
            self.base_instance_schematron_path = self.ndr_tools_path / "all-complete.sch"

    def _create_base_instance_schematron(self, base_content: str) -> str:
        """Create base instance schematron template with common instance validation rules"""
        # Add instance-specific validation rules that apply to all schemas
        instance_rules = '''
  <!-- Base instance validation rules for all NIEM schemas -->

  <!-- Check that root element has proper conformance targets -->
  <pattern id="instance-conformance-targets">
    <rule context="/*">
      <assert test="@ct:conformanceTargets">
        Root element must have conformance targets attribute
      </assert>
      <assert test="contains(@ct:conformanceTargets, 'https://docs.oasis-open.org/niemopen/ns/specification/NDR/6.0/#InfoExchangeMessage') or
                    contains(@ct:conformanceTargets, 'https://docs.oasis-open.org/niemopen/ns/specification/NDR/6.0/#InfoExchangePackageDocument')">
        Root element must declare conformance to NIEM instance conformance targets
      </assert>
    </rule>
  </pattern>

  <!-- Validate structure namespace usage -->
  <pattern id="instance-structures">
    <rule context="//*[@structures:id]">
      <assert test="matches(@structures:id, '^[A-Za-z]([A-Za-z0-9\\-_])*$')">
        structures:id must follow NIEM identifier pattern
      </assert>
    </rule>
    <rule context="//*[@structures:ref]">
      <assert test="//*[@structures:id = current()/@structures:ref]">
        structures:ref must reference an element with matching structures:id
      </assert>
    </rule>
  </pattern>

  <!-- Validate that required elements are present -->
  <pattern id="instance-required-elements">
    <rule context="/*">
      <assert test="namespace-uri() != ''">
        Root element must be in a namespace
      </assert>
    </rule>
  </pattern>

  <!-- SCHEMA_SPECIFIC_RULES_PLACEHOLDER -->

</schema>'''

        # Insert instance rules before the closing </schema> tag
        if '</schema>' in base_content:
            base_content = base_content.replace('</schema>', instance_rules)
        else:
            # If no closing tag found, append the rules
            base_content += instance_rules

        return base_content

    async def validate_xsd_conformance(self, xsd_content: str) -> Dict:
        """
        Validate XSD content against comprehensive NIEM NDR rules

        TODO: Implement schema type detection (ref, ext, sub) and use appropriate
        validation rules based on conformance targets found in the schema

        Args:
            xsd_content: The XSD file content as string

        Returns:
            Dict containing validation results
        """
        try:
            # Create temporary file for XSD content
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xsd', delete=False) as temp_file:
                temp_file.write(xsd_content)
                temp_file_path = temp_file.name

            try:
                # Run NDR validation using extension schematron
                result = await self._run_ndr_validation(temp_file_path)
                return result
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"NDR validation failed: {e}")
            return {
                "status": "error",
                "message": f"NDR validation failed: {str(e)}",
                "conformance_target": "all",
                "violations": [],
                "summary": {
                    "total_violations": 0,
                    "error_count": 1,
                    "warning_count": 0,
                    "info_count": 0
                }
            }


    async def validate_xml_conformance(self, xml_content: str, schema_id: str = None) -> Dict:
        """
        Validate XML content against NIEM NDR rules using general schematron validation only

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
                # Only use the pre-compiled general schema validation
                result = await self._run_ndr_validation(temp_file_path)
                return result
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"XML NDR validation failed: {e}")
            return {
                "status": "error",
                "message": f"XML NDR validation failed: {str(e)}",
                "conformance_target": "general",
                "violations": [],
                "summary": {
                    "total_violations": 0,
                    "error_count": 1,
                    "warning_count": 0,
                    "info_count": 0
                }
            }


    async def _run_ndr_validation(self, file_path: str) -> Dict:
        """Run the actual NDR validation using pre-compiled XSLT"""
        logger.error(f"*** DEBUG: Starting NDR validation for {file_path}")
        try:
            # Verify we have the pre-compiled XSLT
            if not self.validation_xslt_path or not self.validation_xslt_path.exists():
                raise FileNotFoundError(f"Pre-compiled validation XSLT not found: {self.validation_xslt_path}")

            # Get Saxon JAR path
            saxon_jar = self.ndr_tools_path / "pkg" / "saxon" / "saxon9he.jar"
            if not saxon_jar.exists():
                raise FileNotFoundError(f"Saxon JAR not found: {saxon_jar}")

            # Run validation using pre-compiled XSLT (no compilation needed!)
            cmd = [
                "java", "-jar", str(saxon_jar),
                f"-xsl:{self.validation_xslt_path}",
                file_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            # Parse SVRL output (even if return code is non-zero, there might be useful output)
            svrl_output = stdout.decode('utf-8')
            stderr_output = stderr.decode('utf-8')

            # Debug logging to see what we're getting
            logger.error(f"*** DEBUG: SVRL stdout length: {len(svrl_output)}")
            logger.error(f"*** DEBUG: SVRL stderr: {stderr_output}")
            logger.error(f"*** DEBUG: SVRL stdout (first 500 chars): {svrl_output[:500]}")
            logger.error(f"*** DEBUG: Contains failed-assert: {'failed-assert' in svrl_output}")
            logger.error(f"*** DEBUG: Failed assertion count: {svrl_output.count('<svrl:failed-assert')}")

            result = self._parse_svrl_output(svrl_output, stderr_output)
            result["conformance_target"] = "all"  # Using comprehensive all.sch validation

            return result

        except Exception as e:
            logger.error(f"*** DEBUG: Exception in NDR validation: {e}")
            logger.error(f"Failed to run NDR validation: {e}")
            raise

    def _parse_svrl_output(self, svrl_content: str, stderr_content: str) -> Dict:
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
                violation = self._extract_violation_from_element(failed_assert, 'error')
                violations.append(violation)
                summary["error_count"] += 1
                summary["total_violations"] += 1

            for report in root.findall('.//svrl:successful-report', ns):
                violation = self._extract_violation_from_element(report, 'warning')
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

    def _extract_violation_from_element(self, element, violation_type: str) -> Dict:
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

        return {
            "type": violation_type,
            "rule": rule_context or test,
            "message": message or f"Violation at {location}",
            "location": location,
            "test": test
        }

    def get_conformance_target_description(self) -> str:
        """Get description for the comprehensive conformance target"""
        return "Comprehensive NIEM NDR - All applicable schema validation rules"


# Convenience functions for easy import
async def validate_niem_conformance(xsd_content: str) -> Dict:
    """
    Convenience function to validate XSD content against comprehensive NIEM NDR rules

    Args:
        xsd_content: The XSD file content as string

    Returns:
        Dict containing validation results
    """
    validator = NiemNdrValidator()
    return await validator.validate_xsd_conformance(xsd_content)

