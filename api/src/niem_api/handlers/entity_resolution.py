#!/usr/bin/env python3
"""
Entity resolution handler for mock entity resolution workflows.

This module provides a simple deterministic matching algorithm that identifies
duplicate entities based on name matching, creating ResolvedEntity nodes
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


# ============================================================================
# Internal Helper Functions (Entity Resolution Logic)
# ============================================================================

def _extract_entities_from_neo4j(neo4j_client: Neo4jClient) -> List[Dict]:
    """Extract person entities from Neo4j for resolution.

    Supports multiple entity types:
    - j:CrashDriver (direct connection to PersonName)
    - cb_exchange:TransmittalSubjectChild (nested via RoleOfPerson)

    Supports multiple name formats:
    - PersonGivenName + PersonSurName (CrashDriver)
    - PersonFullName (TransmittalSubjectChild)

    Args:
        neo4j_client: Neo4j client instance

    Returns:
        List of entity dictionaries with properties
    """
    # Query to get both CrashDriver and TransmittalSubjectChild entities
    # Use variable-length path to handle both:
    #   - Direct: CrashDriver -> PersonName (1 hop)
    #   - Nested: TransmittalSubjectChild -> RoleOfPerson -> PersonName (2 hops)
    query = """
    MATCH (entity)-[*1..2]->(pn:nc_PersonName)
    WHERE entity.qname IN ['j:CrashDriver', 'cb_exchange:TransmittalSubjectChild']
    RETURN
        id(entity) as neo4j_id,
        entity.id as entity_id,
        entity.qname as qname,
        entity.sourceDoc as sourceDoc,
        entity._source_file as source_file,
        labels(entity) as labels,
        entity as entity_node,
        pn.nc_PersonFullName as PersonFullName,
        pn.nc_PersonGivenName as PersonGivenName,
        pn.nc_PersonSurName as PersonSurName,
        pn.nc_PersonMiddleName as PersonMiddleName
    """

    # Use query() instead of query_graph() for scalar results
    results = neo4j_client.query(query, {})
    entities = []

    for record in results:
        entity_props = dict(record['entity_node'].items()) if record.get('entity_node') else {}

        # Extract name components - support multiple formats
        full_name = str(record.get('PersonFullName') or '')
        given_name = str(record.get('PersonGivenName') or '')
        surname = str(record.get('PersonSurName') or '')
        middle_name = str(record.get('PersonMiddleName') or '')

        # Get source and entity type info
        source = record.get('sourceDoc') or record.get('source_file') or 'unknown'
        entity_type = record.get('qname') or 'Unknown'

        # Log extraction details for debugging
        if full_name:
            logger.info(
                f"✓ Extracted {entity_type} entity: PersonFullName='{full_name}' "
                f"from {source} (node {record.get('entity_id')})"
            )
        elif given_name and surname:
            logger.info(
                f"✓ Extracted {entity_type} entity: GivenName='{given_name}', SurName='{surname}' "
                f"from {source} (node {record.get('entity_id')})"
            )
        else:
            logger.warning(
                f"✗ Failed to extract name from {entity_type} in {source} (node {record.get('entity_id')}). "
                f"PersonFullName='{full_name}', GivenName='{given_name}', SurName='{surname}'"
            )
            continue  # Skip entities without sufficient name data

        entities.append({
            'neo4j_id': record['neo4j_id'],
            'entity_id': record.get('entity_id'),
            'entity_type': entity_type,
            'qname': record.get('qname'),
            'labels': record.get('labels', []),
            'source': source,
            'properties': {
                **entity_props,
                'PersonFullName': full_name,
                'PersonGivenName': given_name,
                'PersonSurName': surname,
                'PersonMiddleName': middle_name
            }
        })

    logger.info(f"Extracted {len(entities)} entities from Neo4j")
    return entities


def _create_entity_key(entity: Dict) -> str:
    """Create a matching key for entity resolution.

    Supports multiple name formats:
    - PersonFullName (e.g., "Jason Ohlendorf" -> "jason_ohlendorf")
    - PersonGivenName + PersonSurName (e.g., "Peter" + "Wimsey" -> "peter_wimsey")

    In a real system, this would include birth date, SSN, or other identifiers.

    Args:
        entity: Entity dictionary with properties

    Returns:
        Matching key string, or empty string if insufficient data
    """
    props = entity.get('properties', {})

    # Try PersonFullName first (for TransmittalSubjectChild entities)
    full_name = props.get('PersonFullName', '').strip().lower()
    if full_name:
        # Normalize: "Jason Ohlendorf" -> "jason_ohlendorf"
        key = full_name.replace(' ', '_')
        return key

    # Fall back to GivenName + SurName (for CrashDriver entities)
    given_name = props.get('PersonGivenName', '').strip().lower()
    surname = props.get('PersonSurName', '').strip().lower()

    if given_name and surname:
        # Create normalized key: "peter" + "wimsey" -> "peter_wimsey"
        key = f"{given_name}_{surname}"
        return key

    # Insufficient data for matching
    return ''


def _group_entities_by_key(entities: List[Dict]) -> Dict[str, List[Dict]]:
    """Group entities by matching key.

    Args:
        entities: List of entity dictionaries

    Returns:
        Dictionary mapping keys to lists of matching entities
    """
    groups: Dict[str, List[Dict]] = {}

    for entity in entities:
        key = _create_entity_key(entity)

        if not key:
            # Skip entities without sufficient matching data
            continue

        if key not in groups:
            groups[key] = []

        groups[key].append(entity)

    # Filter to only groups with duplicates (2+ entities)
    duplicate_groups = {k: v for k, v in groups.items() if len(v) >= 2}

    # Log detailed grouping information
    logger.info(f"Found {len(duplicate_groups)} duplicate entity groups from {len(entities)} total entities")
    for key, group in duplicate_groups.items():
        sources = [e.get('source', 'unknown') for e in group]
        logger.info(f"  Match key '{key}': {len(group)} entities from sources: {sources}")

    return duplicate_groups


def _create_resolved_entity_nodes(
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

        # Use PersonFullName if available (TransmittalSubjectChild format)
        full_name = props.get('PersonFullName', '').strip()

        # Otherwise construct from name parts (CrashDriver format)
        if not full_name:
            given_name = props.get('PersonGivenName', '')
            middle_names = props.get('PersonMiddleName', [])
            surname = props.get('PersonSurName', '')

            # Handle middle names (can be list or string)
            if isinstance(middle_names, list):
                middle_str = ' '.join(str(m) for m in middle_names if m)
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


def _reset_entity_resolution(neo4j_client: Neo4jClient) -> Dict[str, int]:
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


def _get_resolution_status(neo4j_client: Neo4jClient) -> Dict:
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


# ============================================================================
# Public Handler Functions (API Endpoints)
# ============================================================================

def handle_run_entity_resolution() -> Dict:
    """Run mock entity resolution on the current Neo4j graph.

    This is the main orchestration function that:
    1. Extracts entities from Neo4j
    2. Groups entities by matching keys
    3. Creates ResolvedEntity nodes for duplicates
    4. Returns summary statistics

    Returns:
        Dictionary with resolution results and statistics
    """
    logger.info("Starting mock entity resolution")

    try:
        # Get Neo4j client
        neo4j_client = Neo4jClient()

        # Step 1: Extract entities from Neo4j
        logger.info("Extracting entities from Neo4j")
        entities = _extract_entities_from_neo4j(neo4j_client)

        if not entities:
            return {
                'status': 'success',
                'message': 'No entities found in the graph to resolve',
                'entities_extracted': 0,
                'duplicate_groups_found': 0,
                'resolved_entities_created': 0,
                'relationships_created': 0
            }

        # Step 2: Group entities by matching keys
        logger.info("Grouping entities by matching criteria")
        entity_groups = _group_entities_by_key(entities)

        if not entity_groups:
            return {
                'status': 'success',
                'message': 'No duplicate entities found - all entities are unique',
                'entities_extracted': len(entities),
                'duplicate_groups_found': 0,
                'resolved_entities_created': 0,
                'relationships_created': 0
            }

        # Step 3: Create ResolvedEntity nodes and relationships
        logger.info(f"Creating ResolvedEntity nodes for {len(entity_groups)} groups")
        resolved_count, relationship_count = _create_resolved_entity_nodes(
            neo4j_client,
            entity_groups
        )

        # Calculate total entities involved in resolution
        total_resolved_entities = sum(len(group) for group in entity_groups.values())

        logger.info(
            f"Entity resolution completed: {resolved_count} clusters created, "
            f"{total_resolved_entities} entities resolved"
        )

        return {
            'status': 'success',
            'message': f'Successfully resolved {total_resolved_entities} entities into {resolved_count} clusters',
            'entities_extracted': len(entities),
            'duplicate_groups_found': len(entity_groups),
            'resolved_entities_created': resolved_count,
            'relationships_created': relationship_count,
            'entities_resolved': total_resolved_entities
        }

    except Exception as e:
        logger.error(f"Entity resolution failed: {e}", exc_info=True)
        return {
            'status': 'error',
            'message': f'Entity resolution failed: {str(e)}',
            'entities_extracted': 0,
            'duplicate_groups_found': 0,
            'resolved_entities_created': 0,
            'relationships_created': 0
        }


def handle_get_resolution_status() -> Dict:
    """Get current entity resolution statistics.

    Returns:
        Dictionary with resolution status and counts
    """
    try:
        neo4j_client = Neo4jClient()
        status = _get_resolution_status(neo4j_client)

        return {
            'status': 'success',
            **status
        }

    except Exception as e:
        logger.error(f"Failed to get resolution status: {e}", exc_info=True)
        return {
            'status': 'error',
            'message': f'Failed to get resolution status: {str(e)}',
            'resolved_entity_clusters': 0,
            'entities_resolved': 0,
            'is_active': False
        }


def handle_reset_entity_resolution() -> Dict:
    """Reset entity resolution by removing all ResolvedEntity nodes.

    Returns:
        Dictionary with reset results and counts
    """
    logger.info("Resetting entity resolution")

    try:
        neo4j_client = Neo4jClient()
        counts = _reset_entity_resolution(neo4j_client)

        logger.info(
            f"Entity resolution reset: deleted {counts['resolved_entities_deleted']} nodes "
            f"and {counts['relationships_deleted']} relationships"
        )

        return {
            'status': 'success',
            'message': 'Entity resolution reset successfully',
            **counts
        }

    except Exception as e:
        logger.error(f"Failed to reset entity resolution: {e}", exc_info=True)
        return {
            'status': 'error',
            'message': f'Failed to reset entity resolution: {str(e)}',
            'resolved_entities_deleted': 0,
            'relationships_deleted': 0
        }
