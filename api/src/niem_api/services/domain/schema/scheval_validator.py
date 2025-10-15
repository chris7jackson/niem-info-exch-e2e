#!/usr/bin/env python3
"""
NIEM Schematron Validation Service

Business logic for validating XSD/XML files using schematron rules via the scheval tool.
Provides high-level validation operations with structured error reporting including line/column numbers.

This service layer orchestrates schematron validation operations using the scheval_client for execution.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from ....clients.scheval_client import (
    is_scheval_available,
    run_scheval_command,
    parse_scheval_validation_output,
    SchevalError
)

logger = logging.getLogger(__name__)


class SchevalValidator:
    """
    Service for validating XSD/XML files using schematron rules via the scheval tool.

    Provides structured validation results with actionable error messages including
    file, line, and column number information for each validation issue.
    """

    def __init__(self, schematron_rules_path: Optional[str] = None):
        """
        Initialize the scheval validator.

        Args:
            schematron_rules_path: Optional path to directory containing schematron rule files.
                                  If None, defaults to /app/third_party/niem-ndr/src
        """
        if schematron_rules_path is None:
            # Default to NDR schematron rules directory
            schematron_rules_path = Path("/app/third_party/niem-ndr/src")

        self.schematron_rules_path = Path(schematron_rules_path)

        if not self.schematron_rules_path.exists():
            logger.warning(f"Schematron rules directory not found: {self.schematron_rules_path}")
        else:
            logger.info(f"Initialized scheval validator with rules from {self.schematron_rules_path}")

    async def validate_xsd_with_schematron(
        self,
        xsd_content: str,
        schematron_file: str,
        xml_catalog: Optional[str] = None,
        use_compiled_xslt: bool = False
    ) -> Dict:
        """
        Validate XSD content using schematron rules.

        Args:
            xsd_content: XSD file content as string
            schematron_file: Path to schematron rule file (.sch) or compiled XSLT (.xslt/.xsl)
            xml_catalog: Optional path to XML catalog file for resolving imports
            use_compiled_xslt: If True, treat schematron_file as pre-compiled XSLT

        Returns:
            Dict containing:
            - status: 'pass', 'fail', or 'error'
            - message: Human-readable summary
            - errors: List of error dicts with file, line, column, message, severity, rule
            - warnings: List of warning dicts
            - summary: Dict with error/warning counts
            - metadata: Additional validation metadata

        Example return value:
            {
                "status": "fail",
                "message": "Found 2 schematron validation errors",
                "errors": [
                    {
                        "file": "schema.xsd",
                        "line": 42,
                        "column": 15,
                        "message": "Invalid attribute usage",
                        "severity": "error",
                        "rule": "Rule 9-5",
                        "context": None
                    }
                ],
                "warnings": [],
                "summary": {
                    "total_issues": 2,
                    "error_count": 2,
                    "warning_count": 0
                },
                "metadata": {
                    "schematron_file": "niem-ndr-rules.sch",
                    "validation_type": "schematron"
                }
            }
        """
        if not is_scheval_available():
            logger.error("Scheval tool is not available")
            return {
                "status": "error",
                "message": "Scheval tool is not available. Please ensure it is properly installed.",
                "errors": [],
                "warnings": [],
                "summary": {
                    "total_issues": 0,
                    "error_count": 0,
                    "warning_count": 0
                },
                "metadata": {
                    "validation_type": "schematron",
                    "tool_available": False
                }
            }

        try:
            # Create temporary directory for validation
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)

                # Write XSD content to temporary file
                xsd_file = temp_dir_path / "schema.xsd"
                with open(xsd_file, 'w', encoding='utf-8') as f:
                    f.write(xsd_content)

                # Build scheval command
                cmd = []

                # Add schematron/XSLT file flag
                if use_compiled_xslt:
                    cmd.extend(["-x", schematron_file])
                else:
                    cmd.extend(["-s", schematron_file])

                # Add XML catalog if provided
                if xml_catalog:
                    cmd.extend(["-c", xml_catalog])

                # Add input file
                cmd.append(xsd_file.name)

                logger.info(f"Running scheval validation with schematron: {schematron_file}")

                # Run scheval command
                result = run_scheval_command(cmd, timeout=120, working_dir=str(temp_dir_path))

                # Parse validation output
                parsed = parse_scheval_validation_output(
                    result["stdout"],
                    result["stderr"],
                    xsd_file.name
                )

                # Build structured response
                total_issues = len(parsed["errors"]) + len(parsed["warnings"])

                if parsed["has_errors"]:
                    status = "fail"
                    message = f"Found {len(parsed['errors'])} schematron validation error(s)"
                    if parsed["warnings"]:
                        message += f" and {len(parsed['warnings'])} warning(s)"
                elif parsed["warnings"]:
                    status = "pass"
                    message = f"Validation passed with {len(parsed['warnings'])} warning(s)"
                else:
                    status = "pass"
                    message = "No schematron validation issues found"

                return {
                    "status": status,
                    "message": message,
                    "errors": parsed["errors"],
                    "warnings": parsed["warnings"],
                    "summary": {
                        "total_issues": total_issues,
                        "error_count": len(parsed["errors"]),
                        "warning_count": len(parsed["warnings"])
                    },
                    "metadata": {
                        "schematron_file": Path(schematron_file).name,
                        "validation_type": "schematron",
                        "used_compiled_xslt": use_compiled_xslt,
                        "catalog_provided": xml_catalog is not None
                    }
                }

        except SchevalError as e:
            logger.error(f"Scheval validation failed: {e}")
            return {
                "status": "error",
                "message": f"Scheval validation failed: {str(e)}",
                "errors": [],
                "warnings": [],
                "summary": {
                    "total_issues": 0,
                    "error_count": 0,
                    "warning_count": 0
                },
                "metadata": {
                    "validation_type": "schematron",
                    "error": str(e)
                }
            }
        except Exception as e:
            logger.error(f"Unexpected error during schematron validation: {e}")
            return {
                "status": "error",
                "message": f"Unexpected validation error: {str(e)}",
                "errors": [],
                "warnings": [],
                "summary": {
                    "total_issues": 0,
                    "error_count": 0,
                    "warning_count": 0
                },
                "metadata": {
                    "validation_type": "schematron",
                    "error": str(e)
                }
            }

    async def validate_xml_with_schematron(
        self,
        xml_content: str,
        schematron_file: str,
        xml_catalog: Optional[str] = None,
        use_compiled_xslt: bool = False
    ) -> Dict:
        """
        Validate XML content using schematron rules.

        This is similar to validate_xsd_with_schematron but optimized for XML instance documents.

        Args:
            xml_content: XML file content as string
            schematron_file: Path to schematron rule file (.sch) or compiled XSLT (.xslt/.xsl)
            xml_catalog: Optional path to XML catalog file for resolving imports
            use_compiled_xslt: If True, treat schematron_file as pre-compiled XSLT

        Returns:
            Dict containing validation results (same structure as validate_xsd_with_schematron)
        """
        if not is_scheval_available():
            logger.error("Scheval tool is not available")
            return {
                "status": "error",
                "message": "Scheval tool is not available. Please ensure it is properly installed.",
                "errors": [],
                "warnings": [],
                "summary": {
                    "total_issues": 0,
                    "error_count": 0,
                    "warning_count": 0
                },
                "metadata": {
                    "validation_type": "schematron",
                    "tool_available": False
                }
            }

        try:
            # Create temporary directory for validation
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)

                # Write XML content to temporary file
                xml_file = temp_dir_path / "instance.xml"
                with open(xml_file, 'w', encoding='utf-8') as f:
                    f.write(xml_content)

                # Build scheval command
                cmd = []

                # Add schematron/XSLT file flag
                if use_compiled_xslt:
                    cmd.extend(["-x", schematron_file])
                else:
                    cmd.extend(["-s", schematron_file])

                # Add XML catalog if provided
                if xml_catalog:
                    cmd.extend(["-c", xml_catalog])

                # Add input file
                cmd.append(xml_file.name)

                logger.info(f"Running scheval validation on XML with schematron: {schematron_file}")

                # Run scheval command
                result = run_scheval_command(cmd, timeout=120, working_dir=str(temp_dir_path))

                # Parse validation output
                parsed = parse_scheval_validation_output(
                    result["stdout"],
                    result["stderr"],
                    xml_file.name
                )

                # Build structured response
                total_issues = len(parsed["errors"]) + len(parsed["warnings"])

                if parsed["has_errors"]:
                    status = "fail"
                    message = f"Found {len(parsed['errors'])} schematron validation error(s)"
                    if parsed["warnings"]:
                        message += f" and {len(parsed['warnings'])} warning(s)"
                elif parsed["warnings"]:
                    status = "pass"
                    message = f"Validation passed with {len(parsed['warnings'])} warning(s)"
                else:
                    status = "pass"
                    message = "No schematron validation issues found"

                return {
                    "status": status,
                    "message": message,
                    "errors": parsed["errors"],
                    "warnings": parsed["warnings"],
                    "summary": {
                        "total_issues": total_issues,
                        "error_count": len(parsed["errors"]),
                        "warning_count": len(parsed["warnings"])
                    },
                    "metadata": {
                        "schematron_file": Path(schematron_file).name,
                        "validation_type": "schematron",
                        "used_compiled_xslt": use_compiled_xslt,
                        "catalog_provided": xml_catalog is not None
                    }
                }

        except SchevalError as e:
            logger.error(f"Scheval validation failed: {e}")
            return {
                "status": "error",
                "message": f"Scheval validation failed: {str(e)}",
                "errors": [],
                "warnings": [],
                "summary": {
                    "total_issues": 0,
                    "error_count": 0,
                    "warning_count": 0
                },
                "metadata": {
                    "validation_type": "schematron",
                    "error": str(e)
                }
            }
        except Exception as e:
            logger.error(f"Unexpected error during schematron validation: {e}")
            return {
                "status": "error",
                "message": f"Unexpected validation error: {str(e)}",
                "errors": [],
                "warnings": [],
                "summary": {
                    "total_issues": 0,
                    "error_count": 0,
                    "warning_count": 0
                },
                "metadata": {
                    "validation_type": "schematron",
                    "error": str(e)
                }
            }

    def get_available_schematron_files(self) -> List[str]:
        """
        Get list of available schematron rule files.

        Returns:
            List of schematron file paths (relative to schematron_rules_path)
        """
        if not self.schematron_rules_path.exists():
            logger.warning(f"Schematron rules directory not found: {self.schematron_rules_path}")
            return []

        schematron_files = []

        # Find all .sch files in the directory
        for sch_file in self.schematron_rules_path.glob("*.sch"):
            schematron_files.append(str(sch_file))

        # Also check compiled directory for pre-compiled XSLT files
        compiled_dir = self.schematron_rules_path.parent / "sch"
        if compiled_dir.exists():
            for xsl_file in compiled_dir.glob("*.xsl"):
                schematron_files.append(str(xsl_file))

        logger.info(f"Found {len(schematron_files)} schematron rule files")
        return schematron_files


# Convenience functions for easy import
async def validate_xsd_with_schematron(
    xsd_content: str,
    schematron_file: str,
    xml_catalog: Optional[str] = None,
    use_compiled_xslt: bool = False
) -> Dict:
    """
    Convenience function to validate XSD content using schematron rules.

    Args:
        xsd_content: XSD file content as string
        schematron_file: Path to schematron rule file (.sch) or compiled XSLT (.xslt/.xsl)
        xml_catalog: Optional path to XML catalog file for resolving imports
        use_compiled_xslt: If True, treat schematron_file as pre-compiled XSLT

    Returns:
        Dict containing validation results
    """
    validator = SchevalValidator()
    return await validator.validate_xsd_with_schematron(
        xsd_content,
        schematron_file,
        xml_catalog,
        use_compiled_xslt
    )


async def validate_xml_with_schematron(
    xml_content: str,
    schematron_file: str,
    xml_catalog: Optional[str] = None,
    use_compiled_xslt: bool = False
) -> Dict:
    """
    Convenience function to validate XML content using schematron rules.

    Args:
        xml_content: XML file content as string
        schematron_file: Path to schematron rule file (.sch) or compiled XSLT (.xslt/.xsl)
        xml_catalog: Optional path to XML catalog file for resolving imports
        use_compiled_xslt: If True, treat schematron_file as pre-compiled XSLT

    Returns:
        Dict containing validation results
    """
    validator = SchevalValidator()
    return await validator.validate_xml_with_schematron(
        xml_content,
        schematron_file,
        xml_catalog,
        use_compiled_xslt
    )
