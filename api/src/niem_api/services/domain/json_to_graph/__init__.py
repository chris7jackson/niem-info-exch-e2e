"""
NIEM JSON to Graph Conversion Domain

Handles conversion of NIEM JSON (JSON-LD compliant) instance documents to Neo4j graph structures.
NIEM JSON uses JSON-LD features (@context, @id, @type) with NIEM-specific conventions.
"""

from .converter import generate_for_json_content

__all__ = ["generate_for_json_content"]
