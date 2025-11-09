#!/usr/bin/env python3
"""
Entity resolution handler for NIEM graph entities.

This module provides entity resolution capabilities using either:
1. Senzing SDK for advanced ML-based entity resolution (if available)
2. Text-based entity matching as fallback (simple name matching)

The handler supports dynamic node type selection, allowing users to choose
which entity types to resolve from the Neo4j graph.
"""

import hashlib
import json
import logging
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from ..clients.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

# Cache for Senzing field mappings
_SENZING_FIELD_MAPPINGS = None

# Try to import Senzing integration
SENZING_AVAILABLE = False
try:
    from ..clients.senzing_client import get_senzing_client, SenzingClient
    from ..services.entity_to_senzing import (
        batch_convert_to_senzing,
        senzing_result_to_neo4j_format,
        extract_confidence_from_senzing,
    )

    SENZING_AVAILABLE = True
    logger.info("Senzing integration available")
except ImportError:
    logger.info("Senzing integration not available - will use text-based entity matching")


def _load_senzing_field_mappings() -> Dict[str, str]:
    """Load Senzing field mappings from YAML configuration.

    Returns:
        Dictionary mapping NIEM field names to Senzing field names
    """
    global _SENZING_FIELD_MAPPINGS

    if _SENZING_FIELD_MAPPINGS is not None:
        return _SENZING_FIELD_MAPPINGS

    try:
        # Look for config file in multiple locations
        config_paths = [
            Path("/app/config/niem_senzing_mappings.yaml"),  # Docker
            Path(__file__).parent.parent.parent.parent / "config" / "niem_senzing_mappings.yaml",  # Development
        ]

        config_path = None
        for path in config_paths:
            if path.exists():
                config_path = path
                break

        if not config_path:
            logger.warning("Senzing mappings config not found, using empty mappings")
            _SENZING_FIELD_MAPPINGS = {}
            return _SENZING_FIELD_MAPPINGS

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Extract field mappings
        field_mappings = config.get("field_mappings", {})
        custom_mappings = config.get("custom_mappings", {})

        # Merge mappings
        _SENZING_FIELD_MAPPINGS = {**field_mappings, **custom_mappings}

        logger.info(f"Loaded {len(_SENZING_FIELD_MAPPINGS)} Senzing field mappings from {config_path}")
        return _SENZING_FIELD_MAPPINGS

    except Exception as e:
        logger.error(f"Failed to load Senzing field mappings: {e}")
        _SENZING_FIELD_MAPPINGS = {}
        return _SENZING_FIELD_MAPPINGS


def _count_senzing_mappable_fields(node_keys: List[str]) -> int:
    """Count how many properties on a node map to Senzing fields.

    Handles long prefixes like: role_of_person__nc_PersonFullName

    Args:
        node_keys: List of property keys from a Neo4j node

    Returns:
        Count of properties that map to Senzing fields
    """
    mappings = _load_senzing_field_mappings()
    if not mappings:
        return 0

    # Get the NIEM field names (keys from mappings)
    niem_fields = set(mappings.keys())

    # Count matches - check if any node key ends with or contains a known NIEM field name
    count = 0
    for node_key in node_keys:
        # Normalize key by removing all separators for comparison
        normalized_key = node_key.lower().replace("__", "").replace("_", "").replace("-", "")

        # Check if this key contains any known NIEM field
        for niem_field in niem_fields:
            # Normalize NIEM field the same way
            niem_field_normalized = niem_field.lower().replace("_", "")

            # Match if the normalized node key ends with the normalized NIEM field
            if normalized_key.endswith(niem_field_normalized):
                count += 1
                break  # Count each node key only once

    return count


def _extract_match_details_from_senzing_results(resolved_entities: Dict) -> Dict:
    """Extract and aggregate match details from Senzing resolution results.

    Args:
        resolved_entities: Dictionary of Senzing entity groups with their data

    Returns:
        Dictionary with aggregated match details including:
        - totalEntitiesMatched: Total number of entities that were matched
        - totalResolvedGroups: Number of unique resolved entity groups
        - matchQualityDistribution: Breakdown by confidence level
        - commonMatchKeys: Most common matching attributes
        - featureScores: Average scores for each feature type
        - resolutionRules: Rules used for entity resolution
    """
    match_details = {
        "totalEntitiesMatched": 0,
        "totalResolvedGroups": 0,
        "matchQualityDistribution": {"high": 0, "medium": 0, "low": 0},
        "commonMatchKeys": {},
        "featureScores": {},
        "resolutionRules": {},
    }

    if not resolved_entities:
        return match_details

    match_details["totalResolvedGroups"] = len(resolved_entities)

    # Aggregate data from each resolved entity group
    for senzing_entity_id, group_data in resolved_entities.items():
        entities_in_group = group_data["entities"]
        senzing_data = group_data["senzing_data"]

        # Count entities matched
        match_details["totalEntitiesMatched"] += len(entities_in_group)

        # Only process groups with duplicates (2+ entities)
        if len(entities_in_group) < 2:
            continue

        records = senzing_data.get("RECORDS", [])

        # Extract match quality from records
        for record in records:
            match_level_code = record.get("MATCH_LEVEL_CODE", "").upper()
            match_level = record.get("MATCH_LEVEL", 0)

            # Categorize match quality
            if match_level_code in ["RESOLVED", "EXACT_MATCH"] or match_level >= 3:
                match_details["matchQualityDistribution"]["high"] += 1
            elif match_level_code in ["POSSIBLY_SAME", "POSSIBLY_RELATED"] or match_level >= 2:
                match_details["matchQualityDistribution"]["medium"] += 1
            else:
                match_details["matchQualityDistribution"]["low"] += 1

            # Track match keys
            match_key = record.get("MATCH_KEY", "")
            if match_key:
                match_details["commonMatchKeys"][match_key] = match_details["commonMatchKeys"].get(match_key, 0) + 1

            # Track resolution rules
            errule_code = record.get("ERRULE_CODE", "")
            if errule_code:
                match_details["resolutionRules"][errule_code] = match_details["resolutionRules"].get(errule_code, 0) + 1

        # Extract feature scores
        # NOTE: Senzing feature scores are only available with enhanced flags
        # The FEATURES object contains feature values, not scores by default
        features = senzing_data.get("FEATURES", {})

        # Try to get record-level feature details if available
        records = senzing_data.get("RECORDS", [])
        for record in records:
            # Check for FEATURE_DETAILS in records (available with enhanced flags)
            if "FEATURES" in record:
                record_features = record["FEATURES"]
                for feature_type, feature_list in record_features.items():
                    if not feature_list:
                        continue

                    # Initialize feature score tracking
                    if feature_type not in match_details["featureScores"]:
                        match_details["featureScores"][feature_type] = {"total": 0, "count": 0, "average": 0}

                    # Aggregate scores from record features
                    for feature in feature_list:
                        # Try different possible score locations in Senzing response
                        score = 0
                        if isinstance(feature, dict):
                            # Try FEAT_DESC_VALUES structure
                            if "FEAT_DESC_VALUES" in feature and isinstance(feature["FEAT_DESC_VALUES"], list):
                                if len(feature["FEAT_DESC_VALUES"]) > 0:
                                    score = feature["FEAT_DESC_VALUES"][0].get("FEAT_SCORE", 0)
                            # Try direct USAGE_TYPE (can indicate match quality)
                            elif "USAGE_TYPE" in feature:
                                # USAGE_TYPE values like "FF" (full feature) indicate strong match
                                usage = feature.get("USAGE_TYPE", "")
                                if usage == "FF":
                                    score = 100
                                elif usage in ["FM", "FME"]:
                                    score = 75
                                elif usage in ["FNF"]:
                                    score = 50

                        if score > 0:
                            match_details["featureScores"][feature_type]["total"] += score
                            match_details["featureScores"][feature_type]["count"] += 1

        # If no record-level features, try entity-level features with count
        if not match_details["featureScores"] and features:
            for feature_type, feature_list in features.items():
                if not feature_list or not isinstance(feature_list, list):
                    continue

                # Initialize tracking
                if feature_type not in match_details["featureScores"]:
                    match_details["featureScores"][feature_type] = {"total": 0, "count": 0, "average": 0}

                # Count features as a proxy for score (number of matching values)
                # Normalize to 0-100 scale based on number of records
                num_records = len(records) if records else 1
                feature_count = len(feature_list)
                # If we have as many features as records, score 100; otherwise proportional
                score = min(100, int((feature_count / num_records) * 100)) if num_records > 0 else 0

                if score > 0:
                    match_details["featureScores"][feature_type]["total"] = score
                    match_details["featureScores"][feature_type]["count"] = 1

    # Calculate average feature scores
    for feature_type, scores in match_details["featureScores"].items():
        if scores["count"] > 0:
            scores["average"] = round(scores["total"] / scores["count"], 2)

    # Sort match keys and resolution rules by frequency
    match_details["commonMatchKeys"] = dict(
        sorted(match_details["commonMatchKeys"].items(), key=lambda x: x[1], reverse=True)[:10]
    )  # Top 10

    match_details["resolutionRules"] = dict(
        sorted(match_details["resolutionRules"].items(), key=lambda x: x[1], reverse=True)[:10]
    )  # Top 10

    return match_details


# ============================================================================
# Internal Helper Functions (Entity Resolution Logic)
# ============================================================================


def _extract_entities_from_neo4j(neo4j_client: Neo4jClient, selected_node_types: List[str]) -> List[Dict]:
    """Extract entities from Neo4j for resolution.

    Supports TWO patterns:
    1. Flattened attributes directly on entity nodes (e.g., entity.nc_PersonFullName)
    2. Related PersonName/OrganizationName nodes (e.g., entity-[:HAS_PERSONNAME]->personName)

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

    # Query to get entities with resolution attributes from entity OR related nodes
    # Handles both flattened and relationship-based structures
    query = """
    MATCH (entity)
    WHERE entity.qname IN $node_types

    // Optionally match related name nodes (PersonName, OrganizationName, etc.)
    OPTIONAL MATCH (entity)-[]->(relatedName)
    WHERE relatedName.qname IN ['nc:PersonName', 'nc:OrganizationName', 'nc:PersonBirthDate']

    // Get keys from both entity and related nodes
    WITH entity,
         keys(entity) as entityKeys,
         collect(keys(relatedName)) as relatedKeys,
         collect(relatedName) as relatedNodes

    // Flatten related keys
    WITH entity, entityKeys, relatedNodes,
         reduce(allKeys = entityKeys, keyList IN relatedKeys | allKeys + keyList) as allKeys

    // Find resolution-relevant attributes by checking patterns (case-insensitive)
    WITH entity, entityKeys, relatedNodes, allKeys,
         // Name fields
         [key IN allKeys WHERE toLower(key) CONTAINS 'fullname' OR toLower(key) CONTAINS 'organizationname'][0] as nameKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'givenname' OR toLower(key) CONTAINS 'firstname'][0] as givenNameKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'surname' OR toLower(key) CONTAINS 'lastname'][0] as surNameKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'middlename'][0] as middleNameKey,
         // Identifier fields
         [key IN allKeys WHERE toLower(key) CONTAINS 'ssn' OR toLower(key) CONTAINS 'socialsecurity'][0] as ssnKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'driverslicense' OR toLower(key) CONTAINS 'dln'][0] as dlKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'identification' AND NOT toLower(key) CONTAINS 'driver'][0] as idKey,
         // Date fields
         [key IN allKeys WHERE toLower(key) CONTAINS 'birthdate' OR toLower(key) CONTAINS 'dob'][0] as dobKey,
         // Address fields
         [key IN allKeys WHERE toLower(key) CONTAINS 'address' AND NOT toLower(key) CONTAINS 'email'][0] as addressKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'city'][0] as cityKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'state'][0] as stateKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'zip' OR toLower(key) CONTAINS 'postal'][0] as zipKey,
         // Contact fields
         [key IN allKeys WHERE toLower(key) CONTAINS 'phone' OR toLower(key) CONTAINS 'telephone'][0] as phoneKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'email'][0] as emailKey

    // Helper function to extract value from entity or related nodes
    WITH entity, relatedNodes, nameKey, givenNameKey, surNameKey, middleNameKey,
         ssnKey, dlKey, idKey, dobKey, addressKey, cityKey, stateKey, zipKey, phoneKey, emailKey,
         // Extract from entity first, then from related nodes
         CASE
           WHEN nameKey IS NOT NULL AND entity[nameKey] IS NOT NULL THEN entity[nameKey]
           WHEN nameKey IS NOT NULL THEN head([n IN relatedNodes WHERE n[nameKey] IS NOT NULL | n[nameKey]])
           ELSE null
         END as PersonFullName,
         CASE
           WHEN givenNameKey IS NOT NULL AND entity[givenNameKey] IS NOT NULL THEN entity[givenNameKey]
           WHEN givenNameKey IS NOT NULL THEN head([n IN relatedNodes WHERE n[givenNameKey] IS NOT NULL | n[givenNameKey]])
           ELSE null
         END as PersonGivenName,
         CASE
           WHEN surNameKey IS NOT NULL AND entity[surNameKey] IS NOT NULL THEN entity[surNameKey]
           WHEN surNameKey IS NOT NULL THEN head([n IN relatedNodes WHERE n[surNameKey] IS NOT NULL | n[surNameKey]])
           ELSE null
         END as PersonSurName,
         CASE
           WHEN middleNameKey IS NOT NULL AND entity[middleNameKey] IS NOT NULL THEN entity[middleNameKey]
           WHEN middleNameKey IS NOT NULL THEN head([n IN relatedNodes WHERE n[middleNameKey] IS NOT NULL | n[middleNameKey]])
           ELSE null
         END as PersonMiddleName,
         CASE
           WHEN ssnKey IS NOT NULL AND entity[ssnKey] IS NOT NULL THEN entity[ssnKey]
           WHEN ssnKey IS NOT NULL THEN head([n IN relatedNodes WHERE n[ssnKey] IS NOT NULL | n[ssnKey]])
           ELSE null
         END as PersonSSN,
         CASE
           WHEN dlKey IS NOT NULL AND entity[dlKey] IS NOT NULL THEN entity[dlKey]
           WHEN dlKey IS NOT NULL THEN head([n IN relatedNodes WHERE n[dlKey] IS NOT NULL | n[dlKey]])
           ELSE null
         END as DriverLicense,
         CASE
           WHEN dobKey IS NOT NULL AND entity[dobKey] IS NOT NULL THEN entity[dobKey]
           WHEN dobKey IS NOT NULL THEN head([n IN relatedNodes WHERE n[dobKey] IS NOT NULL | n[dobKey]])
           ELSE null
         END as BirthDate,
         CASE
           WHEN addressKey IS NOT NULL AND entity[addressKey] IS NOT NULL THEN entity[addressKey]
           WHEN addressKey IS NOT NULL THEN head([n IN relatedNodes WHERE n[addressKey] IS NOT NULL | n[addressKey]])
           ELSE null
         END as Address

    WITH entity, PersonFullName, PersonGivenName, PersonSurName, PersonMiddleName,
         PersonSSN, DriverLicense, BirthDate, Address,
         null as PersonID, null as City, null as State, null as ZipCode, null as Phone, null as Email

    // Only return entities that have at least one resolution-relevant attribute
    WHERE PersonFullName IS NOT NULL
       OR (PersonGivenName IS NOT NULL AND PersonSurName IS NOT NULL)
       OR PersonSSN IS NOT NULL
       OR DriverLicense IS NOT NULL
       OR PersonID IS NOT NULL
       OR BirthDate IS NOT NULL
       OR Address IS NOT NULL

    RETURN
        id(entity) as neo4j_id,
        entity.id as entity_id,
        entity.qname as qname,
        entity.sourceDoc as sourceDoc,
        entity._source_file as source_file,
        labels(entity) as labels,
        entity as entity_node,
        PersonFullName,
        PersonGivenName,
        PersonSurName,
        PersonMiddleName,
        PersonSSN,
        DriverLicense,
        PersonID,
        BirthDate,
        Address,
        City,
        State,
        ZipCode,
        Phone,
        Email
    """

    # Use query() instead of query_graph() for scalar results
    results = neo4j_client.query(query, {"node_types": selected_node_types})
    entities = []

    for record in results:
        entity_props = dict(record["entity_node"].items()) if record.get("entity_node") else {}

        # Extract all resolution attributes
        full_name = str(record.get("PersonFullName") or "")
        given_name = str(record.get("PersonGivenName") or "")
        surname = str(record.get("PersonSurName") or "")
        middle_name = str(record.get("PersonMiddleName") or "")
        ssn = str(record.get("PersonSSN") or "")
        driver_license = str(record.get("DriverLicense") or "")
        person_id = str(record.get("PersonID") or "")
        birth_date = str(record.get("BirthDate") or "")
        address = str(record.get("Address") or "")
        city = str(record.get("City") or "")
        state = str(record.get("State") or "")
        zip_code = str(record.get("ZipCode") or "")
        phone = str(record.get("Phone") or "")
        email = str(record.get("Email") or "")

        # Get source and entity type info
        source = record.get("sourceDoc") or record.get("source_file") or "unknown"
        entity_type = record.get("qname") or "Unknown"

        # Build list of found attributes for logging
        found_attrs = []
        if full_name:
            found_attrs.append(f"Name='{full_name}'")
        elif given_name and surname:
            found_attrs.append(f"Name='{given_name} {surname}'")
        if ssn:
            found_attrs.append(f"SSN='{ssn[:3]}-XX-XXXX'")  # Masked for logging
        if birth_date:
            found_attrs.append(f"DOB='{birth_date}'")
        if address:
            found_attrs.append(f"Address='{address[:20]}...'")
        if phone:
            found_attrs.append(f"Phone='{phone}'")

        # Log extraction with all found attributes
        if found_attrs:
            logger.info(
                f"✓ Extracted {entity_type} entity with {len(found_attrs)} attributes: {', '.join(found_attrs)} "
                f"from {source} (neo4j_id={record.get('neo4j_id')})"
            )
        else:
            logger.warning(
                f"⚠ Skipping {entity_type} - no resolution attributes found " f"(neo4j_id={record.get('neo4j_id')})"
            )
            continue

        entities.append(
            {
                "neo4j_id": record["neo4j_id"],
                "entity_id": record.get("entity_id"),
                "entity_type": entity_type,
                "qname": record.get("qname"),
                "labels": record.get("labels", []),
                "source": source,
                "properties": {
                    **entity_props,
                    "PersonFullName": full_name,
                    "PersonGivenName": given_name,
                    "PersonSurName": surname,
                    "PersonMiddleName": middle_name,
                    "PersonSSN": ssn,
                    "DriverLicense": driver_license,
                    "PersonID": person_id,
                    "BirthDate": birth_date,
                    "Address": address,
                    "City": city,
                    "State": state,
                    "ZipCode": zip_code,
                    "Phone": phone,
                    "Email": email,
                },
            }
        )

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
    props = entity.get("properties", {})

    # DEBUG: Show entity being processed for text-based matching
    print(f"\n[SENZING_DEBUG] TEXT-BASED MATCHING - Processing entity:")
    print(f"[SENZING_DEBUG]   neo4j_id: {entity.get('neo4j_id')}")
    print(f"[SENZING_DEBUG]   qname: {entity.get('qname')}")
    print(f"[SENZING_DEBUG]   properties: {list(props.keys())}")

    # Try PersonFullName first (for Child entities from NEICE documents)
    full_name = props.get("PersonFullName", "").strip().lower()
    if full_name:
        # Normalize: "Jason Ohlendorf" -> "jason_ohlendorf"
        key = full_name.replace(" ", "_")
        print(f"[SENZING_DEBUG]   Matched on PersonFullName: '{full_name}' → key='{key}'")
        return key

    # Fall back to GivenName + SurName (for CrashDriver entities)
    given_name = props.get("PersonGivenName", "").strip().lower()
    surname = props.get("PersonSurName", "").strip().lower()

    if given_name and surname:
        # Create normalized key: "peter" + "wimsey" -> "peter_wimsey"
        key = f"{given_name}_{surname}"
        print(f"[SENZING_DEBUG]   Matched on GivenName+SurName: '{given_name}' + '{surname}' → key='{key}'")
        return key

    # Insufficient data for matching
    print(f"[SENZING_DEBUG]   ❌ Insufficient data for matching - no name fields found")
    return ""


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
        sources = [e.get("source", "unknown") for e in group]
        logger.info(f"  Match key '{key}': {len(group)} entities from sources: {sources}")

    return duplicate_groups


def _create_resolved_entity_nodes(neo4j_client: Neo4jClient, entity_groups: Dict[str, List[Dict]]) -> Tuple[int, int]:
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
        props = first_entity["properties"]

        # Use PersonFullName if available (Child entity format)
        full_name = props.get("PersonFullName", "").strip()

        # Otherwise construct from name parts (CrashDriver format)
        if not full_name:
            given_name = props.get("PersonGivenName", "")
            middle_names = props.get("PersonMiddleName", [])
            surname = props.get("PersonSurName", "")

            # Handle middle names (can be list or string)
            if isinstance(middle_names, list):
                middle_str = " ".join(str(m) for m in middle_names if m)
            else:
                middle_str = str(middle_names) if middle_names else ""

            full_name = f"{given_name} {middle_str} {surname}".strip()

        birth_date = props.get("PersonBirthDate", "")

        # Collect graph isolation properties from all entities in the group
        upload_ids = set()
        schema_ids = set()
        source_docs = set()

        for entity in entities:
            entity_props = entity.get("properties", {})

            # Collect _upload_id
            upload_id = entity_props.get("_upload_id")
            if upload_id:
                upload_ids.add(upload_id)

            # Collect _schema_id
            schema_id = entity_props.get("_schema_id")
            if schema_id:
                schema_ids.add(schema_id)

            # Collect sourceDoc
            source_doc = entity.get("source") or entity_props.get("sourceDoc")
            if source_doc:
                source_docs.add(source_doc)

        # Convert sets to sorted lists for consistency
        upload_ids_list = sorted(list(upload_ids))
        schema_ids_list = sorted(list(schema_ids))
        source_docs_list = sorted(list(source_docs))

        # Create ResolvedEntity node
        create_node_query = """
        MERGE (re:ResolvedEntity {entity_id: $entity_id})
        SET re.name = $name,
            re.birth_date = $birth_date,
            re.resolved_count = $resolved_count,
            re.resolved_at = $resolved_at,
            re.match_key = $match_key,
            re._upload_ids = $upload_ids,
            re._schema_ids = $schema_ids,
            re.sourceDocs = $source_docs
        RETURN re
        """

        neo4j_client.query_graph(
            create_node_query,
            {
                "entity_id": entity_id,
                "name": full_name,
                "birth_date": birth_date,
                "resolved_count": len(entities),
                "resolved_at": timestamp,
                "match_key": match_key,
                "upload_ids": upload_ids_list,
                "schema_ids": schema_ids_list,
                "source_docs": source_docs_list,
            },
        )

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

            neo4j_client.query_graph(
                create_rel_query,
                {
                    "neo4j_id": int(entity["neo4j_id"]),
                    "entity_id": entity_id,
                    "confidence": 0.95,  # High confidence for text-based matching (name-only)
                    "matched_on": "given_name+surname",
                    "resolved_at": timestamp,
                },
            )

            relationship_count += 1

    logger.info(
        f"Created {resolved_count} ResolvedEntity nodes " f"with {relationship_count} RESOLVED_TO relationships"
    )

    return resolved_count, relationship_count


def _create_resolved_entity_relationships(neo4j_client: Neo4jClient) -> int:
    """Create relationships between ResolvedEntity nodes based on original entity relationships.

    This function finds relationships between original entities that have been resolved,
    then creates corresponding relationships between their ResolvedEntity nodes.

    Args:
        neo4j_client: Neo4j client instance

    Returns:
        Count of relationships created between ResolvedEntity nodes
    """
    # Query to find relationships between resolved entities
    # For each relationship between original entities, create a relationship
    # between their corresponding ResolvedEntity nodes
    query = """
    // Find all relationships between entities that have been resolved
    MATCH (source)-[original_rel]->(target)
    WHERE NOT type(original_rel) = 'RESOLVED_TO'
      AND exists((source)-[:RESOLVED_TO]->())
      AND exists((target)-[:RESOLVED_TO]->())

    // Get the ResolvedEntity nodes for source and target
    MATCH (source)-[:RESOLVED_TO]->(source_re:ResolvedEntity)
    MATCH (target)-[:RESOLVED_TO]->(target_re:ResolvedEntity)

    // Avoid creating duplicate relationships
    WHERE NOT exists((source_re)-[]->(target_re))

    // Create relationship between ResolvedEntity nodes with same type as original
    WITH source_re, target_re, type(original_rel) as rel_type,
         collect(distinct id(original_rel)) as original_rel_ids

    // Use CALL to dynamically create relationships with the original type
    CALL apoc.create.relationship(source_re, rel_type, {
        original_relationship_ids: original_rel_ids,
        created_at: datetime()
    }, target_re) YIELD rel

    RETURN count(rel) as relationships_created
    """

    try:
        result = neo4j_client.query(query, {})
        if result and len(result) > 0:
            count = result[0].get("relationships_created", 0)
            logger.info(f"Created {count} relationships between ResolvedEntity nodes")
            return count
        return 0
    except Exception as e:
        logger.warning(f"Could not create resolved entity relationships (APOC may not be available): {e}")
        logger.info("Falling back to generic RESOLVED_RELATIONSHIP type")

        # Fallback query without APOC - uses generic relationship type
        fallback_query = """
        MATCH (source)-[original_rel]->(target)
        WHERE NOT type(original_rel) = 'RESOLVED_TO'
          AND exists((source)-[:RESOLVED_TO]->())
          AND exists((target)-[:RESOLVED_TO]->())

        MATCH (source)-[:RESOLVED_TO]->(source_re:ResolvedEntity)
        MATCH (target)-[:RESOLVED_TO]->(target_re:ResolvedEntity)

        WHERE NOT exists((source_re)-[]->(target_re))

        WITH source_re, target_re, type(original_rel) as rel_type,
             collect(distinct id(original_rel)) as original_rel_ids

        MERGE (source_re)-[r:RESOLVED_RELATIONSHIP]->(target_re)
        SET r.original_type = rel_type,
            r.original_relationship_ids = original_rel_ids,
            r.created_at = datetime()

        RETURN count(r) as relationships_created
        """

        result = neo4j_client.query(fallback_query, {})
        if result and len(result) > 0:
            count = result[0].get("relationships_created", 0)
            logger.info(f"Created {count} RESOLVED_RELATIONSHIP relationships (fallback mode)")
            return count
        return 0


def _resolve_entities_with_senzing(neo4j_client: Neo4jClient, entities: List[Dict]) -> Tuple[int, int, Dict]:
    """
    Resolve entities using Senzing SDK.

    Args:
        neo4j_client: Neo4j client instance
        entities: List of entity dictionaries to resolve

    Returns:
        Tuple of (resolved_entity_count, relationship_count, match_details)
    """
    if not SENZING_AVAILABLE:
        logger.error("Senzing not available but Senzing resolution was called")
        return 0, 0, {}

    # Get or initialize Senzing client
    senzing_client = get_senzing_client()
    if not senzing_client.is_available():
        logger.error("Senzing client not available (license or configuration issue)")
        return 0, 0, {}

    if not senzing_client.initialized:
        if not senzing_client.initialize():
            logger.error("Failed to initialize Senzing client")
            return 0, 0, {}

    try:
        # Convert entities to Senzing format
        senzing_records = batch_convert_to_senzing(entities)

        # Log what's being sent to Senzing (DEBUG)
        logger.info("=" * 80)
        logger.info("SENZING INPUT: Converting entities to Senzing format")
        logger.info("=" * 80)
        for i, (data_source, record_id, record_json) in enumerate(senzing_records[:5]):  # Show first 5
            record_dict = json.loads(record_json)
            logger.info(f"\n--- Record {i+1}/{len(senzing_records)} (ID: {record_id}) ---")
            logger.info(f"DATA_SOURCE: {data_source}")
            logger.info(f"RECORD_TYPE: {record_dict.get('RECORD_TYPE', 'N/A')}")
            logger.info(f"ENTITY_TYPE: {record_dict.get('ENTITY_TYPE', 'N/A')}")
            logger.info(f"SOURCE_FILE: {record_dict.get('SOURCE_FILE', 'N/A')}")

            # Show name fields
            name_fields = {k: v for k, v in record_dict.items() if "NAME" in k}
            if name_fields:
                logger.info(f"NAME FIELDS: {json.dumps(name_fields, indent=2)}")

            # Show identifier fields
            id_fields = {
                k: v for k, v in record_dict.items() if any(x in k for x in ["SSN", "DOB", "LICENSE", "ID_NUMBER"])
            }
            if id_fields:
                logger.info(f"IDENTIFIER FIELDS: {json.dumps(id_fields, indent=2)}")

            # Show address fields
            addr_fields = {k: v for k, v in record_dict.items() if "ADDR" in k}
            if addr_fields:
                logger.info(f"ADDRESS FIELDS: {json.dumps(addr_fields, indent=2)}")

        if len(senzing_records) > 5:
            logger.info(f"\n... and {len(senzing_records) - 5} more records")
        logger.info("=" * 80)

        # Process records through Senzing
        batch_result = senzing_client.process_batch(senzing_records)
        logger.info(f"Processed {batch_result['processed']} records through Senzing")

        # Track resolution results
        resolved_entities = {}
        resolved_count = 0
        relationship_count = 0
        timestamp = datetime.utcnow().isoformat()

        # Log Senzing output
        logger.info("=" * 80)
        logger.info("SENZING OUTPUT: Retrieving resolution results")
        logger.info("=" * 80)

        # Get resolution results for each entity
        for i, entity in enumerate(entities):
            record_id = str(entity.get("entity_id") or entity.get("neo4j_id", ""))

            # Get Senzing resolution result
            result = senzing_client.get_entity_by_record_id("NIEM_GRAPH", record_id)
            if not result:
                logger.warning(f"No Senzing result for record {record_id}")
                continue

            # DEBUG: Print raw Senzing response
            resolved_entity = result.get("RESOLVED_ENTITY", {})
            records = resolved_entity.get("RECORDS", [])
            print(f"\n[SENZING_DEBUG] Senzing response for record_id={record_id}:")
            print(f"[SENZING_DEBUG]   ENTITY_ID: {resolved_entity.get('ENTITY_ID')}")
            print(f"[SENZING_DEBUG]   ENTITY_NAME: {resolved_entity.get('ENTITY_NAME')}")
            print(f"[SENZING_DEBUG]   Records matched: {len(records)}")
            for rec in records:
                print(
                    f"[SENZING_DEBUG]     - {rec.get('DATA_SOURCE')}/{rec.get('RECORD_ID')} (MATCH_KEY: {rec.get('MATCH_KEY', 'N/A')})"
                )

            # Extract Senzing entity ID
            senzing_entity_id = result.get("RESOLVED_ENTITY", {}).get("ENTITY_ID")
            if not senzing_entity_id:
                logger.warning(f"No entity ID in Senzing result for record {record_id}")
                continue

            # Log detailed Senzing output for first 5 entities
            if i < 5:
                resolved_entity = result.get("RESOLVED_ENTITY", {})
                logger.info(f"\n--- Senzing Result {i+1}/{len(entities)} (Record ID: {record_id}) ---")
                logger.info(f"SENZING ENTITY_ID: {senzing_entity_id}")
                logger.info(f"ENTITY_NAME: {resolved_entity.get('ENTITY_NAME', 'N/A')}")
                logger.info(f"RECORD_SUMMARY:")

                # Show all records that resolved to this entity
                records = resolved_entity.get("RECORDS", [])
                for rec in records:
                    logger.info(
                        f"  - {rec.get('DATA_SOURCE')}/{rec.get('RECORD_ID')} (MATCH_KEY: {rec.get('MATCH_KEY', 'N/A')})"
                    )

                # Show match details
                if len(records) > 1:
                    logger.info(f"✓ DUPLICATE DETECTED: {len(records)} records resolve to same entity")
                    # DEBUG: Print duplicate detection
                    record_ids = [rec.get("RECORD_ID") for rec in records]
                    print(
                        f"[SENZING_DEBUG] ✓ DUPLICATE FOUND: Records {record_ids} all resolve to Senzing ENTITY_ID={senzing_entity_id}"
                    )
                else:
                    logger.info(f"  UNIQUE ENTITY: Only 1 record for this entity")

            # Check if this is a duplicate (multiple records resolved to same entity)
            if senzing_entity_id not in resolved_entities:
                # First time seeing this Senzing entity
                resolved_entities[senzing_entity_id] = {
                    "entities": [],
                    "senzing_data": result.get("RESOLVED_ENTITY", {}),
                }

            resolved_entities[senzing_entity_id]["entities"].append(entity)

        logger.info(f"\n--- Summary ---")
        logger.info(f"Total Senzing Entity IDs: {len(resolved_entities)}")
        logger.info(
            f"Entities with duplicates (2+ records): {sum(1 for v in resolved_entities.values() if len(v['entities']) >= 2)}"
        )
        logger.info("=" * 80)

        # Create ResolvedEntity nodes for groups with duplicates
        for senzing_entity_id, group_data in resolved_entities.items():
            entities_in_group = group_data["entities"]
            senzing_data = group_data["senzing_data"]

            # Only create resolved entity if there are duplicates
            if len(entities_in_group) < 2:
                continue

            # Create unique entity ID for Neo4j
            entity_hash = hashlib.sha256(str(senzing_entity_id).encode()).hexdigest()[:12]
            neo4j_entity_id = f"SE_{entity_hash}"

            # Extract name from Senzing result
            entity_name = senzing_data.get("ENTITY_NAME", "")
            if not entity_name:
                # Fall back to first entity's name
                first_entity = entities_in_group[0]
                props = first_entity.get("properties", {})
                entity_name = props.get("PersonFullName", "")
                if not entity_name:
                    given = props.get("PersonGivenName", "")
                    surname = props.get("PersonSurName", "")
                    entity_name = f"{given} {surname}".strip()

            # Get match confidence from Senzing
            confidence = extract_confidence_from_senzing({"RESOLVED_ENTITY": senzing_data})

            # Collect graph isolation properties from all entities in the group
            upload_ids = set()
            schema_ids = set()
            source_docs = set()

            for entity in entities_in_group:
                entity_props = entity.get("properties", {})

                # Collect _upload_id
                upload_id = entity_props.get("_upload_id")
                if upload_id:
                    upload_ids.add(upload_id)

                # Collect _schema_id
                schema_id = entity_props.get("_schema_id")
                if schema_id:
                    schema_ids.add(schema_id)

                # Collect sourceDoc
                source_doc = entity.get("source") or entity_props.get("sourceDoc")
                if source_doc:
                    source_docs.add(source_doc)

            # Convert sets to sorted lists for consistency
            upload_ids_list = sorted(list(upload_ids))
            schema_ids_list = sorted(list(schema_ids))
            source_docs_list = sorted(list(source_docs))

            # Create ResolvedEntity node
            create_node_query = """
            MERGE (re:ResolvedEntity {entity_id: $entity_id})
            SET re.name = $name,
                re.senzing_entity_id = $senzing_entity_id,
                re.resolved_count = $resolved_count,
                re.resolved_at = $resolved_at,
                re.resolution_method = 'senzing',
                re.confidence = $confidence,
                re._upload_ids = $upload_ids,
                re._schema_ids = $schema_ids,
                re.sourceDocs = $source_docs
            RETURN re
            """

            neo4j_client.query_graph(
                create_node_query,
                {
                    "entity_id": neo4j_entity_id,
                    "name": entity_name,
                    "senzing_entity_id": senzing_entity_id,
                    "resolved_count": len(entities_in_group),
                    "resolved_at": timestamp,
                    "confidence": confidence,
                    "upload_ids": upload_ids_list,
                    "schema_ids": schema_ids_list,
                    "source_docs": source_docs_list,
                },
            )

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

                neo4j_client.query_graph(
                    create_rel_query,
                    {
                        "neo4j_id": int(entity["neo4j_id"]),
                        "entity_id": neo4j_entity_id,
                        "confidence": confidence,
                        "resolved_at": timestamp,
                        "senzing_entity_id": senzing_entity_id,
                    },
                )

                relationship_count += 1

        logger.info(
            f"Senzing resolution created {resolved_count} resolved entities with {relationship_count} relationships"
        )

        # Extract match details from Senzing results
        match_details = _extract_match_details_from_senzing_results(resolved_entities)

        return resolved_count, relationship_count, match_details

    except Exception as e:
        logger.error(f"Error during Senzing resolution: {e}", exc_info=True)
        return 0, 0, {}


def _reset_entity_resolution(neo4j_client: Neo4jClient) -> Dict[str, int]:
    """Remove all entity resolution data from Neo4j and Senzing.

    Args:
        neo4j_client: Neo4j client instance

    Returns:
        Dictionary with counts of deleted nodes and relationships
    """
    # Delete ResolvedEntity nodes and all their relationships
    # Use DETACH DELETE to automatically remove all relationships
    delete_query = """
    MATCH (re:ResolvedEntity)
    WITH re, size([(re)-[r:RESOLVED_TO]-() | r]) as resolved_to_count
    DETACH DELETE re
    RETURN count(re) as nodes_deleted, sum(resolved_to_count) as rels_deleted
    """

    result = neo4j_client.query(delete_query, {})
    node_count = 0
    rel_count = 0
    if result and len(result) > 0:
        node_count = result[0].get("nodes_deleted", 0)
        rel_count = result[0].get("rels_deleted", 0)

    logger.info(f"Reset entity resolution: deleted {node_count} nodes " f"and {rel_count} relationships from Neo4j")

    # Also clear Senzing repository if available
    if SENZING_AVAILABLE:
        try:
            senzing_client = get_senzing_client()
            if senzing_client.is_available() and senzing_client.initialized:
                if senzing_client.purge_repository():
                    logger.info("Purged all records from Senzing repository")
                else:
                    logger.warning("Failed to purge Senzing repository")
        except Exception as e:
            logger.warning(f"Could not purge Senzing repository: {e}")

    return {"resolved_entities_deleted": node_count, "relationships_deleted": rel_count}


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

    result = neo4j_client.query(count_query, {})
    resolved_count = 0
    if result and len(result) > 0:
        resolved_count = result[0].get("resolved_entities", 0)

    # Count RESOLVED_TO relationships
    rel_count_query = """
    MATCH ()-[r:RESOLVED_TO]->()
    RETURN count(r) as relationships
    """

    rel_result = neo4j_client.query(rel_count_query, {})
    rel_count = 0
    if rel_result and len(rel_result) > 0:
        rel_count = rel_result[0].get("relationships", 0)

    return {"resolved_entity_clusters": resolved_count, "entities_resolved": rel_count, "is_active": resolved_count > 0}


def _get_available_node_types(neo4j_client: Neo4jClient) -> List[Dict]:
    """Get all available node types that can be resolved.

    This function discovers all node types in the graph that have:
    - A qname property (indicating they're NIEM entities)
    - Resolution attributes (names, DOB, SSN, addresses, phone/email, etc.)

    Supports flattened attributes with long prefixes (e.g., role_of_person__nc_person__nc_personname)

    Args:
        neo4j_client: Neo4j client instance

    Returns:
        List of dictionaries containing node type information
    """
    # Query to find all distinct qnames and check if they have resolution-relevant attributes
    discovery_query = """
    // Find all distinct qnames in the graph
    // Exclude component nodes (PersonName, OrganizationName, etc.) - only show actual entities
    MATCH (n)
    WHERE n.qname IS NOT NULL
      AND NOT n.qname IN ['nc:PersonName', 'nc:OrganizationName', 'nc:PersonBirthDate',
                          'nc:PersonGivenName', 'nc:PersonSurName', 'nc:PersonMiddleName',
                          'nc:PersonFullName', 'nc:AddressFullText', 'nc:Date']
    WITH DISTINCT n.qname as qname, labels(n)[0] as label

    // Count entities for each qname and get a sample entity
    MATCH (entity)
    WHERE entity.qname = qname
    WITH qname, label, count(entity) as count, collect(entity)[0] as sample

    // Also check related nodes for resolution attributes (PersonName, OrganizationName, etc.)
    OPTIONAL MATCH (sample)-[]->(relatedName)
    WHERE relatedName.qname IN ['nc:PersonName', 'nc:OrganizationName', 'nc:PersonBirthDate']

    // Get all property keys from both the sample entity and related nodes
    WITH qname, label, count, sample,
         keys(sample) as entityKeys,
         collect(keys(relatedName)) as relatedKeys,
         collect(relatedName) as relatedNodes

    // Flatten all keys from entity and related nodes
    WITH qname, label, count, sample, relatedNodes,
         reduce(allKeys = entityKeys, keyList IN relatedKeys | allKeys + keyList) as allKeys

    // Find resolution-relevant attributes by checking suffixes (case-insensitive patterns)
    // Support long prefixes like: role_of_person__nc_person__nc_personname
    WITH qname, label, count, sample, relatedNodes, allKeys,
         // Name fields
         [key IN allKeys WHERE toLower(key) CONTAINS 'fullname' OR toLower(key) CONTAINS 'organizationname'][0] as nameKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'givenname' OR toLower(key) CONTAINS 'firstname'][0] as givenNameKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'surname' OR toLower(key) CONTAINS 'lastname'][0] as surNameKey,
         // Identifier fields
         [key IN allKeys WHERE toLower(key) CONTAINS 'ssn' OR toLower(key) CONTAINS 'socialsecurity'][0] as ssnKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'driverslicense' OR toLower(key) CONTAINS 'dln'][0] as dlKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'identification' AND NOT toLower(key) CONTAINS 'driver'][0] as idKey,
         // Date fields
         [key IN allKeys WHERE toLower(key) CONTAINS 'birthdate' OR toLower(key) CONTAINS 'dob'][0] as dobKey,
         // Address fields
         [key IN allKeys WHERE toLower(key) CONTAINS 'address' AND NOT toLower(key) CONTAINS 'email'][0] as addressKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'city'][0] as cityKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'state'][0] as stateKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'zip' OR toLower(key) CONTAINS 'postal'][0] as zipKey,
         // Contact fields
         [key IN allKeys WHERE toLower(key) CONTAINS 'phone' OR toLower(key) CONTAINS 'telephone'][0] as phoneKey,
         [key IN allKeys WHERE toLower(key) CONTAINS 'email'][0] as emailKey

    // Check if entity has at least one resolution-relevant attribute
    WITH qname, label, count, sample, relatedNodes, nameKey, givenNameKey, surNameKey, ssnKey, dlKey, idKey,
         dobKey, addressKey, cityKey, stateKey, zipKey, phoneKey, emailKey,
         // Count how many resolution attributes exist
         size([k IN [nameKey, givenNameKey, ssnKey, dlKey, idKey, dobKey, addressKey, phoneKey, emailKey] WHERE k IS NOT NULL]) as attrCount

    // Only return types that have at least one resolution-relevant attribute
    WHERE attrCount > 0

    // Get sample values from found keys (check entity first, then related nodes)
    WITH qname, label, count, sample, relatedNodes, attrCount,
         CASE
           WHEN nameKey IS NOT NULL AND sample[nameKey] IS NOT NULL THEN sample[nameKey]
           WHEN nameKey IS NOT NULL THEN head([n IN relatedNodes WHERE n[nameKey] IS NOT NULL | n[nameKey]])
           ELSE null
         END as sampleName,
         CASE
           WHEN givenNameKey IS NOT NULL AND sample[givenNameKey] IS NOT NULL THEN sample[givenNameKey]
           WHEN givenNameKey IS NOT NULL THEN head([n IN relatedNodes WHERE n[givenNameKey] IS NOT NULL | n[givenNameKey]])
           ELSE null
         END as sampleGivenName,
         CASE
           WHEN surNameKey IS NOT NULL AND sample[surNameKey] IS NOT NULL THEN sample[surNameKey]
           WHEN surNameKey IS NOT NULL THEN head([n IN relatedNodes WHERE n[surNameKey] IS NOT NULL | n[surNameKey]])
           ELSE null
         END as sampleSurName,
         CASE
           WHEN ssnKey IS NOT NULL AND sample[ssnKey] IS NOT NULL THEN sample[ssnKey]
           WHEN ssnKey IS NOT NULL THEN head([n IN relatedNodes WHERE n[ssnKey] IS NOT NULL | n[ssnKey]])
           ELSE null
         END as sampleSSN,
         CASE
           WHEN dobKey IS NOT NULL AND sample[dobKey] IS NOT NULL THEN sample[dobKey]
           WHEN dobKey IS NOT NULL THEN head([n IN relatedNodes WHERE n[dobKey] IS NOT NULL | n[dobKey]])
           ELSE null
         END as sampleDOB,
         CASE
           WHEN addressKey IS NOT NULL AND sample[addressKey] IS NOT NULL THEN sample[addressKey]
           WHEN addressKey IS NOT NULL THEN head([n IN relatedNodes WHERE n[addressKey] IS NOT NULL | n[addressKey]])
           ELSE null
         END as sampleAddress,
         keys(sample) + reduce(allKeys = [], keyList IN [n IN relatedNodes | keys(n)] | allKeys + keyList) as sampleKeys

    // Find the hierarchy path from root to this entity type
    WITH qname, label, count, sample, attrCount, sampleName, sampleGivenName, sampleSurName,
         sampleSSN, sampleDOB, sampleAddress, sampleKeys
    OPTIONAL MATCH path = (root)-[*]->(sample)
    WHERE sample.qname = qname
      AND NOT EXISTS((()-[]->(root)))  // root has no incoming edges
      AND root.qname IS NOT NULL
    WITH qname, label, count, attrCount, sampleName, sampleGivenName, sampleSurName,
         sampleSSN, sampleDOB, sampleAddress, sampleKeys,
         collect(DISTINCT [node in nodes(path) | node.qname])[0] as pathQnames

    RETURN DISTINCT qname, label, count, attrCount,
           sampleName,
           sampleGivenName,
           sampleSurName,
           sampleSSN,
           sampleDOB,
           sampleAddress,
           sampleKeys,
           pathQnames[0..-1] as hierarchyPath
    ORDER BY count DESC
    """

    results = neo4j_client.query(discovery_query, {})
    node_types = []
    seen_qnames = set()  # Track qnames to prevent duplicates

    for record in results:
        qname = record["qname"]

        # Skip if we've already seen this qname
        if qname in seen_qnames:
            continue
        seen_qnames.add(qname)

        # Determine which resolution attributes are available
        attr_count = record.get("attrCount", 0)
        if attr_count == 0:
            continue

        # Build list of available fields dynamically
        available_fields = []
        if record.get("sampleName"):
            available_fields.append("Name")
        if record.get("sampleGivenName") or record.get("sampleSurName"):
            available_fields.append("Given/Surname")
        if record.get("sampleSSN"):
            available_fields.append("SSN")
        if record.get("sampleDOB"):
            available_fields.append("DOB")
        if record.get("sampleAddress"):
            available_fields.append("Address")

        # Determine category
        category = "other"
        try:
            from ..services.entity_to_senzing import get_entity_category

            entity_mock = {"qname": qname}
            category = get_entity_category(entity_mock)
        except:
            pass

        # Filter: Include person, organization, and location entity types
        # (as requested by user - key entities for resolution)
        if category not in ["person", "organization", "address"]:
            logger.debug(f"Excluding {qname} from entity resolution (category: {category})")
            continue

        # Extract hierarchy path (list of qnames from root to this entity)
        hierarchy_path = record.get("hierarchyPath", [])
        if hierarchy_path and isinstance(hierarchy_path, list):
            # Filter out None values and ensure it's a list of strings
            hierarchy_path = [str(h) for h in hierarchy_path if h is not None]
        else:
            hierarchy_path = []

        # Compute how many properties map to Senzing fields (for "recommended" types)
        sample_keys = record.get("sampleKeys", [])
        senzing_mapped_count = _count_senzing_mappable_fields(sample_keys)
        is_recommended = senzing_mapped_count > 0

        node_type_info = {
            "qname": qname,
            "label": record["label"],
            "count": record["count"],
            "nameFields": available_fields,  # Changed from name_fields
            "category": category,
            "hierarchyPath": hierarchy_path,
            "attributeCount": attr_count,
            "senzingMappedFields": senzing_mapped_count,
            "recommended": is_recommended,
        }

        node_types.append(node_type_info)

        logger.info(
            f"Found resolvable type: {record['qname']} "
            f"({record['count']} entities, {attr_count} resolution attributes, "
            f"{senzing_mapped_count} Senzing-mapped fields{' - RECOMMENDED' if is_recommended else ''})"
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
    3. Falls back to text-based entity matching if Senzing unavailable
    4. Creates ResolvedEntity nodes for duplicates
    5. Returns summary statistics

    Args:
        selected_node_types: List of qnames to resolve (required)

    Returns:
        Dictionary with resolution results and statistics
    """
    if not selected_node_types:
        return {
            "status": "error",
            "message": "No node types selected for entity resolution",
            "entitiesExtracted": 0,
            "duplicateGroupsFound": 0,
            "resolvedEntitiesCreated": 0,
            "relationshipsCreated": 0,
            "entitiesResolved": 0,
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
                "status": "success",
                "message": "No entities found in the graph to resolve",
                "entitiesExtracted": 0,
                "duplicateGroupsFound": 0,
                "resolvedEntitiesCreated": 0,
                "relationshipsCreated": 0,
                "entitiesResolved": 0,
                "resolutionMethod": "text_based",
                "nodeTypesProcessed": selected_node_types,
            }

        # Step 2: Group entities by matching keys
        logger.info("Grouping entities by matching criteria")
        entity_groups = _group_entities_by_key(entities)

        if not entity_groups:
            return {
                "status": "success",
                "message": "No duplicate entities found - all entities are unique",
                "entitiesExtracted": len(entities),
                "duplicateGroupsFound": 0,
                "resolvedEntitiesCreated": 0,
                "relationshipsCreated": 0,
                "entitiesResolved": 0,
                "resolutionMethod": "text_based",
                "nodeTypesProcessed": selected_node_types,
            }

        # Step 3: Perform entity resolution
        # Check if Senzing is available
        match_details = {}  # Initialize match details
        if SENZING_AVAILABLE:
            try:
                senzing_client = get_senzing_client()
                if senzing_client.is_available():
                    logger.info("Using Senzing SDK for entity resolution")
                    resolved_count, relationship_count, match_details = _resolve_entities_with_senzing(
                        neo4j_client, entities
                    )
                else:
                    logger.info("Senzing not available (no license), falling back to text-based entity matching")
                    resolved_count, relationship_count = _create_resolved_entity_nodes(neo4j_client, entity_groups)
            except Exception as e:
                logger.error(f"Senzing resolution failed, falling back to text-based entity matching: {e}")
                resolved_count, relationship_count = _create_resolved_entity_nodes(neo4j_client, entity_groups)
        else:
            logger.info("Using text-based entity matching (Senzing SDK not installed)")
            resolved_count, relationship_count = _create_resolved_entity_nodes(neo4j_client, entity_groups)

        # Step 4: Create relationships between ResolvedEntity nodes
        logger.info("Creating relationships between resolved entities")
        resolved_relationships_count = _create_resolved_entity_relationships(neo4j_client)

        # Calculate total entities involved in resolution
        total_resolved_entities = sum(len(group) for group in entity_groups.values())

        logger.info(
            f"Entity resolution completed: {resolved_count} clusters created, "
            f"{total_resolved_entities} entities resolved, "
            f"{resolved_relationships_count} relationships created between resolved entities"
        )

        # Determine which resolution method was used
        resolution_method = "text_based"
        if SENZING_AVAILABLE:
            try:
                if get_senzing_client().is_available():
                    resolution_method = "senzing"
            except:
                pass

        response = {
            "status": "success",
            "message": f"Successfully resolved {total_resolved_entities} entities into {resolved_count} clusters with {resolved_relationships_count} relationships",
            "entitiesExtracted": len(entities),
            "duplicateGroupsFound": len(entity_groups),
            "resolvedEntitiesCreated": resolved_count,
            "relationshipsCreated": relationship_count + resolved_relationships_count,
            "entitiesResolved": total_resolved_entities,
            "resolutionMethod": resolution_method,
            "nodeTypesProcessed": selected_node_types,
        }

        # Include match details if using Senzing
        if resolution_method == "senzing" and match_details:
            response["matchDetails"] = match_details

        return response

    except Exception as e:
        logger.error(f"Entity resolution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Entity resolution failed: {str(e)}",
            "entitiesExtracted": 0,
            "duplicateGroupsFound": 0,
            "resolvedEntitiesCreated": 0,
            "relationshipsCreated": 0,
        }


def handle_get_resolution_status() -> Dict:
    """Get current entity resolution statistics.

    Returns:
        Dictionary with resolution status and counts
    """
    try:
        neo4j_client = Neo4jClient()
        status = _get_resolution_status(neo4j_client)

        return {"status": "success", **status}

    except Exception as e:
        logger.error(f"Failed to get resolution status: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to get resolution status: {str(e)}",
            "resolved_entity_clusters": 0,
            "entities_resolved": 0,
            "is_active": False,
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

        return {"status": "success", "message": "Entity resolution reset successfully", **counts}

    except Exception as e:
        logger.error(f"Failed to reset entity resolution: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to reset entity resolution: {str(e)}",
            "resolved_entities_deleted": 0,
            "relationships_deleted": 0,
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

        return {"status": "success", "nodeTypes": node_types, "totalTypes": len(node_types)}

    except Exception as e:
        logger.error(f"Failed to get available node types: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to get available node types: {str(e)}",
            "nodeTypes": [],
            "totalTypes": 0,
        }
