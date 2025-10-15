#!/usr/bin/env python3

from unittest.mock import MagicMock, Mock, patch

import pytest
from neo4j.exceptions import ClientError
from neo4j.graph import Node, Relationship

from niem_api.clients.neo4j_client import Neo4jClient


class TestNeo4jClient:
    """Test suite for Neo4j client service"""

    @pytest.fixture
    def mock_driver(self):
        """Mock Neo4j driver"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_driver.session.return_value.__exit__.return_value = None
        return mock_driver, mock_session

    @pytest.fixture
    def neo4j_client(self, mock_driver):
        """Neo4j client with mocked driver"""
        driver, session = mock_driver
        with patch('niem_api.clients.neo4j_client.GraphDatabase.driver', return_value=driver):
            client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
            return client, session

    def test_neo4j_client_initialization(self):
        """Test Neo4j client initialization"""
        with patch('niem_api.clients.neo4j_client.GraphDatabase.driver') as mock_driver:
            client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")

            assert client.uri == "bolt://localhost:7687"
            assert client.user == "neo4j"
            assert client.password == "password"
            mock_driver.assert_called_once_with(
                "bolt://localhost:7687",
                auth=("neo4j", "password")
            )

    def test_query_success(self, neo4j_client):
        """Test successful query execution"""
        client, mock_session = neo4j_client

        # Mock query result
        mock_record = Mock()
        mock_record.data.return_value = {"name": "test", "id": 1}
        mock_result = [mock_record]
        mock_session.run.return_value = mock_result

        result = client.query("MATCH (n) RETURN n LIMIT 1")

        assert len(result) == 1
        assert result[0] == {"name": "test", "id": 1}
        mock_session.run.assert_called_once_with("MATCH (n) RETURN n LIMIT 1", {})

    def test_query_with_parameters(self, neo4j_client):
        """Test query execution with parameters"""
        client, mock_session = neo4j_client

        mock_session.run.return_value = []
        params = {"name": "test", "id": 123}

        client.query("MATCH (n {name: $name}) RETURN n", params)

        mock_session.run.assert_called_once_with(
            "MATCH (n {name: $name}) RETURN n",
            params
        )

    def test_query_error_handling(self, neo4j_client):
        """Test query error handling"""
        client, mock_session = neo4j_client

        mock_session.run.side_effect = ClientError("Invalid query")

        with pytest.raises(ClientError):
            client.query("INVALID QUERY")

    def test_query_graph_success(self, neo4j_client):
        """Test successful graph query execution"""
        client, mock_session = neo4j_client

        # Mock graph result with nodes and relationships
        mock_record = MagicMock()
        mock_node = MagicMock(spec=Node)
        mock_node.id = 1
        mock_node.labels = frozenset(["Person"])
        mock_node.items.return_value = [("name", "John"), ("age", 30)]

        mock_rel = MagicMock(spec=Relationship)
        mock_rel.id = 10
        mock_rel.type = "KNOWS"
        mock_rel.start_node = MagicMock(spec=Node)
        mock_rel.start_node.id = 1
        mock_rel.start_node.labels = frozenset(["Person"])
        mock_rel.start_node.items.return_value = [("name", "John")]
        mock_rel.end_node = MagicMock(spec=Node)
        mock_rel.end_node.id = 2
        mock_rel.end_node.labels = frozenset(["Person"])
        mock_rel.end_node.items.return_value = [("name", "Jane")]
        mock_rel.items.return_value = [("since", "2020")]

        # Make record.items() return an iterable
        mock_record.items.return_value = [("n", mock_node), ("r", mock_rel)]
        mock_session.run.return_value = [mock_record]

        result = client.query_graph("MATCH (n)-[r]->(m) RETURN n, r, m")

        assert "nodes" in result
        assert "relationships" in result
        assert len(result["nodes"]) >= 1
        assert len(result["relationships"]) == 1

        # Check first node has correct properties
        node = result["nodes"][0]
        assert "Person" in node["labels"]

    def test_query_graph_empty_result(self, neo4j_client):
        """Test graph query with empty result"""
        client, mock_session = neo4j_client

        mock_session.run.return_value = []

        result = client.query_graph("MATCH (n) WHERE n.name = 'nonexistent' RETURN n")

        assert result["nodes"] == []
        assert result["relationships"] == []

    def test_get_stats(self, neo4j_client):
        """Test database statistics retrieval"""
        client, mock_session = neo4j_client

        # Mock query results for stats
        mock_node_result = MagicMock()
        mock_node_result.single.return_value = {"count": 100}

        mock_rel_result = MagicMock()
        mock_rel_result.single.return_value = {"count": 50}

        mock_session.run.side_effect = [mock_node_result, mock_rel_result]

        stats = client.get_stats()

        assert stats["nodeCount"] == 100
        assert stats["relationshipCount"] == 50

    def test_get_schema(self, neo4j_client):
        """Test schema retrieval"""
        client, mock_session = neo4j_client

        # Mock labels result
        mock_labels_result = [
            MagicMock(**{"__getitem__": lambda self, key: "Person"}),
            MagicMock(**{"__getitem__": lambda self, key: "Company"})
        ]

        # Mock relationship types result
        mock_rel_types_result = [
            MagicMock(**{"__getitem__": lambda self, key: "WORKS_FOR"}),
            MagicMock(**{"__getitem__": lambda self, key: "KNOWS"})
        ]

        mock_session.run.side_effect = [mock_labels_result, mock_rel_types_result]

        schema = client.get_schema()

        assert "nodeLabels" in schema
        assert "relationshipTypes" in schema
        assert "Person" in schema["nodeLabels"]
        assert "KNOWS" in schema["relationshipTypes"]

    def test_close_connection(self, neo4j_client):
        """Test closing database connection"""
        client, _ = neo4j_client

        client.close()

        client.driver.close.assert_called_once()

    def test_query_returns_data(self, neo4j_client):
        """Test query returns record data correctly"""
        client, mock_session = neo4j_client

        # Mock multiple records
        mock_records = [
            MagicMock(data=lambda: {"name": "Alice", "age": 30}),
            MagicMock(data=lambda: {"name": "Bob", "age": 25})
        ]
        mock_session.run.return_value = mock_records

        result = client.query("MATCH (n:Person) RETURN n.name as name, n.age as age")

        assert len(result) == 2
        assert all(isinstance(r, dict) for r in result)

    def test_extract_graph_data_edge_cases(self, neo4j_client):
        """Test graph data extraction with edge cases"""
        client, mock_session = neo4j_client

        # Test with mixed data types
        mock_record = MagicMock()
        mock_node = MagicMock(spec=Node)
        mock_node.id = 1
        mock_node.labels = frozenset(["TestNode"])
        mock_node.items.return_value = [
            ("string_prop", "test"),
            ("int_prop", 42),
            ("bool_prop", True),
            ("list_prop", [1, 2, 3]),
            ("null_prop", None)
        ]

        mock_record.items.return_value = [("node", mock_node)]
        mock_session.run.return_value = [mock_record]

        result = client.query_graph("MATCH (n) RETURN n as node")

        node = result["nodes"][0]
        props = node["properties"]
        assert props["string_prop"] == "test"
        assert props["int_prop"] == 42
        assert props["bool_prop"] is True
        assert props["list_prop"] == [1, 2, 3]
        assert props["null_prop"] is None
