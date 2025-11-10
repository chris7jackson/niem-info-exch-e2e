"""
XML to Graph Conversion Domain

Handles conversion of XML instance documents to Neo4j graph structures.
"""

from .converter import generate_for_xml_content

__all__ = ["generate_for_xml_content"]
