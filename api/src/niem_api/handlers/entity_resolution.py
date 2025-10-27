#!/usr/bin/env python3
"""
Entity resolution handler for orchestrating mock entity resolution workflows.

Coordinates between Neo4j client and mock entity resolution service to:
- Extract entities from the graph
- Run matching algorithm
- Create resolved entity nodes
- Return summary statistics
"""

import logging
from typing import Dict

from ..clients.neo4j_client import get_neo4j_client
from ..services.mock_entity_resolution import (
    create_resolved_entity_nodes,
    extract_entities_from_neo4j,
    get_resolution_status,
    group_entities_by_key,
    reset_entity_resolution,
)

logger = logging.getLogger(__name__)


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
        neo4j_client = get_neo4j_client()

        # Step 1: Extract entities from Neo4j
        logger.info("Extracting entities from Neo4j")
        entities = extract_entities_from_neo4j(neo4j_client)

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
        entity_groups = group_entities_by_key(entities)

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
        resolved_count, relationship_count = create_resolved_entity_nodes(
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
        neo4j_client = get_neo4j_client()
        status = get_resolution_status(neo4j_client)

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
        neo4j_client = get_neo4j_client()
        counts = reset_entity_resolution(neo4j_client)

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
