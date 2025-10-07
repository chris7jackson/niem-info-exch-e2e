"""XSD Schema Parser for extracting structure for browser visualization."""

import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from pathlib import Path


class XSDParser:
    """Parse XSD files to extract elements, types, and structure for visualization."""

    # XML Schema namespace
    XS_NS = "http://www.w3.org/2001/XMLSchema"

    def __init__(self):
        self.namespaces = {'xs': self.XS_NS}

    def parse_xsd_file(self, file_path: str) -> Dict[str, Any]:
        """Parse an XSD file and extract its structure.

        Args:
            file_path: Path to XSD file

        Returns:
            Dict with schema structure including elements, types, and hierarchy
        """
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Extract target namespace
        target_namespace = root.get('targetNamespace', '')

        # Extract elements, types, and their relationships
        elements = self._extract_elements(root)
        complex_types = self._extract_complex_types(root)
        simple_types = self._extract_simple_types(root)

        return {
            'target_namespace': target_namespace,
            'elements': elements,
            'complex_types': complex_types,
            'simple_types': simple_types,
            'file_name': Path(file_path).name
        }

    def _extract_elements(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract top-level element declarations."""
        elements = []

        for elem in root.findall('.//xs:element', self.namespaces):
            name = elem.get('name')
            if not name:  # Skip references and nested elements
                continue

            type_attr = elem.get('type', '')

            element_info = {
                'name': name,
                'type': type_attr,
                'documentation': self._extract_documentation(elem),
                'min_occurs': elem.get('minOccurs', '1'),
                'max_occurs': elem.get('maxOccurs', '1'),
                'abstract': elem.get('abstract', 'false') == 'true',
                'substitution_group': elem.get('substitutionGroup', None),
                'children': []
            }

            # Check for inline complex type
            inline_complex = elem.find('xs:complexType', self.namespaces)
            if inline_complex:
                element_info['inline_type'] = self._parse_complex_type_content(inline_complex)

            elements.append(element_info)

        return elements

    def _extract_complex_types(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract complex type definitions."""
        complex_types = []

        for ctype in root.findall('.//xs:complexType', self.namespaces):
            name = ctype.get('name')
            if not name:  # Skip inline types (handled in elements)
                continue

            type_info = {
                'name': name,
                'documentation': self._extract_documentation(ctype),
                'abstract': ctype.get('abstract', 'false') == 'true',
                'base_type': None,
                'attributes': [],
                'elements': []
            }

            # Parse content (sequence, choice, complexContent, simpleContent, etc.)
            content = self._parse_complex_type_content(ctype)
            type_info.update(content)

            complex_types.append(type_info)

        return complex_types

    def _extract_simple_types(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract simple type definitions."""
        simple_types = []

        for stype in root.findall('.//xs:simpleType', self.namespaces):
            name = stype.get('name')
            if not name:
                continue

            type_info = {
                'name': name,
                'documentation': self._extract_documentation(stype),
                'base_type': None,
                'restrictions': []
            }

            # Check for restriction
            restriction = stype.find('xs:restriction', self.namespaces)
            if restriction:
                type_info['base_type'] = restriction.get('base', '')

                # Extract restriction facets (pattern, enumeration, etc.)
                for facet in restriction:
                    facet_name = facet.tag.replace(f'{{{self.XS_NS}}}', '')
                    facet_value = facet.get('value', '')
                    type_info['restrictions'].append({
                        'type': facet_name,
                        'value': facet_value
                    })

            simple_types.append(type_info)

        return simple_types

    def _parse_complex_type_content(self, ctype: ET.Element) -> Dict[str, Any]:
        """Parse the content of a complex type (sequence, choice, attributes, etc.)."""
        result = {
            'base_type': None,
            'attributes': [],
            'elements': []
        }

        # Check for extension/restriction (complexContent or simpleContent)
        complex_content = ctype.find('xs:complexContent', self.namespaces)
        simple_content = ctype.find('xs:simpleContent', self.namespaces)

        if complex_content or simple_content:
            content = complex_content if complex_content else simple_content
            extension = content.find('xs:extension', self.namespaces)
            restriction = content.find('xs:restriction', self.namespaces)

            if extension:
                result['base_type'] = extension.get('base', '')
                result['attributes'] = self._extract_attributes(extension)
                result['elements'] = self._extract_sequence_elements(extension)
            elif restriction:
                result['base_type'] = restriction.get('base', '')
                result['attributes'] = self._extract_attributes(restriction)

        # Direct sequence/choice/all
        result['elements'].extend(self._extract_sequence_elements(ctype))
        result['attributes'].extend(self._extract_attributes(ctype))

        return result

    def _extract_sequence_elements(self, parent: ET.Element) -> List[Dict[str, Any]]:
        """Extract elements from sequence, choice, or all groups."""
        elements = []

        for group in parent.findall('.//xs:sequence', self.namespaces):
            elements.extend(self._extract_elements_from_group(group))

        for group in parent.findall('.//xs:choice', self.namespaces):
            elements.extend(self._extract_elements_from_group(group))

        for group in parent.findall('.//xs:all', self.namespaces):
            elements.extend(self._extract_elements_from_group(group))

        return elements

    def _extract_elements_from_group(self, group: ET.Element) -> List[Dict[str, Any]]:
        """Extract elements from a sequence/choice/all group."""
        elements = []

        for elem in group.findall('xs:element', self.namespaces):
            name = elem.get('name') or elem.get('ref', '')
            type_attr = elem.get('type', '')

            elements.append({
                'name': name,
                'type': type_attr,
                'min_occurs': elem.get('minOccurs', '1'),
                'max_occurs': elem.get('maxOccurs', '1'),
                'documentation': self._extract_documentation(elem)
            })

        return elements

    def _extract_attributes(self, parent: ET.Element) -> List[Dict[str, Any]]:
        """Extract attribute declarations."""
        attributes = []

        for attr in parent.findall('.//xs:attribute', self.namespaces):
            name = attr.get('name') or attr.get('ref', '')
            type_attr = attr.get('type', '')
            use = attr.get('use', 'optional')

            attributes.append({
                'name': name,
                'type': type_attr,
                'use': use,
                'documentation': self._extract_documentation(attr)
            })

        return attributes

    def _extract_documentation(self, element: ET.Element) -> Optional[str]:
        """Extract documentation/annotation from an element."""
        annotation = element.find('xs:annotation', self.namespaces)
        if annotation is None:
            return None

        doc = annotation.find('xs:documentation', self.namespaces)
        if doc is not None and doc.text:
            return doc.text.strip()

        return None
