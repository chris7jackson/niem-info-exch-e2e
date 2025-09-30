"""
Graph Database Domain

Handles Neo4j graph database schema management:
- Schema configuration from mappings
- Index and constraint management
- Schema inspection and reporting
"""

from .schema_manager import GraphSchemaManager, get_graph_schema_manager

__all__ = ['GraphSchemaManager', 'get_graph_schema_manager']
