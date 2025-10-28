#!/usr/bin/env python3
"""
Entity resolution handler for NIEM graph entities.

This module provides entity resolution capabilities using either:
1. Senzing SDK for advanced ML-based entity resolution (if available)
2. Mock deterministic matching as fallback (simple name matching)

The handler supports dynamic node type selection, allowing users to choose
which entity types to resolve from the Neo4j graph.
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from ..clients.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

# Try to import Senzing integration
SENZING_AVAILABLE = False
try:
    from ..clients.senzing_client import get_senzing_client, SenzingClient
    from ..services.entity_to_senzing import (
        batch_convert_to_senzing,
        senzing_result_to_neo4j_format,
        extract_confidence_from_senzing
    )
    SENZING_AVAILABLE = True
    logger.info("Senzing integration available")
except ImportError:
    logger.info("Senzing integration not available - will use mock resolution")


# ============================================================================
# Internal Helper Functions (Entity Resolution Logic)
# ============================================================================

def _extract_entities_from_neo4j(neo4j_client: Neo4jClient, selected_node_types: List[str]) -> List[Dict]:
    """Extract entities from Neo4j for resolution.

    Supports any entity type with name properties accessible through
    direct or nested relationships to PersonName nodes.

    Args:
        neo4j_client: Neo4j client instance
        selected_node_types: List of qnames to resolve (required)

    Returns:
        List of entity dictionaries with properties
    """
    if not selected_node_types:
        logger.warning("No node types selected for entity resolution")
        return []

    logger.info(f"Extracting entities for resolution: {selected_node_types}")

    # Query to get entities of selected types
    # Use variable-length path to handle both:
    #   - Direct: Entity -> PersonName (1 hop)
    #   - Nested: Entity -> RoleOfPerson -> PersonName (2 hops)
    query = """
    MATCH (entity)-[*1..2]->(pn:nc_PersonName)
    WHERE entity.qname IN $node_types
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
    results = neo4j_client.query(query, {'node_types': selected_node_types})
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

    # Try PersonFullName first (for Child entities from NEICE documents)
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

        # Use PersonFullName if available (Child entity format)
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


def _resolve_entities_with_senzing(neo4j_client: Neo4jClient, entities: List[Dict]) -> Tuple[int, int]:
    """
    Resolve entities using Senzing SDK.

    Args:
        neo4j_client: Neo4j client instance
        entities: List of entity dictionaries to resolve

    Returns:
        Tuple of (resolved_entity_count, relationship_count)
    """
    if not SENZING_AVAILABLE:
        logger.error("Senzing not available but Senzing resolution was called")
        return 0, 0

    # Get or initialize Senzing client
    senzing_client = get_senzing_client()
    if not senzing_client.is_available():
        logger.error("Senzing client not available (license or configuration issue)")
        return 0, 0

    if not senzing_client.initialized:
        if not senzing_client.initialize():
            logger.error("Failed to initialize Senzing client")
            return 0, 0

    try:
        # Convert entities to Senzing format
        senzing_records = batch_convert_to_senzing(entities)

        # Process records through Senzing
        batch_result = senzing_client.process_batch(senzing_records)
        logger.info(f"Processed {batch_result['processed']} records through Senzing")

        # Track resolution results
        resolved_entities = {}
        resolved_count = 0
        relationship_count = 0
        timestamp = datetime.utcnow().isoformat()

        # Get resolution results for each entity
        for entity in entities:
            record_id = str(entity.get('entity_id') or entity.get('neo4j_id', ''))

            # Get Senzing resolution result
            result = senzing_client.get_entity_by_record_id("NIEM_GRAPH", record_id)
            if not result:
                continue

            # Extract Senzing entity ID
            senzing_entity_id = result.get('RESOLVED_ENTITY', {}).get('ENTITY_ID')
            if not senzing_entity_id:
                continue

            # Check if this is a duplicate (multiple records resolved to same entity)
            if senzing_entity_id not in resolved_entities:
                # First time seeing this Senzing entity
                resolved_entities[senzing_entity_id] = {
                    'entities': [],
                    'senzing_data': result.get('RESOLVED_ENTITY', {})
                }

            resolved_entities[senzing_entity_id]['entities'].append(entity)

        # Create ResolvedEntity nodes for groups with duplicates
        for senzing_entity_id, group_data in resolved_entities.items():
            entities_in_group = group_data['entities']
            senzing_data = group_data['senzing_data']

            # Only create resolved entity if there are duplicates
            if len(entities_in_group) < 2:
                continue

            # Create unique entity ID for Neo4j
            entity_hash = hashlib.sha256(str(senzing_entity_id).encode()).hexdigest()[:12]
            neo4j_entity_id = f"SE_{entity_hash}"

            # Extract name from Senzing result
            entity_name = senzing_data.get('ENTITY_NAME', '')
            if not entity_name:
                # Fall back to first entity's name
                first_entity = entities_in_group[0]
                props = first_entity.get('properties', {})
                entity_name = props.get('PersonFullName', '')
                if not entity_name:
                    given = props.get('PersonGivenName', '')
                    surname = props.get('PersonSurName', '')
                    entity_name = f"{given} {surname}".strip()

            # Get match confidence from Senzing
            confidence = extract_confidence_from_senzing({'RESOLVED_ENTITY': senzing_data})

            # Create ResolvedEntity node
            create_node_query = """
            MERGE (re:ResolvedEntity {entity_id: $entity_id})
            SET re.name = $name,
                re.senzing_entity_id = $senzing_entity_id,
                re.resolved_count = $resolved_count,
                re.resolved_at = $resolved_at,
                re.resolution_method = 'senzing',
                re.confidence = $confidence
            RETURN re
            """

            neo4j_client.query_graph(create_node_query, {
                'entity_id': neo4j_entity_id,
                'name': entity_name,
                'senzing_entity_id': senzing_entity_id,
                'resolved_count': len(entities_in_group),
                'resolved_at': timestamp,
                'confidence': confidence
            })

            resolved_count += 1

            # Create RESOLVED_TO relationships
            for entity in entities_in_group:
                create_rel_query = """
                MATCH (n), (re:ResolvedEntity {entity_id: $entity_id})
                WHERE id(n) = $neo4j_id
                MERGE (n)-[r:RESOLVED_TO]->(re)
                SET r.confidence = $confidence,
                    r.resolution_method = 'senzing',
                    r.resolved_at = $resolved_at,
                    r.senzing_entity_id = $senzing_entity_id
                RETURN r
                """

                neo4j_client.query_graph(create_rel_query, {
                    'neo4j_id': int(entity['neo4j_id']),
                    'entity_id': neo4j_entity_id,
                    'confidence': confidence,
                    'resolved_at': timestamp,
                    'senzing_entity_id': senzing_entity_id
                })

                relationship_count += 1

        logger.info(f"Senzing resolution created {resolved_count} resolved entities with {relationship_count} relationships")
        return resolved_count, relationship_count

    except Exception as e:
        logger.error(f"Error during Senzing resolution: {e}", exc_info=True)
        return 0, 0


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


def _get_available_node_types(neo4j_client: Neo4jClient) -> List[Dict]:
    """Get all available node types that can be resolved.

    This function discovers all node types in the graph that have:
    - A qname property (indicating they're NIEM entities)
    - Name properties (either PersonFullName or PersonGivenName/PersonSurName)

    Args:
        neo4j_client: Neo4j client instance

    Returns:
        List of dictionaries containing node type information
    """
    # Query to find all distinct qnames and check if they have name properties
    discovery_query = """
    // Find all distinct qnames in the graph
    MATCH (n)
    WHERE n.qname IS NOT NULL
    WITH DISTINCT n.qname as qname, labels(n)[0] as label

    // Count entities for each qname
    MATCH (entity)
    WHERE entity.qname = qname
    WITH qname, label, count(entity) as count

    // Check if entities of this type have name properties
    // Using OPTIONAL MATCH to check for name properties
    OPTIONAL MATCH (sample)-[*1..2]->(pn:nc_PersonName)
    WHERE sample.qname = qname
    WITH qname, label, count,
         collect(DISTINCT pn.nc_PersonFullName)[0] as sampleFullName,
         collect(DISTINCT pn.nc_PersonGivenName)[0] as sampleGivenName,
         collect(DISTINCT pn.nc_PersonSurName)[0] as sampleSurName

    // Only return types that have name properties
    WHERE sampleFullName IS NOT NULL
       OR (sampleGivenName IS NOT NULL AND sampleSurName IS NOT NULL)

    RETURN qname, label, count,
           CASE
               WHEN sampleFullName IS NOT NULL THEN true
               ELSE false
           END as hasFullName,
           CASE
               WHEN sampleGivenName IS NOT NULL AND sampleSurName IS NOT NULL THEN true
               ELSE false
           END as hasGivenAndSurname,
           sampleFullName,
           sampleGivenName,
           sampleSurName
    ORDER BY count DESC
    """

    results = neo4j_client.query(discovery_query, {})
    node_types = []

    # Try to load configuration for categorization
    try:
        from ..services.entity_to_senzing import load_mapping_config, get_entity_category
        config = load_mapping_config()
        recommended_types = config.get('recommended_types', [])
    except ImportError:
        config = {}
        recommended_types = []

    for record in results:
        # Determine which name fields are available
        name_fields = []
        if record.get('hasFullName'):
            name_fields.append('PersonFullName')
        if record.get('hasGivenAndSurname'):
            name_fields.append('PersonGivenName + PersonSurName')

        qname = record['qname']

        # Determine category and recommendation
        category = 'other'
        recommended = qname in recommended_types

        # Get category from entity_to_senzing service
        try:
            from ..services.entity_to_senzing import get_entity_category
            entity_mock = {'qname': qname}
            category = get_entity_category(entity_mock)
            # Person and Organization are always recommended
            if category in ['person', 'organization']:
                recommended = True
        except:
            pass

        node_type_info = {
            'qname': qname,
            'label': record['label'],
            'count': record['count'],
            'nameFields': name_fields,
            'category': category,
            'recommended': recommended
        }

        node_types.append(node_type_info)

        logger.info(
            f"Found resolvable type: {record['qname']} "
            f"({record['count']} entities, name fields: {', '.join(name_fields)})"
        )

    logger.info(f"Discovered {len(node_types)} resolvable node types")
    return node_types


# ============================================================================
# Public Handler Functions (API Endpoints)
# ============================================================================

def handle_run_entity_resolution(selected_node_types: List[str]) -> Dict:
    """Run entity resolution on the current Neo4j graph.

    This is the main orchestration function that:
    1. Extracts entities from Neo4j for selected node types
    2. Uses Senzing SDK for entity resolution (if available)
    3. Falls back to mock resolution if Senzing unavailable
    4. Creates ResolvedEntity nodes for duplicates
    5. Returns summary statistics

    Args:
        selected_node_types: List of qnames to resolve (required)

    Returns:
        Dictionary with resolution results and statistics
    """
    if not selected_node_types:
        return {
            'status': 'error',
            'message': 'No node types selected for entity resolution',
            'entities_extracted': 0,
            'duplicate_groups_found': 0,
            'resolved_entities_created': 0,
            'relationships_created': 0
        }

    logger.info(f"Starting entity resolution for node types: {selected_node_types}")

    try:
        # Get Neo4j client
        neo4j_client = Neo4jClient()

        # Step 1: Extract entities from Neo4j
        logger.info("Extracting entities from Neo4j")
        entities = _extract_entities_from_neo4j(neo4j_client, selected_node_types)

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

        # Step 3: Perform entity resolution
        # Check if Senzing is available
        if SENZING_AVAILABLE:
            try:
                senzing_client = get_senzing_client()
                if senzing_client.is_available():
                    logger.info("Using Senzing SDK for entity resolution")
                    resolved_count, relationship_count = _resolve_entities_with_senzing(
                        neo4j_client,
                        entities
                    )
                else:
                    logger.info("Senzing not available (no license), falling back to mock resolution")
                    resolved_count, relationship_count = _create_resolved_entity_nodes(
                        neo4j_client,
                        entity_groups
                    )
            except Exception as e:
                logger.error(f"Senzing resolution failed, falling back to mock: {e}")
                resolved_count, relationship_count = _create_resolved_entity_nodes(
                    neo4j_client,
                    entity_groups
                )
        else:
            logger.info("Using mock entity resolution (Senzing SDK not installed)")
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

        # Determine which resolution method was used
        resolution_method = 'mock'
        if SENZING_AVAILABLE:
            try:
                if get_senzing_client().is_available():
                    resolution_method = 'senzing'
            except:
                pass

        return {
            'status': 'success',
            'message': f'Successfully resolved {total_resolved_entities} entities into {resolved_count} clusters',
            'entities_extracted': len(entities),
            'duplicate_groups_found': len(entity_groups),
            'resolved_entities_created': resolved_count,
            'relationships_created': relationship_count,
            'entities_resolved': total_resolved_entities,
            'resolution_method': resolution_method,
            'node_types_processed': selected_node_types
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


def handle_get_available_node_types() -> Dict:
    """Get all available node types that can be resolved.

    Returns:
        Dictionary with available node types and their information
    """
    logger.info("Getting available node types for entity resolution")

    try:
        neo4j_client = Neo4jClient()
        node_types = _get_available_node_types(neo4j_client)

        logger.info(f"Found {len(node_types)} resolvable node types")

        return {
            'status': 'success',
            'nodeTypes': node_types,
            'totalTypes': len(node_types)
        }

    except Exception as e:
        logger.error(f"Failed to get available node types: {e}", exc_info=True)
        return {
            'status': 'error',
            'message': f'Failed to get available node types: {str(e)}',
            'nodeTypes': [],
            'totalTypes': 0
        }
