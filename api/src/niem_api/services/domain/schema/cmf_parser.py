#!/usr/bin/env python3
"""CMF Parser for extracting graph structure from NIEM Common Model Format XML.

This parser is data-driven and NIEM-agnostic - it passes through values from CMF
without validating against hardcoded enums, making it future-proof and flexible.
"""

import logging
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# CMF and structures namespaces
CMF_NS = "https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/"
STRUCT_NS = "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"

NAMESPACES = {
    'cmf': CMF_NS,
    'structures': STRUCT_NS
}


class CMFParseError(Exception):
    """Raised when CMF parsing fails."""
    pass


class CMFParser:
    """Parse NIEM CMF XML into graph structure for visualization."""

    def __init__(self):
        self.namespaces = {}
        self.nodes = []
        self.edges = []
        self.metadata = {}

    def parse(self, cmf_content: str) -> Dict[str, Any]:
        """Parse CMF XML and return graph structure.

        Args:
            cmf_content: CMF XML as string

        Returns:
            Dictionary with keys: nodes, edges, namespaces, metadata

        Raises:
            CMFParseError: If CMF is malformed or invalid
        """
        try:
            root = ET.fromstring(cmf_content)
        except ET.ParseError as e:
            raise CMFParseError(f"Invalid XML: {str(e)}")

        # Validate root element
        if not root.tag.endswith('}Model') and root.tag != 'Model':
            raise CMFParseError(f"Root element is not CMF Model: {root.tag}")

        logger.info("Starting CMF parsing")

        # Phase 1: Parse namespaces
        self.namespaces = self._parse_namespaces(root)
        logger.info(f"Parsed {len(self.namespaces)} namespaces")

        # Phase 2: Parse classes as nodes
        class_nodes = self._parse_classes(root)
        self.nodes.extend(class_nodes)
        logger.info(f"Parsed {len(class_nodes)} classes")

        # Phase 3: Parse properties and create edges
        property_edges = self._parse_properties_and_edges(root)
        self.edges.extend(property_edges)
        logger.info(f"Created {len(property_edges)} property edges")

        # Phase 4: Parse associations
        association_edges = self._parse_associations(root)
        self.edges.extend(association_edges)
        logger.info(f"Created {len(association_edges)} association edges")

        # Phase 5: Parse augmentations
        augmentation_edges = self._parse_augmentations(root)
        self.edges.extend(augmentation_edges)
        logger.info(f"Created {len(augmentation_edges)} augmentation edges")

        # Phase 6: Calculate depth and usage counts
        self.nodes = self._calculate_depth(self.nodes, self.edges)
        self.nodes = self._calculate_usage_counts(self.nodes, self.edges)

        # Build metadata
        self.metadata = {
            'totalNodes': len(self.nodes),
            'totalEdges': len(self.edges),
            'namespaceCount': len(self.namespaces),
            'parseDate': datetime.now(timezone.utc).isoformat(),
            'cmfVersion': '1.0'
        }

        return {
            'nodes': self.nodes,
            'edges': self.edges,
            'namespaces': list(self.namespaces.values()),
            'metadata': self.metadata
        }

    def parse_file(self, cmf_file_path: str) -> Dict[str, Any]:
        """Parse CMF from file path.

        Args:
            cmf_file_path: Path to CMF XML file

        Returns:
            Dictionary with keys: nodes, edges, namespaces, metadata
        """
        with open(cmf_file_path, 'r', encoding='utf-8') as f:
            cmf_content = f.read()
        return self.parse(cmf_content)

    def _parse_namespaces(self, root: ET.Element) -> Dict[str, Dict[str, Any]]:
        """Extract all namespace declarations."""
        namespaces = {}

        for ns_elem in root.findall('.//cmf:Namespace', NAMESPACES):
            ns_id = ns_elem.get(f'{{{STRUCT_NS}}}id')
            if not ns_id:
                continue

            prefix = self._extract_text(ns_elem, './/cmf:NamespacePrefixText')
            uri = self._extract_text(ns_elem, './/cmf:NamespaceURI')
            category = self._extract_text(ns_elem, './/cmf:NamespaceCategoryCode', default='')
            documentation = self._extract_text(ns_elem, './/cmf:DocumentationText')

            # Generate label from prefix or category
            label = self._generate_namespace_label(prefix, category)

            namespace = {
                'id': prefix or ns_id,
                'prefix': prefix or ns_id,
                'uri': uri,
                'category': category,  # Pass through as-is from CMF
                'label': label,
                'documentation': documentation,
                'classCount': 0,  # Updated later
                'propertyCount': 0  # Updated later
            }

            namespaces[ns_id] = namespace

        return namespaces

    def _parse_classes(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract all class definitions as nodes."""
        nodes = []

        for class_elem in root.findall('.//cmf:Class', NAMESPACES):
            class_id = class_elem.get(f'{{{STRUCT_NS}}}id')
            if not class_id:
                continue

            class_name = self._extract_text(class_elem, './/cmf:Name')
            if not class_name:
                continue

            # Find namespace reference
            ns_elem = class_elem.find('.//cmf:Namespace', NAMESPACES)
            if ns_elem is None:
                logger.warning(f"Class {class_id} has no namespace reference")
                continue

            ns_ref = ns_elem.get(f'{{{STRUCT_NS}}}ref')
            namespace = self.namespaces.get(ns_ref)
            if not namespace:
                logger.warning(f"Class {class_id} references unknown namespace {ns_ref}")
                continue

            # Extract properties
            has_properties = class_elem.findall('.//cmf:HasProperty', NAMESPACES)
            property_count = len(has_properties)

            # Check if abstract
            abstract = self._extract_bool(class_elem, './/cmf:AbstractIndicator')

            # Check if augmentable
            augmentable = self._extract_bool(class_elem, './/cmf:AugmentableIndicator')

            # Get base type (for inheritance)
            base_type = None
            extension_elem = class_elem.find('.//cmf:ExtensionOfClass', NAMESPACES)
            if extension_elem is not None:
                base_type = extension_elem.get(f'{{{STRUCT_NS}}}ref')

            node = {
                'id': class_id,
                'label': class_name,
                'namespace': namespace['prefix'],
                'namespaceURI': namespace['uri'],
                'namespaceCategory': namespace['category'],  # Pass through from CMF
                'nodeType': 'class',  # Derived from CMF structure
                'documentation': self._extract_text(class_elem, './/cmf:DefinitionText'),
                'hasChildren': property_count > 0,
                'depth': 0,  # Calculated later
                'metadata': {
                    'abstract': abstract,
                    'baseType': base_type,
                    'augmentable': augmentable,
                    'file': namespace.get('file', ''),
                    'propertyCount': property_count,
                    'usageCount': 0  # Calculated later
                }
            }

            nodes.append(node)
            namespace['classCount'] += 1

        return nodes

    def _parse_properties_and_edges(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract properties and create edges from classes to types."""
        edges = []

        for class_elem in root.findall('.//cmf:Class', NAMESPACES):
            class_id = class_elem.get(f'{{{STRUCT_NS}}}id')
            if not class_id:
                continue

            for has_prop in class_elem.findall('.//cmf:HasProperty', NAMESPACES):
                prop_ref = has_prop.get(f'{{{STRUCT_NS}}}ref')
                if not prop_ref:
                    continue

                # Find property definition
                prop_elem = root.find(f".//cmf:Property[@structures:id='{prop_ref}']", NAMESPACES)
                if prop_elem is None:
                    logger.warning(f"Property {prop_ref} not found")
                    continue

                prop_name = self._extract_text(prop_elem, './/cmf:Name')
                if not prop_name:
                    continue

                # Get property type
                prop_type_elem = prop_elem.find('.//cmf:Class', NAMESPACES)
                if prop_type_elem is None:
                    continue

                prop_type_ref = prop_type_elem.get(f'{{{STRUCT_NS}}}ref')
                if not prop_type_ref:
                    continue

                # Get cardinality
                min_occurs = self._extract_text(has_prop, './/cmf:MinOccursQuantity', default='1')
                max_occurs = self._extract_text(has_prop, './/cmf:MaxOccursQuantity', default='1')
                cardinality = f"[{min_occurs}..{max_occurs}]"

                edge = {
                    'id': f"edge_{class_id}_{prop_ref}",
                    'source': class_id,
                    'target': prop_type_ref,
                    'label': prop_name,
                    'edgeType': 'property',  # Derived from CMF structure
                    'cardinality': cardinality,
                    'documentation': self._extract_text(prop_elem, './/cmf:DefinitionText')
                }

                edges.append(edge)

        return edges

    def _parse_associations(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract association types as edges."""
        edges = []

        for assoc_elem in root.findall('.//cmf:Association', NAMESPACES):
            assoc_id = assoc_elem.get(f'{{{STRUCT_NS}}}id')
            if not assoc_id:
                continue

            assoc_name = self._extract_text(assoc_elem, './/cmf:Name')
            if not assoc_name:
                continue

            # Get source class
            source_elem = assoc_elem.find('.//cmf:SourceClass', NAMESPACES)
            if source_elem is None:
                continue
            source_ref = source_elem.get(f'{{{STRUCT_NS}}}ref')

            # Get target class
            target_elem = assoc_elem.find('.//cmf:TargetClass', NAMESPACES)
            if target_elem is None:
                continue
            target_ref = target_elem.get(f'{{{STRUCT_NS}}}ref')

            if not source_ref or not target_ref:
                continue

            # Get cardinality if available
            min_occurs = self._extract_text(assoc_elem, './/cmf:MinOccursQuantity', default='1')
            max_occurs = self._extract_text(assoc_elem, './/cmf:MaxOccursQuantity', default='unbounded')
            cardinality = f"[{min_occurs}..{max_occurs}]"

            edge = {
                'id': f"assoc_{assoc_id}",
                'source': source_ref,
                'target': target_ref,
                'label': assoc_name,
                'edgeType': 'association',  # Derived from CMF structure
                'cardinality': cardinality,
                'documentation': self._extract_text(assoc_elem, './/cmf:DefinitionText')
            }

            edges.append(edge)

        return edges

    def _parse_augmentations(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract augmentation records as edges."""
        edges = []

        for aug_elem in root.findall('.//cmf:AugmentationRecord', NAMESPACES):
            # Get target class (the class being augmented)
            target_class_elem = aug_elem.find('.//cmf:Class', NAMESPACES)
            if target_class_elem is None:
                continue
            target_class_ref = target_class_elem.get(f'{{{STRUCT_NS}}}ref')

            # Get property being added
            prop_elem = aug_elem.find('.//cmf:DataProperty', NAMESPACES)
            if prop_elem is None:
                prop_elem = aug_elem.find('.//cmf:ObjectProperty', NAMESPACES)
            if prop_elem is None:
                continue

            prop_ref = prop_elem.get(f'{{{STRUCT_NS}}}ref')
            if not prop_ref or not target_class_ref:
                continue

            # Find the property definition to get its type
            prop_def = root.find(f".//cmf:Property[@structures:id='{prop_ref}']", NAMESPACES)
            if prop_def is None:
                continue

            prop_name = self._extract_text(prop_def, './/cmf:Name', default='Augmentation')

            # Get property type
            prop_type_elem = prop_def.find('.//cmf:Class', NAMESPACES)
            if prop_type_elem is None:
                continue
            prop_type_ref = prop_type_elem.get(f'{{{STRUCT_NS}}}ref')

            if not prop_type_ref:
                continue

            # Get cardinality
            min_occurs = self._extract_text(aug_elem, './/cmf:MinOccursQuantity', default='0')
            max_occurs = self._extract_text(aug_elem, './/cmf:MaxOccursQuantity', default='unbounded')
            cardinality = f"[{min_occurs}..{max_occurs}]"

            edge = {
                'id': f"aug_{target_class_ref}_{prop_ref}",
                'source': prop_type_ref,  # Augmentation type
                'target': target_class_ref,  # Augmented class
                'label': prop_name,
                'edgeType': 'augmentation',  # Derived from CMF structure
                'cardinality': cardinality,
                'documentation': f"Augments {target_class_ref} with {prop_name}"
            }

            edges.append(edge)

        return edges

    def _calculate_depth(self, nodes: List[Dict], edges: List[Dict]) -> List[Dict]:
        """Calculate hierarchical depth for each node using BFS."""
        # Build adjacency list
        graph = defaultdict(list)
        for edge in edges:
            if edge['edgeType'] in ['property', 'extends']:
                graph[edge['source']].append(edge['target'])

        # Find root nodes (no incoming edges of type property/extends)
        incoming = set()
        for edge in edges:
            if edge['edgeType'] in ['property', 'extends']:
                incoming.add(edge['target'])

        roots = [node['id'] for node in nodes if node['id'] not in incoming]

        # BFS to calculate depth
        depths = {}
        queue = [(root, 0) for root in roots]

        while queue:
            node_id, depth = queue.pop(0)
            if node_id not in depths or depth < depths[node_id]:
                depths[node_id] = depth
                for child in graph.get(node_id, []):
                    queue.append((child, depth + 1))

        # Update node depths
        for node in nodes:
            node['depth'] = depths.get(node['id'], 0)

        return nodes

    def _calculate_usage_counts(self, nodes: List[Dict], edges: List[Dict]) -> List[Dict]:
        """Calculate how many times each type is referenced."""
        usage = defaultdict(int)
        for edge in edges:
            usage[edge['target']] += 1

        for node in nodes:
            node['metadata']['usageCount'] = usage.get(node['id'], 0)

        return nodes

    def _extract_text(self, element: ET.Element, xpath: str, default: str = '') -> str:
        """Safely extract text from XML element."""
        found = element.find(xpath, NAMESPACES)
        if found is not None and found.text:
            return found.text.strip()
        return default

    def _extract_bool(self, element: ET.Element, xpath: str, default: bool = False) -> bool:
        """Safely extract boolean from XML element."""
        text = self._extract_text(element, xpath)
        if not text:
            return default
        return text.lower() in ('true', '1', 'yes')

    def _generate_namespace_label(self, prefix: str, category: str) -> str:
        """Generate human-readable label from prefix or category."""
        if not prefix:
            return category or 'Unknown'

        # Common NIEM prefix labels (not exhaustive - just common ones)
        common_labels = {
            'nc': 'NIEM Core',
            'j': 'Justice',
            'hs': 'Human Services',
            'em': 'Emergency Management',
            'mo': 'Military Operations',
            'structures': 'Structures'
        }

        return common_labels.get(prefix, prefix.upper())
