#!/usr/bin/env python3

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from niem_api.services.domain.schema.validator import NiemNdrValidator


class TestNiemNdrValidator:
    """Test suite for NIEM NDR validator schema type detection"""

    @pytest.fixture
    def mock_ndr_tools_path(self, tmp_path):
        """Create a mock NDR tools directory structure with pre-compiled XSLTs"""
        ndr_path = tmp_path / "niem-ndr"
        ndr_path.mkdir()

        # Create sch directory with pre-compiled XSLT files
        sch_dir = ndr_path / "sch"
        sch_dir.mkdir()

        # Create mock pre-compiled XSLT files
        (sch_dir / "refTarget-6.0.xsl").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="2.0">\n'
            '</xsl:stylesheet>\n'
        )
        (sch_dir / "extTarget-6.0.xsl").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="2.0">\n'
            '</xsl:stylesheet>\n'
        )
        (sch_dir / "subTarget-6.0.xsl").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="2.0">\n'
            '</xsl:stylesheet>\n'
        )

        # Create pkg/saxon directory for integration tests
        (ndr_path / "pkg" / "saxon").mkdir(parents=True)
        saxon_jar = ndr_path / "pkg" / "saxon" / "saxon9he.jar"
        saxon_jar.touch()

        return ndr_path

    @pytest.fixture
    def reference_schema_xsd(self):
        """Sample reference schema document"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema
  xmlns:xs="http://www.w3.org/2001/XMLSchema"
  xmlns:ct="https://docs.oasis-open.org/niemopen/ns/specification/conformanceTargets/6.0/"
  ct:conformanceTargets="https://docs.oasis-open.org/niemopen/ns/specification/NDR/6.0/#ReferenceSchemaDocument"
  targetNamespace="http://example.com/test">
  <xs:element name="TestElement" type="xs:string"/>
</xs:schema>'''

    @pytest.fixture
    def extension_schema_xsd(self):
        """Sample extension schema document"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema
  xmlns:xs="http://www.w3.org/2001/XMLSchema"
  xmlns:ct="https://docs.oasis-open.org/niemopen/ns/specification/conformanceTargets/6.0/"
  ct:conformanceTargets="https://docs.oasis-open.org/niemopen/ns/specification/NDR/6.0/#ExtensionSchemaDocument"
  targetNamespace="http://example.com/test">
  <xs:element name="TestElement" type="xs:string"/>
</xs:schema>'''

    @pytest.fixture
    def subset_schema_xsd(self):
        """Sample subset schema document"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema
  xmlns:xs="http://www.w3.org/2001/XMLSchema"
  xmlns:ct="https://docs.oasis-open.org/niemopen/ns/specification/conformanceTargets/6.0/"
  ct:conformanceTargets="https://docs.oasis-open.org/niemopen/ns/specification/NDR/6.0/#SubsetSchemaDocument"
  targetNamespace="http://example.com/test">
  <xs:element name="TestElement" type="xs:string"/>
</xs:schema>'''

    @pytest.fixture
    def schema_no_conformance_xsd(self):
        """Sample schema without conformance targets"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema
  xmlns:xs="http://www.w3.org/2001/XMLSchema"
  targetNamespace="http://example.com/test">
  <xs:element name="TestElement" type="xs:string"/>
</xs:schema>'''

    @pytest.fixture
    def schema_multiple_targets_xsd(self):
        """Sample schema with multiple conformance targets"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema
  xmlns:xs="http://www.w3.org/2001/XMLSchema"
  xmlns:ct="https://docs.oasis-open.org/niemopen/ns/specification/conformanceTargets/6.0/"
  ct:conformanceTargets="https://docs.oasis-open.org/niemopen/ns/specification/NDR/6.0/#ExtensionSchemaDocument https://docs.oasis-open.org/niemopen/ns/specification/NDR/6.0/#SubsetSchemaDocument"
  targetNamespace="http://example.com/test">
  <xs:element name="TestElement" type="xs:string"/>
</xs:schema>'''

    def test_detect_schema_type_reference(self, mock_ndr_tools_path, reference_schema_xsd):
        """Test detection of ReferenceSchemaDocument"""
        validator = NiemNdrValidator(ndr_tools_path=str(mock_ndr_tools_path))
        schema_type = validator._detect_schema_type(reference_schema_xsd)
        assert schema_type == 'ref'

    def test_detect_schema_type_extension(self, mock_ndr_tools_path, extension_schema_xsd):
        """Test detection of ExtensionSchemaDocument"""
        validator = NiemNdrValidator(ndr_tools_path=str(mock_ndr_tools_path))
        schema_type = validator._detect_schema_type(extension_schema_xsd)
        assert schema_type == 'ext'

    def test_detect_schema_type_subset(self, mock_ndr_tools_path, subset_schema_xsd):
        """Test detection of SubsetSchemaDocument"""
        validator = NiemNdrValidator(ndr_tools_path=str(mock_ndr_tools_path))
        schema_type = validator._detect_schema_type(subset_schema_xsd)
        assert schema_type == 'sub'

    def test_detect_schema_type_missing_conformance(self, mock_ndr_tools_path, schema_no_conformance_xsd):
        """Test fallback when conformanceTargets attribute is missing"""
        validator = NiemNdrValidator(ndr_tools_path=str(mock_ndr_tools_path))
        schema_type = validator._detect_schema_type(schema_no_conformance_xsd)
        assert schema_type == 'unknown'

    def test_detect_schema_type_multiple_targets_priority(self, mock_ndr_tools_path, schema_multiple_targets_xsd):
        """Test that extension is selected when multiple targets present (ref > ext > sub priority)"""
        validator = NiemNdrValidator(ndr_tools_path=str(mock_ndr_tools_path))
        schema_type = validator._detect_schema_type(schema_multiple_targets_xsd)
        # This schema has both ext and sub, ext should be selected due to priority
        assert schema_type == 'ext'

    def test_detect_schema_type_malformed_xml(self, mock_ndr_tools_path):
        """Test fallback when XML is malformed"""
        malformed_xsd = "This is not valid XML <unclosed>"

        validator = NiemNdrValidator(ndr_tools_path=str(mock_ndr_tools_path))
        schema_type = validator._detect_schema_type(malformed_xsd)
        assert schema_type == 'unknown'

    def test_get_conformance_target_uri(self, mock_ndr_tools_path):
        """Test conformance target URI mapping"""
        validator = NiemNdrValidator(ndr_tools_path=str(mock_ndr_tools_path))

        assert 'ReferenceSchemaDocument' in validator._get_conformance_target_uri('ref')
        assert 'ExtensionSchemaDocument' in validator._get_conformance_target_uri('ext')
        assert 'SubsetSchemaDocument' in validator._get_conformance_target_uri('sub')
        # Unknown types fall back to 'sub' (most lenient)
        assert 'SubsetSchemaDocument' in validator._get_conformance_target_uri('unknown')

    def test_get_rule_count(self, mock_ndr_tools_path):
        """Test rule count mapping for each schema type"""
        validator = NiemNdrValidator(ndr_tools_path=str(mock_ndr_tools_path))

        # Reference should have most rules (all + ref)
        assert validator._get_rule_count('ref') == 154
        # Extension should have fewer
        assert validator._get_rule_count('ext') == 145
        # Subset should have fewer still
        assert validator._get_rule_count('sub') == 144
        # Unknown falls back to subset
        assert validator._get_rule_count('unknown') == 144

