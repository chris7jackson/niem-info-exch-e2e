'use client';

import { useEffect, useRef, useState } from 'react';
import cytoscape, { Core, EdgeDefinition, NodeDefinition } from 'cytoscape';
import dagre from 'cytoscape-dagre';
import coseBilkent from 'cytoscape-cose-bilkent';
import { GraphNode, GraphEdge, Namespace } from '@/lib/api';

// Register layout algorithms
if (typeof cytoscape !== 'undefined') {
  cytoscape.use(dagre);
  cytoscape.use(coseBilkent);
}

export interface SchemaGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  namespaces: Namespace[];
  layout: 'tree' | 'force';
  selectedNodeId?: string | null;
  onNodeSelect?: (nodeId: string | null) => void;
  onEdgeSelect?: (edgeId: string | null) => void;
  filterNamespaces?: string[];
  filterNodeTypes?: string[];
  searchTerm?: string;
  expandedNodes?: Set<string>;
  maxDepth?: number;
}

/**
 * SchemaGraph - Interactive graph visualization using Cytoscape.js
 *
 * This component follows the data-driven design principle:
 * - No hardcoded enum values for categories, node types, or edge types
 * - Dynamically assigns colors, shapes, and styles based on data
 * - Provides reasonable defaults for unknown values
 */
export default function SchemaGraph({
  nodes,
  edges,
  namespaces,
  layout = 'tree',
  selectedNodeId = null,
  onNodeSelect,
  onEdgeSelect,
  filterNamespaces = [],
  filterNodeTypes = [],
  searchTerm = '',
  expandedNodes = new Set(),
  maxDepth = 10
}: SchemaGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [isReady, setIsReady] = useState(false);

  // Build dynamic color map from namespace categories
  const getCategoryColorMap = (namespaces: Namespace[]): Map<string, string> => {
    const categories = Array.from(new Set(namespaces.map(ns => ns.category)));
    const colorPalette = [
      '#3182ce', // Blue
      '#38a169', // Green
      '#dd6b20', // Orange
      '#805ad5', // Purple
      '#d69e2e', // Yellow
      '#e53e3e', // Red
      '#38b2ac', // Teal
      '#ed64a6', // Pink
    ];

    const colorMap = new Map<string, string>();
    categories.forEach((category, idx) => {
      colorMap.set(category, colorPalette[idx % colorPalette.length]);
    });

    // Fallback for unknown categories
    colorMap.set('__unknown__', '#718096'); // Gray

    return colorMap;
  };

  // Get color for a namespace category
  const getCategoryColor = (category: string, colorMap: Map<string, string>): string => {
    return colorMap.get(category) || colorMap.get('__unknown__') || '#718096';
  };

  // Build dynamic shape map from node types
  const getNodeTypeShape = (nodeType: string): string => {
    const defaultShapes: { [key: string]: string } = {
      'class': 'roundrectangle',
      'association': 'diamond',
      'property': 'ellipse',
      'augmentation': 'hexagon',
    };

    return defaultShapes[nodeType] || 'ellipse'; // Fallback to ellipse
  };

  // Build dynamic edge style from edge types
  const getEdgeStyle = (edgeType: string): { lineStyle: string; width: number; targetArrow: string } => {
    const defaultStyles: { [key: string]: { lineStyle: string; width: number; targetArrow: string } } = {
      'property': { lineStyle: 'solid', width: 2, targetArrow: 'triangle' },
      'association': { lineStyle: 'dashed', width: 2, targetArrow: 'diamond' },
      'augmentation': { lineStyle: 'dotted', width: 2, targetArrow: 'vee' },
      'extends': { lineStyle: 'solid', width: 3, targetArrow: 'triangle-backcurve' },
    };

    return defaultStyles[edgeType] || { lineStyle: 'solid', width: 1, targetArrow: 'triangle' }; // Fallback
  };

  // Filter nodes and edges based on criteria
  const getFilteredElements = () => {
    const colorMap = getCategoryColorMap(namespaces);

    // Filter nodes
    let filteredNodes = nodes;

    // Apply namespace filter
    if (filterNamespaces.length > 0) {
      filteredNodes = filteredNodes.filter(node =>
        filterNamespaces.includes(node.namespace)
      );
    }

    // Apply node type filter
    if (filterNodeTypes.length > 0) {
      filteredNodes = filteredNodes.filter(node =>
        filterNodeTypes.includes(node.nodeType)
      );
    }

    // Apply depth filter
    filteredNodes = filteredNodes.filter(node => node.depth <= maxDepth);

    // Apply search filter (highlight matching nodes)
    const matchesSearch = (node: GraphNode): boolean => {
      if (!searchTerm) return true;
      const term = searchTerm.toLowerCase();
      return (
        node.label.toLowerCase().includes(term) ||
        node.id.toLowerCase().includes(term) ||
        (node.documentation && node.documentation.toLowerCase().includes(term))
      );
    };

    // Build node set for edge filtering
    const nodeIds = new Set(filteredNodes.map(n => n.id));

    // Filter edges (only include edges where both source and target are visible)
    const filteredEdges = edges.filter(edge =>
      nodeIds.has(edge.source) && nodeIds.has(edge.target)
    );

    // Convert to Cytoscape elements
    const nodeElements: NodeDefinition[] = filteredNodes.map(node => {
      const color = getCategoryColor(node.namespaceCategory, colorMap);
      const shape = getNodeTypeShape(node.nodeType);
      const highlighted = matchesSearch(node);
      const selected = node.id === selectedNodeId;

      return {
        data: {
          id: node.id,
          label: node.label,
          namespace: node.namespace,
          nodeType: node.nodeType,
          category: node.namespaceCategory,
          documentation: node.documentation || '',
          hasChildren: node.hasChildren,
          depth: node.depth,
          metadata: node.metadata,
        },
        classes: [
          highlighted ? 'highlighted' : '',
          selected ? 'selected' : '',
        ].filter(Boolean).join(' '),
        style: {
          'background-color': selected ? '#fbbf24' : (highlighted ? '#fef3c7' : color),
          'shape': shape,
          'width': Math.min(120, Math.max(40, 40 + (node.metadata.usageCount || 0) * 2)),
          'height': Math.min(120, Math.max(40, 40 + (node.metadata.usageCount || 0) * 2)),
          'label': node.label,
          'font-size': '12px',
          'text-valign': 'center',
          'text-halign': 'center',
          'border-width': selected ? 3 : 1,
          'border-color': selected ? '#f59e0b' : '#333',
        }
      };
    });

    const edgeElements: EdgeDefinition[] = filteredEdges.map(edge => {
      const style = getEdgeStyle(edge.edgeType);
      const sourceNode = filteredNodes.find(n => n.id === edge.source);
      const targetColor = sourceNode ? getCategoryColor(sourceNode.namespaceCategory, colorMap) : '#718096';

      return {
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.label,
          edgeType: edge.edgeType,
          cardinality: edge.cardinality || '',
          documentation: edge.documentation || '',
        },
        style: {
          'line-color': targetColor,
          'line-style': style.lineStyle,
          'width': style.width,
          'target-arrow-shape': style.targetArrow,
          'target-arrow-color': targetColor,
          'label': edge.label,
          'font-size': '10px',
          'text-rotation': 'autorotate',
          'curve-style': 'bezier',
        }
      };
    });

    return [...nodeElements, ...edgeElements];
  };

  // Initialize Cytoscape
  useEffect(() => {
    if (!containerRef.current) return;

    const elements = getFilteredElements();

    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#3182ce',
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '12px',
            'min-zoomed-font-size': 8,
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#718096',
            'target-arrow-color': '#718096',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': '10px',
            'text-rotation': 'autorotate',
          }
        },
        {
          selector: '.highlighted',
          style: {
            'background-color': '#fef3c7',
            'border-width': 2,
            'border-color': '#fbbf24',
          }
        },
        {
          selector: '.selected',
          style: {
            'background-color': '#fbbf24',
            'border-width': 3,
            'border-color': '#f59e0b',
          }
        }
      ],
      layout: layout === 'tree' ? {
        name: 'dagre',
        rankDir: 'TB',
        nodeSep: 50,
        edgeSep: 10,
        rankSep: 100,
        animate: true,
        animationDuration: 500,
      } as any : {
        name: 'cose-bilkent',
        animate: true,
        animationDuration: 500,
      } as any
    });

    // Event handlers
    cy.on('tap', 'node', (event) => {
      const nodeId = event.target.id();
      if (onNodeSelect) {
        onNodeSelect(nodeId);
      }
    });

    cy.on('tap', 'edge', (event) => {
      const edgeId = event.target.id();
      if (onEdgeSelect) {
        onEdgeSelect(edgeId);
      }
    });

    // Click on background deselects
    cy.on('tap', (event) => {
      if (event.target === cy && onNodeSelect) {
        onNodeSelect(null);
      }
    });

    cyRef.current = cy;
    setIsReady(true);

    return () => {
      cy.destroy();
    };
  }, [nodes, edges, namespaces, layout, filterNamespaces, filterNodeTypes, searchTerm, selectedNodeId, maxDepth]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full bg-white border border-gray-200 rounded-lg"
      style={{ minHeight: '600px' }}
    />
  );
}
