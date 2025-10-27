#!/usr/bin/env python3
"""
Mock entity resolution service for demonstration purposes.

This service provides a simple deterministic matching algorithm that identifies
duplicate entities based on name and birth date, creating ResolvedEntity nodes
to show which entities represent the same real-world person.

This is a simplified mock - real Senzing provides much more sophisticated matching
including phonetic matching, fuzzy logic, and machine learning.
"""

import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Tuple

from ..clients.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


def extract_entities_from_neo4j(neo4j_client: Neo4jClient) -> List[Dict]:
    """Extract Person and CrashDriver entities from Neo4j for resolution.

    Extracts entities with connected name and birth date information.

    Args:
        neo4j_client: Neo4j client instance

    Returns:
        List of entity dictionaries with properties
    """
    # Query to get CrashDriver nodes with connected PersonName data
    query = """
    MATCH (d:j_CrashDriver)-[:HAS_PERSONNAME]->(pn:nc_PersonName)
    OPTIONAL MATCH (d)-[:HAS_PERSONBIRTHDATE]->(pbd:nc_PersonBirthDate)
    RETURN
        id(d) as neo4j_id,
        d.id as entity_id,
        d.qname as qname,
        labels(d) as labels,
        d as driver_node,
        pn.nc_PersonGivenName as PersonGivenName,
        pn.nc_PersonSurName as PersonSurName,
        pn.nc_PersonMiddleName as PersonMiddleName,
        pbd.id as birth_date_id
    """

    # Use query() instead of query_graph() for scalar results
    results = neo4j_client.query(query, {})
    entities = []

    for record in results:
        driver_props = dict(record['driver_node'].items()) if record.get('driver_node') else {}

        entities.append({
            'neo4j_id': record['neo4j_id'],
            'entity_id': record.get('entity_id'),
            'qname': record.get('qname'),
            'labels': record.get('labels', []),
            'properties': {
                **driver_props,
                'PersonGivenName': record.get('PersonGivenName', ''),
                'PersonSurName': record.get('PersonSurName', ''),
                'PersonMiddleName': record.get('PersonMiddleName', ''),
                'PersonBirthDate': record.get('birth_date_id', '')  # Use birth date node ID as proxy
            }
        })

    logger.info(f"Extracted {len(entities)} entities from Neo4j")
    return entities


def create_entity_key(entity: Dict) -> str:
    """Create a matching key for entity resolution.

    Uses PersonGivenName and PersonSurName to create a deterministic key for matching.
    In a real system, this would include birth date, SSN, or other identifiers.

    Args:
        entity: Entity dictionary with properties

    Returns:
        Matching key string, or empty string if insufficient data
    """
    props = entity.get('properties', {})

    # Extract name components
    given_name = props.get('PersonGivenName', '').strip().lower()
    surname = props.get('PersonSurName', '').strip().lower()

    # Need at least given name and surname for matching
    if not given_name or not surname:
        return ''

    # Create normalized key (using full name for matching)
    key = f"{given_name}_{surname}"
    return key


def group_entities_by_key(entities: List[Dict]) -> Dict[str, List[Dict]]:
    """Group entities by matching key.

    Args:
        entities: List of entity dictionaries

    Returns:
        Dictionary mapping keys to lists of matching entities
    """
    groups: Dict[str, List[Dict]] = {}

    for entity in entities:
        key = create_entity_key(entity)

        if not key:
            # Skip entities without sufficient matching data
            continue

        if key not in groups:
            groups[key] = []

        groups[key].append(entity)

    # Filter to only groups with duplicates (2+ entities)
    duplicate_groups = {k: v for k, v in groups.items() if len(v) >= 2}

    logger.info(f"Found {len(duplicate_groups)} duplicate entity groups")
    return duplicate_groups


def create_resolved_entity_nodes(
    neo4j_client: Neo4jClient,
    entity_groups: Dict[str, List[Dict]]
) -> Tuple[int, int]:
    """Create ResolvedEntity nodes and relationships in Neo4j.

    Args:
        neo4j_client: Neo4j client instance
        entity_groups: Dictionary mapping keys to entity lists

    Returns:
        Tuple of (resolved_entity_count, relationship_count)
    """
    resolved_count = 0
    relationship_count = 0
    timestamp = datetime.utcnow().isoformat()

    for match_key, entities in entity_groups.items():
        # Create unique entity ID
        entity_hash = hashlib.sha256(match_key.encode()).hexdigest()[:12]
        entity_id = f"RE_{entity_hash}"

        # Extract representative name from first entity
        first_entity = entities[0]
        props = first_entity['properties']

        given_name = props.get('PersonGivenName', '')
        middle_names = props.get('PersonMiddleName', [])
        surname = props.get('PersonSurName', '')

        # Handle middle names (can be list or string)
        if isinstance(middle_names, list):
            middle_str = ' '.join(middle_names)
        else:
            middle_str = str(middle_names) if middle_names else ''

        full_name = f"{given_name} {middle_str} {surname}".strip()
        birth_date = props.get('PersonBirthDate', '')

        # Create ResolvedEntity node
        create_node_query = """
        MERGE (re:ResolvedEntity {entity_id: $entity_id})
        SET re.name = $name,
            re.birth_date = $birth_date,
            re.resolved_count = $resolved_count,
            re.resolved_at = $resolved_at,
            re.match_key = $match_key
        RETURN re
        """

        neo4j_client.query_graph(create_node_query, {
            'entity_id': entity_id,
            'name': full_name,
            'birth_date': birth_date,
            'resolved_count': len(entities),
            'resolved_at': timestamp,
            'match_key': match_key
        })

        resolved_count += 1

        # Create RESOLVED_TO relationships from each entity
        for entity in entities:
            create_rel_query = """
            MATCH (n), (re:ResolvedEntity {entity_id: $entity_id})
            WHERE id(n) = $neo4j_id
            MERGE (n)-[r:RESOLVED_TO]->(re)
            SET r.confidence = $confidence,
                r.matched_on = $matched_on,
                r.resolved_at = $resolved_at
            RETURN r
            """

            neo4j_client.query_graph(create_rel_query, {
                'neo4j_id': int(entity['neo4j_id']),
                'entity_id': entity_id,
                'confidence': 0.95,  # Mock high confidence (name-only matching)
                'matched_on': 'given_name+surname',
                'resolved_at': timestamp
            })

            relationship_count += 1

    logger.info(
        f"Created {resolved_count} ResolvedEntity nodes "
        f"with {relationship_count} RESOLVED_TO relationships"
    )

    return resolved_count, relationship_count


def reset_entity_resolution(neo4j_client: Neo4jClient) -> Dict[str, int]:
    """Remove all entity resolution data from Neo4j.

    Args:
        neo4j_client: Neo4j client instance

    Returns:
        Dictionary with counts of deleted nodes and relationships
    """
    # Delete RESOLVED_TO relationships
    delete_rels_query = """
    MATCH ()-[r:RESOLVED_TO]->()
    DELETE r
    RETURN count(r) as count
    """

    rel_result = neo4j_client.query_graph(delete_rels_query, {})
    rel_count = 0
    if rel_result.get('nodes'):
        rel_count = rel_result['nodes'][0].get('properties', {}).get('count', 0)

    # Delete ResolvedEntity nodes
    delete_nodes_query = """
    MATCH (re:ResolvedEntity)
    DELETE re
    RETURN count(re) as count
    """

    node_result = neo4j_client.query_graph(delete_nodes_query, {})
    node_count = 0
    if node_result.get('nodes'):
        node_count = node_result['nodes'][0].get('properties', {}).get('count', 0)

    logger.info(
        f"Reset entity resolution: deleted {node_count} nodes "
        f"and {rel_count} relationships"
    )

    return {
        'resolved_entities_deleted': node_count,
        'relationships_deleted': rel_count
    }


def get_resolution_status(neo4j_client: Neo4jClient) -> Dict:
    """Get current entity resolution statistics.

    Args:
        neo4j_client: Neo4j client instance

    Returns:
        Dictionary with resolution statistics
    """
    # Count ResolvedEntity nodes
    count_query = """
    MATCH (re:ResolvedEntity)
    RETURN count(re) as resolved_entities
    """

    result = neo4j_client.query_graph(count_query, {})
    resolved_count = 0
    if result.get('nodes'):
        resolved_count = result['nodes'][0].get('properties', {}).get('resolved_entities', 0)

    # Count RESOLVED_TO relationships
    rel_count_query = """
    MATCH ()-[r:RESOLVED_TO]->()
    RETURN count(r) as relationships
    """

    rel_result = neo4j_client.query_graph(rel_count_query, {})
    rel_count = 0
    if rel_result.get('nodes'):
        rel_count = rel_result['nodes'][0].get('properties', {}).get('relationships', 0)

    return {
        'resolved_entity_clusters': resolved_count,
        'entities_resolved': rel_count,
        'is_active': resolved_count > 0
    }
