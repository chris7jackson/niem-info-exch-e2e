#!/usr/bin/env python3

from typing import Any

import factory

from niem_api.models.models import NiemNdrReport, NiemNdrViolation, ResetRequest, SchemaResponse


class NiemNdrViolationFactory(factory.Factory):
    """Factory for NIEM NDR violation objects"""

    class Meta:
        model = NiemNdrViolation

    type = "warning"
    message = factory.Sequence(lambda n: f"Validation warning {n}")
    rule_id = factory.Sequence(lambda n: f"RULE-{n:03d}")
    line_number = factory.Faker('random_int', min=1, max=1000)
    column_number = factory.Faker('random_int', min=1, max=100)
    xpath = factory.Sequence(lambda n: f"//xs:element[{n}]")


class NiemNdrReportFactory(factory.Factory):
    """Factory for NIEM NDR report objects"""

    class Meta:
        model = NiemNdrReport

    status = "pass"
    message = "Schema validation successful"
    conformance_target = "niem-6.0"
    violations = factory.SubFactory(factory.List, [])
    summary = factory.LazyFunction(lambda: {
        "total_violations": 0,
        "error_count": 0,
        "warning_count": 0
    })

    @factory.post_generation
    def create_violations(obj, create, extracted, **kwargs):
        """Create violations if specified"""
        if extracted:
            obj.violations = [
                NiemNdrViolationFactory() for _ in range(extracted)
            ]
            obj.summary = {
                "total_violations": len(obj.violations),
                "error_count": len([v for v in obj.violations if v.type == "error"]),
                "warning_count": len([v for v in obj.violations if v.type == "warning"])
            }


class SchemaResponseFactory(factory.Factory):
    """Factory for schema response objects"""

    class Meta:
        model = SchemaResponse

    schema_id = factory.Sequence(lambda n: f"schema_{n:06d}")
    niem_ndr_report = factory.SubFactory(NiemNdrReportFactory)
    is_active = True


class ResetRequestFactory(factory.Factory):
    """Factory for reset request objects"""

    class Meta:
        model = ResetRequest

    reset_schemas = True
    reset_data = True
    reset_neo4j = False
    confirm_token = None


class TestDataFactories:
    """Collection of test data factories"""

    @staticmethod
    def sample_xsd_content(namespace: str = "http://example.com/test") -> str:
        """Generate sample XSD content"""
        return f'''<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                   targetNamespace="{namespace}"
                   xmlns:tns="{namespace}"
                   elementFormDefault="qualified">

            <xs:element name="TestDocument" type="tns:TestDocumentType"/>

            <xs:complexType name="TestDocumentType">
                <xs:sequence>
                    <xs:element name="ID" type="xs:string"/>
                    <xs:element name="Title" type="xs:string"/>
                    <xs:element name="CreatedDate" type="xs:date"/>
                    <xs:element name="Person" type="tns:PersonType" minOccurs="0" maxOccurs="unbounded"/>
                </xs:sequence>
            </xs:complexType>

            <xs:complexType name="PersonType">
                <xs:sequence>
                    <xs:element name="Name" type="xs:string"/>
                    <xs:element name="Age" type="xs:int" minOccurs="0"/>
                    <xs:element name="Email" type="xs:string" minOccurs="0"/>
                </xs:sequence>
                <xs:attribute name="id" type="xs:ID"/>
            </xs:complexType>

        </xs:schema>'''

    @staticmethod
    def sample_cmf_content(namespace: str = "http://example.com/test") -> str:
        """Generate sample CMF content"""
        return f'''<?xml version="1.0" encoding="UTF-8"?>
        <cmf:Model xmlns:cmf="https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/"
                   xmlns:structures="https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/">

            <cmf:Namespace>
                <cmf:NamespaceURI>{namespace}</cmf:NamespaceURI>
                <cmf:NamespacePrefixText>test</cmf:NamespacePrefixText>
            </cmf:Namespace>

            <cmf:Namespace>
                <cmf:NamespaceURI>http://release.niem.gov/niem/niem-core/5.0/</cmf:NamespaceURI>
                <cmf:NamespacePrefixText>nc</cmf:NamespacePrefixText>
            </cmf:Namespace>

            <cmf:Class structures:id="test.PersonType">
                <cmf:Name>PersonType</cmf:Name>
                <cmf:Namespace structures:ref="test"/>
                <cmf:SubClassOf structures:ref="nc.ObjectType"/>
                <cmf:ChildPropertyAssociation>
                    <cmf:ObjectProperty structures:ref="test.PersonName"/>
                    <cmf:MinOccursQuantity>1</cmf:MinOccursQuantity>
                    <cmf:MaxOccursQuantity>1</cmf:MaxOccursQuantity>
                </cmf:ChildPropertyAssociation>
            </cmf:Class>

            <cmf:ObjectProperty structures:id="test.Person">
                <cmf:Class structures:ref="test.PersonType"/>
            </cmf:ObjectProperty>

        </cmf:Model>'''

    @staticmethod
    def sample_mapping_yaml() -> dict[str, Any]:
        """Generate sample mapping YAML structure"""
        return {
            "namespaces": {
                "test": "http://example.com/test",
                "nc": "http://release.niem.gov/niem/niem-core/5.0/"
            },
            "objects": [
                {
                    "qname": "test:Person",
                    "label": "test_Person",
                    "carries_structures_id": True,
                    "scalar_props": []
                }
            ],
            "associations": [],
            "references": [],
            "augmentations": [],
            "polymorphism": {
                "strategy": "extraLabel",
                "store_actual_type_property": "xsiType"
            }
        }

    @staticmethod
    def sample_json_schema() -> dict[str, Any]:
        """Generate sample JSON Schema"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": "Test Schema",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Unique identifier"
                },
                "name": {
                    "type": "string",
                    "description": "Person name"
                },
                "age": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 150
                }
            },
            "required": ["id", "name"]
        }

    @staticmethod
    def sample_xml_data() -> str:
        """Generate sample XML data for ingestion"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <TestDocument xmlns="http://example.com/test">
            <ID>DOC-001</ID>
            <Title>Sample Test Document</Title>
            <CreatedDate>2024-01-01</CreatedDate>
            <Person id="person-1">
                <Name>John Doe</Name>
                <Age>30</Age>
                <Email>john.doe@example.com</Email>
            </Person>
            <Person id="person-2">
                <Name>Jane Smith</Name>
                <Age>25</Age>
                <Email>jane.smith@example.com</Email>
            </Person>
        </TestDocument>'''

    @staticmethod
    def sample_json_data() -> dict[str, Any]:
        """Generate sample JSON data for ingestion"""
        return {
            "id": "DOC-002",
            "title": "Sample JSON Document",
            "created_date": "2024-01-02",
            "people": [
                {
                    "id": "person-3",
                    "name": "Bob Johnson",
                    "age": 35,
                    "email": "bob.johnson@example.com"
                },
                {
                    "id": "person-4",
                    "name": "Alice Brown",
                    "age": 28,
                    "email": "alice.brown@example.com"
                }
            ]
        }

    @staticmethod
    def sample_graph_data() -> dict[str, Any]:
        """Generate sample graph data"""
        return {
            "nodes": [
                {
                    "id": 1,
                    "labels": ["Person"],
                    "properties": {
                        "name": "John Doe",
                        "age": 30,
                        "email": "john.doe@example.com"
                    }
                },
                {
                    "id": 2,
                    "labels": ["Person"],
                    "properties": {
                        "name": "Jane Smith",
                        "age": 25,
                        "email": "jane.smith@example.com"
                    }
                },
                {
                    "id": 3,
                    "labels": ["Company"],
                    "properties": {
                        "name": "Acme Corp",
                        "industry": "Technology"
                    }
                }
            ],
            "relationships": [
                {
                    "id": 10,
                    "type": "WORKS_FOR",
                    "start_node_id": 1,
                    "end_node_id": 3,
                    "properties": {
                        "since": "2020-01-01",
                        "position": "Developer"
                    }
                },
                {
                    "id": 11,
                    "type": "KNOWS",
                    "start_node_id": 1,
                    "end_node_id": 2,
                    "properties": {
                        "since": "2019-06-15"
                    }
                }
            ]
        }

    @staticmethod
    def sample_database_stats() -> dict[str, Any]:
        """Generate sample database statistics"""
        return {
            "node_count": 150,
            "relationship_count": 75,
            "labels": ["Person", "Company", "Document"],
            "relationship_types": ["WORKS_FOR", "KNOWS", "CREATED"],
            "node_counts_by_label": {
                "Person": 100,
                "Company": 25,
                "Document": 25
            },
            "relationship_counts_by_type": {
                "WORKS_FOR": 50,
                "KNOWS": 20,
                "CREATED": 5
            }
        }

    @staticmethod
    def invalid_xsd_content() -> str:
        """Generate invalid XSD content for testing error cases"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <!-- Invalid: missing targetNamespace -->
            <xs:element name="InvalidElement" type="NonExistentType"/>
            <!-- Invalid: unclosed element -->
            <xs:complexType name="InvalidType">
                <xs:sequence>
                    <xs:element name="UnclosedElement"
        </xs:schema>'''
