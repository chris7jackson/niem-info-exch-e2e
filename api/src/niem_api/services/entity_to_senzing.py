#!/usr/bin/env python3
"""
NIEM to Senzing Entity Conversion Service

Converts Neo4j graph entities with NIEM properties to Senzing JSON format
for entity resolution. Handles mapping of various NIEM entity types including
Person, Organization, Address, and Vehicle entities.

Mappings are loaded from configuration file for easy customization.
"""

import json
import logging
import os
import yaml
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Load mapping configuration from YAML file
_mapping_config: Optional[Dict] = None


def load_mapping_config() -> Dict:
    """
    Load NIEM to Senzing mapping configuration from YAML file.

    Returns:
        Dictionary containing mapping configuration
    """
    global _mapping_config

    if _mapping_config is not None:
        return _mapping_config

    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "niem_senzing_mappings.yaml"
    )

    try:
        with open(config_path, "r") as f:
            _mapping_config = yaml.safe_load(f)
            logger.info(f"Loaded mapping configuration from {config_path}")
    except FileNotFoundError:
        logger.warning(f"Mapping configuration file not found at {config_path}, using defaults")
        _mapping_config = get_default_mapping_config()
    except Exception as e:
        logger.error(f"Error loading mapping configuration: {e}")
        _mapping_config = get_default_mapping_config()

    return _mapping_config


def get_default_mapping_config() -> Dict:
    """
    Get default mapping configuration if file is not available.

    Returns:
        Default mapping configuration dictionary
    """
    return {
        "entity_categories": {
            "person": {
                "patterns": ["person", "driver", "child", "parent", "witness", "victim", "subject"],
                "senzing_record_type": "PERSON",
            },
            "organization": {
                "patterns": ["organization", "org", "company", "agency", "department", "official", "enforcement"],
                "senzing_record_type": "ORGANIZATION",
            },
            "address": {"patterns": ["address", "location", "place"], "senzing_record_type": "ADDRESS"},
            "vehicle": {"patterns": ["vehicle", "conveyance", "car"], "senzing_record_type": "VEHICLE"},
        },
        "field_mappings": {
            "nc_PersonFullName": "PRIMARY_NAME_FULL",
            "nc_PersonGivenName": "PRIMARY_NAME_FIRST",
            "nc_PersonSurName": "PRIMARY_NAME_LAST",
            "nc_PersonMiddleName": "PRIMARY_NAME_MIDDLE",
            "nc_PersonBirthDate": "DATE_OF_BIRTH",
            "nc_PersonSSNIdentification": "SSN_NUMBER",
            "nc_OrganizationName": "ORG_NAME",
            "nc_AddressFullText": "ADDR_FULL",
            "nc_VehicleIdentification": "VIN_NUMBER",
        },
        "multi_value_fields": ["PRIMARY_NAME_MIDDLE", "PHONE_NUMBER", "EMAIL_ADDRESS"],
        "date_formats": {"input_formats": ["%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"], "output_format": "%Y-%m-%d"},
        "recommended_types": [],
    }


def get_entity_category(entity: Dict) -> str:
    """
    Determine the category of a NIEM entity for Senzing processing.

    Args:
        entity: Entity dictionary from Neo4j

    Returns:
        Entity category: 'person', 'organization', 'address', 'vehicle', or 'other'
    """
    config = load_mapping_config()
    qname = entity.get("qname", "").lower()

    # Check each category's patterns from configuration
    for category, category_config in config.get("entity_categories", {}).items():
        patterns = category_config.get("patterns", [])
        if any(pattern in qname for pattern in patterns):
            return category

    return "other"


def get_senzing_record_type(entity_category: str) -> str:
    """
    Map entity category to Senzing record type.

    Args:
        entity_category: Category from get_entity_category()

    Returns:
        Senzing record type
    """
    config = load_mapping_config()
    category_config = config.get("entity_categories", {}).get(entity_category, {})
    return category_config.get("senzing_record_type", "GENERIC")


def neo4j_entity_to_senzing_record(entity: Dict, data_source: str = "NIEM_GRAPH") -> str:
    """
    Convert a Neo4j entity with NIEM properties to Senzing JSON format.

    Args:
        entity: Entity dictionary from Neo4j with properties
        data_source: Senzing data source identifier

    Returns:
        JSON string formatted for Senzing ingestion
    """
    props = entity.get("properties", {})

    # DEBUG: Print entity being processed
    print(
        f"\n[SENZING_DEBUG] Processing entity: neo4j_id={entity.get('neo4j_id')}, qname={entity.get('qname')}, properties_count={len(props)}"
    )

    # Start with base record structure
    senzing_record = {
        "DATA_SOURCE": data_source,
        "RECORD_ID": str(entity.get("entity_id") or entity.get("neo4j_id", "")),
        "ENTITY_TYPE": get_entity_category(entity).upper(),
    }

    # Determine and add record type
    entity_category = get_entity_category(entity)
    senzing_record["RECORD_TYPE"] = get_senzing_record_type(entity_category)

    # Add metadata
    senzing_record["SOURCE_FILE"] = entity.get("source", entity.get("sourceDoc", "unknown"))
    senzing_record["QNAME"] = entity.get("qname", "unknown")
    senzing_record["LOADED_DATE"] = datetime.utcnow().isoformat()

    # Load configuration
    config = load_mapping_config()
    field_mappings = config.get("field_mappings", {})
    multi_value_fields = config.get("multi_value_fields", [])

    # Add custom mappings if present
    custom_mappings = config.get("custom_mappings", {})
    field_mappings.update(custom_mappings)

    # Map NIEM properties to Senzing attributes
    for niem_field, senzing_field in field_mappings.items():
        # Check various property name formats
        # Try with nc_, j_, cyfs_ prefixes and without
        value = None

        # Direct property name
        if niem_field in props:
            value = props[niem_field]
        # Without prefix (e.g., PersonFullName instead of nc_PersonFullName)
        elif niem_field.replace("nc_", "").replace("j_", "").replace("cyfs_", "") in props:
            value = props[niem_field.replace("nc_", "").replace("j_", "").replace("cyfs_", "")]
        # Try alternate naming conventions
        elif niem_field.replace("_", "") in props:
            value = props[niem_field.replace("_", "")]

        if value is not None:
            # DEBUG: Print each field mapping
            print(f"[SENZING_DEBUG]   Mapped: {niem_field} → {senzing_field} = {repr(value)}")

            # Handle different value types
            if isinstance(value, list):
                # For lists, join with semicolon or take first value
                if len(value) > 0:
                    if senzing_field in multi_value_fields:
                        # These fields can have multiple values
                        senzing_record[senzing_field] = ";".join(str(v) for v in value)
                    else:
                        # Take first value for single-value fields
                        senzing_record[senzing_field] = str(value[0])
            elif value != "":
                senzing_record[senzing_field] = str(value)

    # Special handling for dates - ensure proper format
    if "DATE_OF_BIRTH" in senzing_record:
        senzing_record["DATE_OF_BIRTH"] = format_date_for_senzing(senzing_record["DATE_OF_BIRTH"])
    if "DATE_OF_DEATH" in senzing_record:
        senzing_record["DATE_OF_DEATH"] = format_date_for_senzing(senzing_record["DATE_OF_DEATH"])

    # Add relationship information if available
    relationships = entity.get("relationships", [])
    if relationships:
        senzing_record["RELATIONSHIPS"] = json.dumps(relationships)

    # DEBUG: Print final Senzing record
    print(f"[SENZING_DEBUG] Final Senzing record: {json.dumps(senzing_record, indent=2)}\n")

    return json.dumps(senzing_record)


def format_date_for_senzing(date_str: str) -> str:
    """
    Format a date string for Senzing using configured formats.

    Args:
        date_str: Date string in various formats

    Returns:
        Formatted date string or original if cannot parse
    """
    if not date_str:
        return date_str

    config = load_mapping_config()
    date_config = config.get("date_formats", {})
    input_formats = date_config.get("input_formats", ["%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"])
    output_format = date_config.get("output_format", "%Y-%m-%d")

    for fmt in input_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime(output_format)
        except ValueError:
            continue

    # Return original if cannot parse
    return date_str


def senzing_result_to_neo4j_format(senzing_result: Dict) -> Dict:
    """
    Convert Senzing entity resolution result to Neo4j-compatible format.

    Args:
        senzing_result: Result from Senzing API

    Returns:
        Dictionary formatted for Neo4j ResolvedEntity creation
    """
    resolved_entity = senzing_result.get("RESOLVED_ENTITY", {})

    neo4j_data = {
        "entity_id": f"SE_{resolved_entity.get('ENTITY_ID', '')}",
        "senzing_entity_id": resolved_entity.get("ENTITY_ID"),
        "entity_name": resolved_entity.get("ENTITY_NAME", ""),
        "match_key": resolved_entity.get("MATCH_KEY", ""),
        "match_level": resolved_entity.get("MATCH_LEVEL", 0),
        "match_score": resolved_entity.get("MATCH_SCORE", 0.0),
        "resolved_at": datetime.utcnow().isoformat(),
    }

    # Add feature scores if available
    features = resolved_entity.get("FEATURES", {})
    if features:
        neo4j_data["name_score"] = features.get("NAME", [{}])[0].get("SCORE", 0)
        neo4j_data["address_score"] = features.get("ADDRESS", [{}])[0].get("SCORE", 0)
        neo4j_data["dob_score"] = features.get("DOB", [{}])[0].get("SCORE", 0)
        neo4j_data["id_score"] = features.get("IDENTIFIER", [{}])[0].get("SCORE", 0)

    # Extract records that were matched
    records = resolved_entity.get("RECORDS", [])
    neo4j_data["matched_records"] = []

    for record in records:
        neo4j_data["matched_records"].append(
            {
                "data_source": record.get("DATA_SOURCE"),
                "record_id": record.get("RECORD_ID"),
                "match_key": record.get("MATCH_KEY"),
                "match_type": record.get("MATCH_TYPE"),
                "confidence": record.get("CONFIDENCE", 0),
            }
        )

    neo4j_data["record_count"] = len(records)

    return neo4j_data


def batch_convert_to_senzing(entities: List[Dict], data_source: str = "NIEM_GRAPH") -> List[Tuple[str, str, str]]:
    """
    Convert a batch of Neo4j entities to Senzing format.

    Args:
        entities: List of entity dictionaries from Neo4j
        data_source: Senzing data source identifier

    Returns:
        List of tuples (data_source, record_id, json_string) ready for Senzing
    """
    senzing_records = []

    for entity in entities:
        try:
            record_id = str(entity.get("entity_id") or entity.get("neo4j_id", ""))
            record_json = neo4j_entity_to_senzing_record(entity, data_source)
            senzing_records.append((data_source, record_id, record_json))

        except Exception as e:
            logger.error(f"Failed to convert entity {entity.get('entity_id')}: {e}")
            continue

    logger.info(f"Converted {len(senzing_records)} entities to Senzing format")
    return senzing_records


def extract_confidence_from_senzing(senzing_result: Dict) -> float:
    """
    Extract overall confidence score from Senzing result.

    Args:
        senzing_result: Result from Senzing API

    Returns:
        Confidence score between 0.0 and 1.0
    """
    resolved_entity = senzing_result.get("RESOLVED_ENTITY", {})

    # Get match score if available
    match_score = resolved_entity.get("MATCH_SCORE", 0)

    # Normalize to 0-1 range (Senzing scores can vary)
    if match_score > 100:
        return min(match_score / 1000, 1.0)
    elif match_score > 1:
        return match_score / 100
    else:
        return match_score
