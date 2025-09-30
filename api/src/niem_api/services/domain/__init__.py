"""
Domain Layer

This package contains business logic organized by domain area.
Domain services implement core algorithms and workflows but should not
directly handle external I/O (use clients layer for that).

Domains:
- xml_to_graph: XML to Neo4j graph conversion
- schema: NIEM schema processing (treeshaking, dependency resolution, validation, mapping)
- graph: Graph database schema management
"""
