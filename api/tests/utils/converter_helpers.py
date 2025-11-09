"""
Test helper utilities for converter unit tests.

Provides assertion helpers and utility functions for testing
XML/JSON to Graph conversion logic.
"""

from typing import List, Dict, Tuple, Optional, Any


def assert_node_exists(nodes: Dict, label: str, properties: Optional[Dict] = None) -> Dict:
    """
    Assert that a node with the given label exists.

    Args:
        nodes: Dictionary of nodes from converter output
        label: Expected node label (e.g., 'Person', 'nc_Person')
        properties: Optional dict of expected properties

    Returns:
        The matching node for further assertions

    Raises:
        AssertionError: If node doesn't exist or properties don't match
    """
    matching_nodes = [n for nid, n in nodes.items() if label in n[0]]

    assert len(matching_nodes) > 0, f"No node found with label containing '{label}'. Available labels: {[n[0] for n in nodes.values()]}"

    node = matching_nodes[0]

    if properties:
        node_props = node[2]
        for key, expected_value in properties.items():
            assert key in node_props, f"Property '{key}' not found in node. Available: {list(node_props.keys())}"
            assert node_props[key] == expected_value, f"Property '{key}' has value '{node_props[key]}', expected '{expected_value}'"

    return node


def assert_node_count(nodes: Dict, expected_count: int):
    """
    Assert the total number of nodes created.

    Args:
        nodes: Dictionary of nodes from converter output
        expected_count: Expected number of nodes
    """
    actual_count = len(nodes)
    assert actual_count == expected_count, f"Expected {expected_count} nodes, got {actual_count}"


def assert_relationship_exists(
    edges: List,
    rel_type: str,
    from_label: Optional[str] = None,
    to_label: Optional[str] = None,
    properties: Optional[Dict] = None
) -> Tuple:
    """
    Assert that a relationship of the given type exists.

    Args:
        edges: List of edges from converter output
        rel_type: Expected relationship type (e.g., 'CONTAINS', 'REPRESENTS')
        from_label: Optional expected source node label
        to_label: Optional expected target node label
        properties: Optional dict of expected edge properties

    Returns:
        The matching edge for further assertions

    Raises:
        AssertionError: If relationship doesn't exist or properties don't match
    """
    matching_edges = [e for e in edges if e[4] == rel_type]

    assert len(matching_edges) > 0, f"No relationship found with type '{rel_type}'. Available types: {list(set(e[4] for e in edges))}"

    # If from_label or to_label specified, filter further
    if from_label or to_label:
        # Note: edges format is (from_id, from_label, to_id, to_label, rel_type, props)
        if from_label:
            matching_edges = [e for e in matching_edges if from_label in e[1]]
        if to_label:
            matching_edges = [e for e in matching_edges if to_label in e[3]]

        assert len(matching_edges) > 0, f"No {rel_type} relationship found matching labels from='{from_label}' to='{to_label}'"

    edge = matching_edges[0]

    if properties:
        edge_props = edge[5]
        for key, expected_value in properties.items():
            assert key in edge_props, f"Edge property '{key}' not found. Available: {list(edge_props.keys())}"
            assert edge_props[key] == expected_value, f"Edge property '{key}' has value '{edge_props[key]}', expected '{expected_value}'"

    return edge


def assert_property_flattened(node_props: Dict, property_path: str, expected_value: Any):
    """
    Assert that a property was flattened with the correct path and value.

    Args:
        node_props: Node properties dictionary
        property_path: Expected flattened property name (e.g., 'nc_PersonName__nc_PersonGivenName')
        expected_value: Expected property value

    Raises:
        AssertionError: If property doesn't exist or value doesn't match
    """
    assert property_path in node_props, f"Flattened property '{property_path}' not found. Available: {list(node_props.keys())}"
    assert node_props[property_path] == expected_value, f"Property '{property_path}' has value '{node_props[property_path]}', expected '{expected_value}'"


def count_nodes_by_label(nodes: Dict, label: str) -> int:
    """
    Count nodes with a specific label.

    Args:
        nodes: Dictionary of nodes from converter output
        label: Label to count (e.g., 'Person', 'nc_Person')

    Returns:
        Number of nodes with matching label
    """
    return len([n for nid, n in nodes.items() if label in n[0]])


def count_relationships_by_type(edges: List, rel_type: str) -> int:
    """
    Count relationships of a specific type.

    Args:
        edges: List of edges from converter output
        rel_type: Relationship type to count (e.g., 'CONTAINS', 'REPRESENTS')

    Returns:
        Number of relationships with matching type
    """
    return len([e for e in edges if e[4] == rel_type])


def get_node_by_id(nodes: Dict, node_id: str) -> Optional[Tuple]:
    """
    Get node by its ID.

    Args:
        nodes: Dictionary of nodes from converter output
        node_id: Node ID to find

    Returns:
        Node tuple or None if not found
    """
    return nodes.get(node_id)


def get_node_properties(nodes: Dict, label: str) -> Dict:
    """
    Get properties of first node matching label.

    Args:
        nodes: Dictionary of nodes from converter output
        label: Node label to find

    Returns:
        Properties dictionary

    Raises:
        AssertionError: If no matching node found
    """
    matching_nodes = [n for nid, n in nodes.items() if label in n[0]]
    assert len(matching_nodes) > 0, f"No node found with label '{label}'"
    return matching_nodes[0][2]


def assert_no_node_with_label(nodes: Dict, label: str):
    """
    Assert that NO node with the given label exists.

    Args:
        nodes: Dictionary of nodes from converter output
        label: Label that should NOT exist

    Raises:
        AssertionError: If node with label exists
    """
    matching_nodes = [n for nid, n in nodes.items() if label in n[0]]
    assert len(matching_nodes) == 0, f"Found unexpected node with label '{label}': {matching_nodes}"


def assert_augmentation_flag(node_props: Dict, property_name: str):
    """
    Assert that a property has the isAugmentation flag set.

    Args:
        node_props: Node properties dictionary
        property_name: Property name to check

    Raises:
        AssertionError: If augmentation flag not set
    """
    aug_flag_key = f"{property_name}_isAugmentation"
    assert aug_flag_key in node_props, f"Augmentation flag '{aug_flag_key}' not found"
    assert node_props[aug_flag_key] is True, f"Augmentation flag '{aug_flag_key}' is not True"


def extract_node_ids(nodes: Dict) -> List[str]:
    """
    Extract all node IDs from converter output.

    Args:
        nodes: Dictionary of nodes from converter output

    Returns:
        List of node IDs
    """
    return list(nodes.keys())


def find_edges_between(edges: List, from_id: str, to_id: str) -> List[Tuple]:
    """
    Find all edges between two specific nodes.

    Args:
        edges: List of edges from converter output
        from_id: Source node ID
        to_id: Target node ID

    Returns:
        List of matching edges
    """
    return [e for e in edges if e[0] == from_id and e[2] == to_id]
