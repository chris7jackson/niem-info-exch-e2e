"""Test fixtures for settings tests."""

from unittest.mock import Mock

from niem_api.clients.neo4j_client import Neo4jClient
from niem_api.models.models import Settings

# Sample settings data for testing
SAMPLE_SETTINGS = {
    "default": {"skip_xml_validation": False, "skip_json_validation": False},
    "skip_xml_only": {"skip_xml_validation": True, "skip_json_validation": False},
    "skip_json_only": {"skip_xml_validation": False, "skip_json_validation": True},
    "skip_both": {"skip_xml_validation": True, "skip_json_validation": True},
}


def create_mock_neo4j_client(query_responses=None):
    """
    Create a mock Neo4j client for testing.

    Args:
        query_responses: List of responses to return for consecutive query() calls.
                        If None, returns empty list by default.

    Returns:
        Mock Neo4j client
    """
    mock = Mock(spec=Neo4jClient)

    if query_responses is None:
        query_responses = [[]]

    # Set up side_effect for multiple calls
    mock.query.side_effect = query_responses

    return mock


def create_settings_object(skip_xml=False, skip_json=False):
    """
    Create a Settings object for testing.

    Args:
        skip_xml: Value for skip_xml_validation
        skip_json: Value for skip_json_validation

    Returns:
        Settings object
    """
    return Settings(skip_xml_validation=skip_xml, skip_json_validation=skip_json)


def create_neo4j_settings_response(skip_xml=False, skip_json=False):
    """
    Create a Neo4j query response for settings.

    Simulates the response from a Cypher query that returns settings.

    Args:
        skip_xml: Value for skip_xml_validation
        skip_json: Value for skip_json_validation

    Returns:
        List of dict as returned by Neo4j query
    """
    return [{"skip_xml_validation": skip_xml, "skip_json_validation": skip_json}]
