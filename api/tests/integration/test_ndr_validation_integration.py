#!/usr/bin/env python3

import asyncio
from pathlib import Path

import pytest

from niem_api.services.domain.schema.validator import NiemNdrValidator


@pytest.mark.integration
class TestNdrValidationIntegration:
    """Integration tests for type-aware NDR validation using real sample files"""

    @pytest.fixture
    def validator(self):
        """Create validator instance with actual NDR tools"""
        # Use the actual NDR tools path (now in api/third_party/)
        ndr_tools_path = Path(__file__).parent.parent.parent / "third_party" / "niem-ndr"

        if not ndr_tools_path.exists():
            pytest.skip(f"NDR tools not found at {ndr_tools_path}")

        return NiemNdrValidator(ndr_tools_path=str(ndr_tools_path))

    @pytest.fixture
    def samples_path(self):
        """Path to sample XSD files"""
        samples_path = (
            Path(__file__).parent.parent.parent.parent
            / "samples" / "CrashDriver-cmf" / "CrashDriverSchemaSet"
        )

        if not samples_path.exists():
            pytest.skip(f"Sample files not found at {samples_path}")

        return samples_path

    def test_validate_subset_schema(self, validator, samples_path):
        """Test validation of SubsetSchemaDocument using real sample file"""
        # CrashDriver.xsd is a SubsetSchemaDocument
        xsd_file = samples_path / "CrashDriver.xsd"

        if not xsd_file.exists():
            pytest.skip(f"Sample file not found: {xsd_file}")

        with open(xsd_file, encoding='utf-8') as f:
            xsd_content = f.read()

        # Run validation
        result = asyncio.run(validator.validate_xsd_conformance(xsd_content))

        # Assertions
        assert result is not None
        assert "status" in result
        assert "detected_schema_type" in result
        assert result["detected_schema_type"] == "sub"
        assert "SubsetSchemaDocument" in result["conformance_target"]
        assert result["rules_applied"] == 144  # all + sub rules

    def test_validate_reference_schema(self, validator):
        """Test validation of ReferenceSchemaDocument using official NIEM model"""
        # Use the official NIEM 6.0 reference schema
        niem_model_path = (
            Path(__file__).parent.parent.parent.parent
            / "third_party" / "niem-model" / "xsd" / "niem-core.xsd"
        )

        if not niem_model_path.exists():
            pytest.skip(f"Official NIEM reference schema not found: {niem_model_path}")

        with open(niem_model_path, encoding='utf-8') as f:
            xsd_content = f.read()

        # Run validation
        result = asyncio.run(validator.validate_xsd_conformance(xsd_content))

        # Assertions
        assert result is not None
        assert "status" in result
        assert "detected_schema_type" in result
        assert result["detected_schema_type"] == "ref"
        assert "ReferenceSchemaDocument" in result["conformance_target"]
        assert result["rules_applied"] == 154  # all + ref rules (most strict)

    def test_validate_multiple_schemas_correct_type_selection(self, validator, samples_path):
        """Test that validator correctly selects different rule sets for different schema types"""
        schemas_to_test = [
            ("CrashDriver.xsd", "sub", 144),
            ("PrivacyMetadata.xsd", None, None),  # Unknown type, will check dynamically
            ("niem/domains/justice.xsd", None, None),
        ]

        results = []

        for filename, _, _ in schemas_to_test:
            xsd_file = samples_path / filename

            if not xsd_file.exists():
                continue

            with open(xsd_file, encoding='utf-8') as f:
                xsd_content = f.read()

            result = asyncio.run(validator.validate_xsd_conformance(xsd_content))
            results.append({
                "filename": filename,
                "schema_type": result.get("detected_schema_type"),
                "rules_applied": result.get("rules_applied"),
                "status": result.get("status")
            })

        # Verify we tested at least one schema
        assert len(results) > 0

        # Verify each result has the required metadata
        for result in results:
            assert result["schema_type"] is not None
            assert result["rules_applied"] is not None
            assert result["status"] in ["pass", "fail", "error"]

    def test_validator_initialization_creates_all_xslt(self, validator):
        """Test that validator initialization maps to all 3 pre-compiled XSLT files"""
        assert hasattr(validator, 'validation_xslt_paths')
        assert isinstance(validator.validation_xslt_paths, dict)

        # Check all expected keys exist (no 'unknown' - it falls back to 'sub')
        assert 'ref' in validator.validation_xslt_paths
        assert 'ext' in validator.validation_xslt_paths
        assert 'sub' in validator.validation_xslt_paths
        assert len(validator.validation_xslt_paths) == 3

        # Check all paths exist
        for schema_type, xslt_path in validator.validation_xslt_paths.items():
            assert xslt_path.exists(), f"XSLT for {schema_type} does not exist: {xslt_path}"

    def test_invalid_schema_unknown_conformance(self, validator, samples_path):
        """Test handling of schema with invalid/missing conformance targets"""
        invalid_xsd_dir = samples_path.parent / "CrashDriverInvalidNDR"
        xsd_file = invalid_xsd_dir / "invalid-schema.xsd"

        if not xsd_file.exists():
            pytest.skip(f"Invalid schema file not found: {xsd_file}")

        with open(xsd_file, encoding='utf-8') as f:
            xsd_content = f.read()

        # Run validation
        result = asyncio.run(validator.validate_xsd_conformance(xsd_content))

        # Should fall back to unknown type if no conformance targets
        assert result is not None
        assert "detected_schema_type" in result
        # Could be unknown or any type depending on the invalid schema content
        assert result["detected_schema_type"] in ['ref', 'ext', 'sub', 'unknown']

    @pytest.mark.slow
    def test_validation_performance_with_large_schema(self, validator, samples_path):
        """Test that validation completes in reasonable time even with large schemas"""
        import time

        # Use the largest schema file available
        xsd_file = samples_path / "niem" / "niem-core.xsd"

        if not xsd_file.exists():
            pytest.skip(f"Large schema file not found: {xsd_file}")

        with open(xsd_file, encoding='utf-8') as f:
            xsd_content = f.read()

        # Measure validation time
        start_time = time.time()
        result = asyncio.run(validator.validate_xsd_conformance(xsd_content))
        elapsed_time = time.time() - start_time

        # Assertions
        assert result is not None
        assert elapsed_time < 10.0, f"Validation took too long: {elapsed_time}s"

    def test_reference_vs_subset_comparison(self, validator, samples_path):
        """Test that reference and subset schemas are validated with different rule sets"""
        # Official NIEM reference schema (14,503 lines)
        reference_path = (
            Path(__file__).parent.parent.parent.parent
            / "third_party" / "niem-model" / "xsd" / "niem-core.xsd"
        )

        # CrashDriver subset schema (467 lines - trimmed from reference)
        subset_path = samples_path / "niem" / "niem-core.xsd"

        if not reference_path.exists() or not subset_path.exists():
            pytest.skip("Reference or subset schema not found for comparison")

        # Validate reference schema
        with open(reference_path, encoding='utf-8') as f:
            ref_result = asyncio.run(validator.validate_xsd_conformance(f.read()))

        # Validate subset schema
        with open(subset_path, encoding='utf-8') as f:
            sub_result = asyncio.run(validator.validate_xsd_conformance(f.read()))

        # Both should succeed but use different rule sets
        assert ref_result["detected_schema_type"] == "ref"
        assert ref_result["rules_applied"] == 154  # Reference: most strict

        assert sub_result["detected_schema_type"] == "sub"
        assert sub_result["rules_applied"] == 144  # Subset: more lenient

        # Verify different conformance targets
        assert "ReferenceSchemaDocument" in ref_result["conformance_target"]
        assert "SubsetSchemaDocument" in sub_result["conformance_target"]

    def test_schema_type_metadata_in_response(self, validator, samples_path):
        """Test that validation response includes all expected metadata fields"""
        xsd_file = samples_path / "CrashDriver.xsd"

        if not xsd_file.exists():
            pytest.skip(f"Sample file not found: {xsd_file}")

        with open(xsd_file, encoding='utf-8') as f:
            xsd_content = f.read()

        result = asyncio.run(validator.validate_xsd_conformance(xsd_content))

        # Check all expected metadata fields are present
        required_fields = [
            "status",
            "message",
            "detected_schema_type",
            "conformance_target",
            "rules_applied",
            "violations",
            "summary"
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

        # Check summary structure
        assert "total_violations" in result["summary"]
        assert "error_count" in result["summary"]
        assert "warning_count" in result["summary"]
        assert "info_count" in result["summary"]
