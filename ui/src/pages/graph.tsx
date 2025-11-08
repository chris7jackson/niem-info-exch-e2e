import { useEffect, useMemo, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import EntityResolutionPanel from '../components/EntityResolutionPanel';

interface GraphNode {
  id: string;
  label: string;
  labels: string[];
  properties: Record<string, any>;
}

interface GraphRelationship {
  id: string;
  type: string;
  startNode: string;
  endNode: string;
  properties: Record<string, any>;
}

interface GraphData {
  nodes: GraphNode[];
  relationships: GraphRelationship[];
  metadata: {
    nodeLabels: string[];
    relationshipTypes: string[];
    nodeCount: number;
    relationshipCount: number;
  };
}

// Universal color generation using HSL for consistent, distinguishable colors
// Works for any number of labels/types without hardcoding
const generateDistinguishableColors = (count: number): string[] => {
  const colors: string[] = [];
  const saturation = 70; // Good saturation for visibility
  const lightness = 50; // Good lightness for contrast

  for (let i = 0; i < count; i++) {
    const hue = ((i * 360) / count) % 360;
    colors.push(`hsl(${hue}, ${saturation}%, ${lightness}%)`);
  }

  return colors;
};

// Universal relationship styling - data-driven, no hardcoded patterns
const getRelationshipStyle = (
  relationshipType: string,
  allTypes: string[],
  colorMap: Record<string, string>
) => {
  return {
    color: colorMap[relationshipType] || '#888888', // Dark gray default
    width: 2, // Balanced width (not too thick)
    style: 'solid', // Consistent style for all relationships
    opacity: 0.7, // Slightly transparent so overlapping edges are visible
  };
};

// Data-agnostic node sizing based on connectivity
const getNodeSize = (node: GraphNode, relationships: GraphRelationship[]): number => {
  const connections = relationships.filter(
    (rel) => rel.startNode === node.id || rel.endNode === node.id
  ).length;

  // Smaller, consistent sizing to reduce overlap
  // Base: 20, scales minimally with connections, max 40
  return Math.max(20, Math.min(40, 20 + connections * 1));
};

// Universal label display - prioritizes semantic information
const getDisplayLabel = (node: GraphNode): string => {
  const props = node.properties;

  // Priority 1: qname (NIEM qualified name) - most semantic
  if (props.qname && typeof props.qname === 'string' && props.qname.length > 0) {
    const qname = props.qname.toString();
    return qname.length > 25 ? qname.substring(0, 25) + '...' : qname;
  }

  // Priority 2: semantic ID from NIEM data
  if (props.id && typeof props.id === 'string' && props.id.length > 0) {
    const id = props.id.toString();
    return id.length > 25 ? id.substring(0, 25) + '...' : id;
  }

  // Priority 3: Common meaningful properties
  const labelPriority = [
    'name',
    'title',
    'label',
    'identifier',
    'content',
    'text',
    'value',
    'description',
  ];

  for (const key of labelPriority) {
    if (props[key] && typeof props[key] === 'string') {
      const value = props[key].toString();
      if (value.length > 0) {
        return value.length > 25 ? value.substring(0, 25) + '...' : value;
      }
    }
  }

  // Fallback to node type label
  return node.label || node.labels[0] || `Node ${node.id}`;
};

// Build comprehensive tooltip showing all node information
const buildNodeTooltip = (node: GraphNode): string => {
  const lines: string[] = [];

  // Show all labels
  lines.push(`Type: ${node.labels.join(', ')}`);

  // Show semantic ID
  if (node.properties.id) {
    lines.push(`ID: ${node.properties.id}`);
  }

  // Show qname
  if (node.properties.qname) {
    lines.push(`QName: ${node.properties.qname}`);
  }

  // Count properties
  const propCount = Object.keys(node.properties).length;
  lines.push(`Properties: ${propCount}`);

  // Show augmentation properties if any
  const augProps = Object.keys(node.properties).filter((k) => k.startsWith('aug_'));
  if (augProps.length > 0) {
    lines.push(`Augmentations: ${augProps.length}`);
  }

  return lines.join('\n');
};

// Build comprehensive relationship tooltip
const buildEdgeTooltip = (rel: GraphRelationship): string => {
  const lines: string[] = [];

  lines.push(`Type: ${rel.type}`);
  lines.push(`From: ${rel.startNode}`);
  lines.push(`To: ${rel.endNode}`);

  const propCount = Object.keys(rel.properties).length;
  if (propCount > 0) {
    lines.push(`Properties: ${propCount}`);
  }

  return lines.join('\n');
};

export default function GraphPage() {
  const cyRef = useRef<HTMLDivElement | null>(null);
  const cyInstance = useRef<cytoscape.Core | null>(null);
  const currentLayout = useRef<any>(null);
  const [isMountedState, setIsMountedState] = useState(false);
  const isMounted = useRef(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cypherQuery, setCypherQuery] = useState(
    'MATCH (n) OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m'
  );
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [selectedLayout, setSelectedLayout] = useState('cose');
  const [showNodeLabels, setShowNodeLabels] = useState(true);
  const [showRelationshipLabels, setShowRelationshipLabels] = useState(false); // Off by default for dense graphs
  const [showResolvedEntities, setShowResolvedEntities] = useState(true); // Toggle for resolved entities - on by default
  const [resultLimit, setResultLimit] = useState(10000);
  const [filenameFilter, setFilenameFilter] = useState<string[]>([]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Extract unique source filenames from graph data
  const availableFiles = useMemo(() => {
    if (!graphData) return [];
    const files = new Set<string>();
    graphData.nodes.forEach(node => {
      const sourceFile = node.properties?._source_file || node.properties?.sourceDoc;
      if (sourceFile) {
        files.add(sourceFile);
      }
    });
    return Array.from(files).sort();
  }, [graphData]);

  useEffect(() => {
    // Set mounted state
    isMounted.current = true;
    setIsMountedState(true);

    const validLayouts = ['cose', 'circle', 'grid', 'breadthfirst', 'concentric'];
    if (!validLayouts.includes(selectedLayout)) {
      setSelectedLayout('cose');
    }

    // Wait a bit for DOM to be ready, then auto-load graph
    const timer = setTimeout(() => {
      if (!cyRef.current) {
        const element = document.getElementById('graph-viz');
        if (element) {
          cyRef.current = element as HTMLDivElement;
        }
      }

      // Get all nodes and relationships (includes isolated nodes)
      executeQuery('MATCH (n) OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m');
    }, 500); // Wait 500ms for DOM to be ready

    // Cleanup on unmount
    return () => {
      clearTimeout(timer);
      isMounted.current = false;
      setIsMountedState(false);

      // Stop any running layout first
      if (currentLayout.current) {
        try {
          currentLayout.current.stop();
        } catch (err) {
          console.warn('Error stopping layout:', err);
        }
        currentLayout.current = null;
      }

      if (cyInstance.current) {
        try {
          // Stop any running animations/layouts before destroying
          cyInstance.current.stop();
          cyInstance.current.destroy();
        } catch (err) {
          console.warn('Error cleaning up Cytoscape instance:', err);
        }
        cyInstance.current = null;
      }
    };
  }, []);

  // Re-render graph when filename filter changes
  useEffect(() => {
    if (graphData && isMounted.current) {
      renderGraph(graphData);
    }
  }, [filenameFilter]);

  // Reload graph when resolved entities toggle changes
  useEffect(() => {
    if (isMountedState && cyRef.current && graphData) {
      // Re-execute the current query with the new toggle state
      executeQuery(cypherQuery, showResolvedEntities);
    }
  }, [showResolvedEntities]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };

    if (isDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isDropdownOpen]);

  const executeQuery = async (query: string, includeResolved: boolean = showResolvedEntities) => {
    setLoading(true);
    setError(null);

    try {
      // If not including resolved entities, wrap the query to filter them out
      let finalQuery = query;
      if (!includeResolved && query.includes('MATCH (n)')) {
        // Add WHERE clause to exclude ResolvedEntity nodes
        finalQuery = query.replace(
          'MATCH (n)',
          `MATCH (n) WHERE NOT 'ResolvedEntity' IN labels(n)`
        );
        // Also filter out RESOLVED_TO relationships
        if (query.includes('MATCH (n)-[r]-')) {
          finalQuery = finalQuery.replace(
            'MATCH (n)-[r]-(m)',
            `MATCH (n)-[r]-(m) WHERE NOT type(r) = 'RESOLVED_TO' AND NOT 'ResolvedEntity' IN labels(m)`
          );
        }
      }

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/graph/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token') || 'devtoken'}`,
        },
        body: JSON.stringify({ query: finalQuery, limit: resultLimit }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();

      if (result.status === 'success') {
        setGraphData(result.data);
        renderGraph(result.data);
      } else {
        throw new Error(result.message || 'Query execution failed');
      }
    } catch (err: any) {
      console.error('Query execution failed:', err);
      setError(err.message || 'Failed to execute query');
    } finally {
      setLoading(false);
    }
  };

  const renderGraph = (data: GraphData) => {
    // Try to get the ref by ID if ref is null
    if (!cyRef.current) {
      const element = document.getElementById('graph-viz');
      if (element) {
        cyRef.current = element as HTMLDivElement;
      }
    }

    if (!cyRef.current) {
      // Try again after a short delay
      setTimeout(() => {
        const element = document.getElementById('graph-viz');
        if (element) {
          cyRef.current = element as HTMLDivElement;
          renderGraph(data);
        }
      }, 100);
      return;
    }

    // Check container dimensions
    const containerWidth = cyRef.current.offsetWidth;
    const containerHeight = cyRef.current.offsetHeight;

    if (containerWidth === 0 || containerHeight === 0) {
      // Try to set dimensions explicitly
      cyRef.current.style.width = '100%';
      cyRef.current.style.height = '600px';
      cyRef.current.style.position = 'relative';
    }

    // Generate universal colors for ALL node labels
    const nodeColors = generateDistinguishableColors(data.metadata.nodeLabels.length);
    const labelColorMap: Record<string, string> = {};
    data.metadata.nodeLabels.forEach((label, index) => {
      labelColorMap[label] = nodeColors[index];
    });

    // Generate universal colors for ALL relationship types
    const edgeColors = generateDistinguishableColors(data.metadata.relationshipTypes.length);
    const relTypeColorMap: Record<string, string> = {};
    data.metadata.relationshipTypes.forEach((type, index) => {
      relTypeColorMap[type] = edgeColors[index];
    });

    // Convert nodes to Cytoscape format with universal styling
    const cyNodes = data.nodes.map((node) => {
      const displayLabel = getDisplayLabel(node);
      const nodeSize = getNodeSize(node, data.relationships);
      const tooltip = buildNodeTooltip(node);

      // Special styling for ResolvedEntity nodes, Association nodes, and EntityHub nodes
      const isResolvedEntity = node.labels.includes('ResolvedEntity');
      const isAssociation = node.properties?._isAssociation === true ||
                            node.properties?._isAssociation === 'True' ||
                            node.properties?.qname?.endsWith('Association');
      const isEntityHub = node.properties?._isHub === true || node.label.startsWith('Entity_');

      // Color priority: EntityHub (teal) > Association (orange) > ResolvedEntity (purple) > default
      const nodeColor = isEntityHub ? '#14B8A6' : (isAssociation ? '#FF8C00' : (isResolvedEntity ? '#9333EA' : (labelColorMap[node.label] || '#95A5A6')));
      const nodeShape = isEntityHub ? 'triangle' : (isResolvedEntity ? 'diamond' : (isAssociation ? 'hexagon' : 'ellipse'));

      return {
        data: {
          id: node.id, // Use semantic ID for node identity
          label: showNodeLabels ? displayLabel : '',
          nodeType: node.label,
          nodeLabels: node.labels,
          properties: node.properties,
          color: nodeColor,
          size: nodeSize,
          tooltip: tooltip,
          shape: nodeShape,
          isResolvedEntity: isResolvedEntity,
          isAssociation: isAssociation,
          isEntityHub: isEntityHub,
        },
      };
    });

    // Filter nodes by filename if filter is active (exact match)
    let filteredNodes = cyNodes;
    let filteredNodeIds = new Set(cyNodes.map(n => n.data.id));

    if (filenameFilter.length > 0) {
      // Step 1: Get nodes from selected files
      const primaryNodes = cyNodes.filter(node => {
        const sourceFile = node.data.properties?._source_file || node.data.properties?.sourceDoc;
        return sourceFile && filenameFilter.includes(sourceFile);
      });
      const primaryNodeIds = new Set(primaryNodes.map(n => n.data.id));

      // Step 2: Find all edges connected to primary nodes
      const connectedEdges = data.relationships.filter(rel =>
        primaryNodeIds.has(rel.startNode) || primaryNodeIds.has(rel.endNode)
      );

      // Step 3: Include all nodes that are connected to primary nodes
      const relatedNodeIds = new Set<string>();
      connectedEdges.forEach(edge => {
        relatedNodeIds.add(edge.startNode);
        relatedNodeIds.add(edge.endNode);
      });

      // Filter to include both primary and related nodes
      filteredNodes = cyNodes.filter(node => relatedNodeIds.has(node.data.id));
      filteredNodeIds = relatedNodeIds;
    }

    // Convert relationships to Cytoscape format with universal styling
    const cyEdges = data.relationships.map((rel) => {
      const relStyle = getRelationshipStyle(
        rel.type,
        data.metadata.relationshipTypes,
        relTypeColorMap
      );

      const tooltip = buildEdgeTooltip(rel);

      // Special styling for RESOLVED_TO, ASSOCIATED_WITH, REPRESENTS, and CONTAINS relationships
      const isResolvedTo = rel.type === 'RESOLVED_TO';
      const isAssociatedWith = rel.type === 'ASSOCIATED_WITH';
      const isRepresents = rel.type === 'REPRESENTS';
      const isContains = rel.type === 'CONTAINS';

      // Color priority: REPRESENTS (teal) > ASSOCIATED_WITH (orange) > RESOLVED_TO (purple) > CONTAINS (grey) > default
      const edgeColor = isRepresents ? '#14B8A6' : (isAssociatedWith ? '#FF8C00' : (isResolvedTo ? '#9333EA' : (isContains ? '#888888' : relStyle.color)));
      const edgeWidth = (isResolvedTo || isAssociatedWith || isRepresents) ? 3 : relStyle.width; // Thicker for special relationships
      const edgeStyle = isResolvedTo ? 'dashed' : (isAssociatedWith ? 'dotted' : (isRepresents ? 'solid' : relStyle.style));

      return {
        data: {
          id: rel.id,
          source: rel.startNode, // Semantic ID
          target: rel.endNode, // Semantic ID
          label: showRelationshipLabels ? rel.type : '',
          type: rel.type,
          properties: rel.properties,
          color: edgeColor,
          width: edgeWidth,
          lineStyle: edgeStyle,
          opacity: relStyle.opacity,
          tooltip: tooltip,
          isResolvedTo: isResolvedTo,
          isAssociatedWith: isAssociatedWith,
          isRepresents: isRepresents,
        },
      };
    });

    // Filter edges to only show edges between filtered nodes
    const filteredEdges = cyEdges.filter(edge =>
      filteredNodeIds.has(edge.data.source) && filteredNodeIds.has(edge.data.target)
    );


    // Stop any running layout first
    if (currentLayout.current) {
      try {
        currentLayout.current.stop();
      } catch (err) {
        console.warn('Error stopping layout:', err);
      }
      currentLayout.current = null;
    }

    // Destroy existing instance
    if (cyInstance.current) {
      try {
        // Stop any running animations/layouts first
        cyInstance.current.stop();
        cyInstance.current.destroy();
      } catch (err) {
        console.warn('Error destroying Cytoscape instance:', err);
      }
      cyInstance.current = null;
    }

    // Create new Cytoscape instance with data-agnostic styles
    try {
      cyInstance.current = cytoscape({
      container: cyRef.current,

      elements: [...filteredNodes, ...filteredEdges],

      // Viewport and zoom settings for better visibility
      minZoom: 0.1,
      maxZoom: 10,

      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            label: 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'text-rotation': 'none', // Force horizontal (no rotation)
            'text-justification': 'center',
            color: '#000000',
            'text-outline-width': 1.5,
            'text-outline-color': '#ffffff',
            'font-size': '7px',
            'font-weight': 'normal',
            width: 'data(size)',
            height: 'data(size)',
            shape: 'data(shape)' as any, // Diamond for ResolvedEntity, ellipse for others
            'border-width': 1,
            'border-color': '#333333',
            'text-wrap': 'wrap', // Wrap text instead of truncating
            'min-zoomed-font-size': 4,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 3,
            'border-color': '#FFA500',
            'text-outline-color': '#FFA500',
          },
        },
        {
          selector: 'edge',
          style: {
            width: 'data(width)',
            'line-color': 'data(color)',
            'target-arrow-color': 'data(color)',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            label: 'data(label)',
            'font-size': '7px',
            color: '#444444',
            'text-outline-width': 1,
            'text-outline-color': '#ffffff',
            'text-rotation': 'autorotate',
            'text-margin-y': -8,
            opacity: 'data(opacity)' as any,
            'line-style': 'data(lineStyle)' as any,
            'min-zoomed-font-size': 4,
          },
        },
        {
          selector: 'edge:selected',
          style: {
            width: 3,
            'line-color': '#FFA500',
            'target-arrow-color': '#FFA500',
          },
        },
      ],

      layout: {
        name: ['cose', 'circle', 'grid', 'breadthfirst', 'concentric'].includes(selectedLayout)
          ? selectedLayout
          : 'cose',
        animate: true,
        animationDuration: 500,
        fit: true,
        padding: 50,
        stop: function() {
          // Ensure fit happens after layout completes
          if (cyInstance.current && isMounted.current) {
            cyInstance.current.fit();
          }
        },
        // Generic layout options that work for any data
        ...(selectedLayout === 'cose' && {
          nodeOverlap: 20,
          refresh: 20,
          randomize: false,
          componentSpacing: 100,
          nodeRepulsion: 400000,
          idealEdgeLength: 100,
          edgeElasticity: 100,
          nestingFactor: 5,
          gravity: 80,
          numIter: 1000,
          initialTemp: 200,
          coolingFactor: 0.95,
          minTemp: 1.0,
        }),
        ...(selectedLayout === 'circle' && {
          radius: Math.min(200, Math.max(100, data.nodes.length * 8)),
        }),
        ...(selectedLayout === 'concentric' && {
          concentric: function (node: any) {
            return node.data('size'); // Arrange by connectivity
          },
          levelWidth: function () {
            return 1;
          },
        }),
      } as any,
    });

    // Universal event handlers - show complete information
    cyInstance.current.on('tap', 'node', function (evt) {
      const node = evt.target;
      const data = node.data();
      console.log('=== Node Details ===');
      console.log('Labels:', data.nodeLabels.join(', '));
      console.log('Primary Label:', data.nodeType);
      console.log('Semantic ID:', data.id);

      if (data.properties.qname) {
        console.log('QName:', data.properties.qname);
      }

      console.log('\n--- All Properties ---');
      Object.entries(data.properties).forEach(([key, value]) => {
        const prefix = key.startsWith('aug_') ? '[AUG] ' : '';
        console.log(`${prefix}${key}:`, value);
      });
      console.log('==================');
    });

    cyInstance.current.on('tap', 'edge', function (evt) {
      const edge = evt.target;
      const data = edge.data();
      console.log('=== Relationship Details ===');
      console.log('Type:', data.type);
      console.log('Internal ID:', data.id);
      console.log('From:', data.source);
      console.log('To:', data.target);

      if (Object.keys(data.properties).length > 0) {
        console.log('\n--- Properties ---');
        Object.entries(data.properties).forEach(([key, value]) => {
          console.log(`${key}:`, value);
        });
      }
      console.log('===========================');
    });

    // Add hover effects for nodes
    cyInstance.current.on('mouseover', 'node', function (evt) {
      const node = evt.target;
      node.style({
        'border-width': 2,
        'border-color': '#FF6B35',
      });
    });

    cyInstance.current.on('mouseout', 'node', function (evt) {
      const node = evt.target;
      node.style({
        'border-width': 1,
        'border-color': '#333333',
      });
    });

    } catch (error) {
      console.error('Failed to initialize Cytoscape:', error);
      return;
    }

    // Fit to viewport
    if (cyInstance.current) {
      cyInstance.current.fit();
    }

    // Apply initial layout after creation
    // Use circle layout for small graphs (< 20 nodes) for better visibility
    const layoutName = filteredNodes.length < 20 ? 'circle' : (selectedLayout || 'cose');

    if (cyInstance.current) {
      currentLayout.current = cyInstance.current.layout({
        name: layoutName,
        animate: true,
        animationDuration: 800,
        fit: true,
        padding: 50,
        // Additional options for better initial view
        boundingBox: { x1: 0, y1: 0, w: cyRef.current.offsetWidth, h: cyRef.current.offsetHeight },
        avoidOverlap: true,
        spacingFactor: 1.5, // More spacing between nodes
      } as any);

      // Also ensure we fit and center after layout completes
      currentLayout.current.on('layoutstop', () => {
        if (cyInstance.current && isMounted.current) {
          try {
            cyInstance.current.fit();
            cyInstance.current.center();
          } catch (err) {
            console.warn('Error fitting graph after layout:', err);
          }
        }
      });

      currentLayout.current.run();
    }
  };

  const applyLayout = (layoutName: string) => {
    if (cyInstance.current && graphData && isMounted.current) {
      // Stop any running layout first
      if (currentLayout.current) {
        try {
          currentLayout.current.stop();
        } catch (err) {
          console.warn('Error stopping previous layout:', err);
        }
      }

      // Validate layout name against available options
      const validLayouts = ['cose', 'circle', 'grid', 'breadthfirst', 'concentric'];
      const safeLayoutName = validLayouts.includes(layoutName) ? layoutName : 'cose';

      currentLayout.current = cyInstance.current.layout({
        name: safeLayoutName,
        animate: true,
        animationDuration: 500,
        fit: true,
        padding: 50,
        stop: function() {
          if (cyInstance.current && isMounted.current) {
            try {
              cyInstance.current.fit();
            } catch (err) {
              console.warn('Error fitting graph after layout stop:', err);
            }
          }
        },
        // Generic layout configurations
        ...(safeLayoutName === 'cose' && {
          nodeOverlap: 20,
          refresh: 20,
          randomize: false,
          componentSpacing: 100,
          nodeRepulsion: 400000,
          idealEdgeLength: 100,
          edgeElasticity: 100,
          nestingFactor: 5,
          gravity: 80,
          numIter: 1000,
          initialTemp: 200,
          coolingFactor: 0.95,
          minTemp: 1.0,
        }),
        ...(safeLayoutName === 'circle' && {
          radius: Math.min(200, Math.max(100, graphData.nodes.length * 8)),
        }),
        ...(safeLayoutName === 'concentric' && {
          concentric: function (node: any) {
            return node.data('size');
          },
          levelWidth: function () {
            return 1;
          },
        }),
      } as any);
      currentLayout.current.run();
    }
    setSelectedLayout(layoutName);
  };

  const toggleLabels = (type: 'nodes' | 'relationships') => {
    if (!cyInstance.current) return;

    if (type === 'nodes') {
      setShowNodeLabels(!showNodeLabels);
      cyInstance.current.nodes().forEach((node) => {
        const data = node.data();
        node.data('label', !showNodeLabels ? getDisplayLabel(data) : '');
      });
    } else {
      setShowRelationshipLabels(!showRelationshipLabels);
      cyInstance.current.edges().forEach((edge) => {
        const data = edge.data();
        edge.data('label', !showRelationshipLabels ? data.type : '');
      });
    }
  };

  const handleQuerySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeQuery(cypherQuery);
  };

  // Simplified query options - default shows everything
  const explorationQueries = [
    {
      name: 'Complete Graph',
      query: 'MATCH (n) OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m',
      description: 'Show ALL nodes and relationships (up to limit)',
    },
    {
      name: 'Limited (100)',
      query: 'MATCH (n) OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 100',
      description: 'Show first 100 nodes/relationships',
    },
    {
      name: 'Resolved Entities',
      query:
        'MATCH (entity)-[:RESOLVED_TO]->(re:ResolvedEntity) OPTIONAL MATCH (entity)-[r]-(m) RETURN entity, re, r, m',
      description: 'Show entities with resolution relationships',
    },
  ];

  const layoutOptions = [
    {
      value: 'cose',
      label: 'Force Physics',
      description: 'Smart force-directed layout with physics simulation',
    },
    { value: 'circle', label: 'Circular', description: 'Nodes arranged in circle' },
    { value: 'grid', label: 'Grid', description: 'Systematic grid arrangement' },
    { value: 'breadthfirst', label: 'Hierarchical', description: 'Tree-like hierarchy' },
    { value: 'concentric', label: 'Concentric', description: 'Layered by importance' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Graph Visualization</h1>
        <p className="mt-1 text-sm text-gray-600">
          Interactive visualization of all nodes and relationships in the Neo4j database. Shows
          complete graph structure with semantic IDs, QNames, and properties.
        </p>
      </div>

      {/* Entity Resolution Section */}
      <EntityResolutionPanel
        onResolutionComplete={(_response) => {
          // Refresh the graph to show resolved entities
          executeQuery(cypherQuery);
        }}
        onError={(error) => {
          console.error('Entity resolution error:', error);
        }}
      />

      {/* Query Input Section */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">Cypher Query</h3>
          <p className="mt-1 text-sm text-gray-600">
            Execute Cypher queries to explore your graph. Default query shows complete graph
            structure with all nodes, relationships, and properties.
          </p>
        </div>
        <div className="p-6">
          <form onSubmit={handleQuerySubmit} className="space-y-4">
            <div>
              <label htmlFor="cypher-query" className="block text-sm font-medium text-gray-700">
                Cypher Query
              </label>
              <textarea
                id="cypher-query"
                rows={3}
                className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm font-mono"
                value={cypherQuery}
                onChange={(e) => setCypherQuery(e.target.value)}
                placeholder="MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50"
              />
            </div>

            {/* Quick Query Options */}
            <div>
              <div className="block text-sm font-medium text-gray-700 mb-2">Quick Options</div>
              <div className="flex flex-wrap gap-2">
                {explorationQueries.map((query) => (
                  <button
                    key={query.name}
                    type="button"
                    onClick={() => setCypherQuery(query.query)}
                    className="inline-flex items-center px-3 py-1 border border-gray-300 shadow-sm text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50"
                    title={query.description}
                  >
                    {query.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Result Limit Control */}
            <div>
              <label
                htmlFor="result-limit"
                className="block text-sm font-medium text-gray-700 mb-2"
              >
                Result Limit
              </label>
              <div className="flex items-center gap-2">
                <input
                  id="result-limit"
                  type="number"
                  min="1"
                  max="100000"
                  step="1"
                  value={resultLimit}
                  onChange={(e) => {
                    const val = Number.parseInt(e.target.value);
                    if (!Number.isNaN(val) && val >= 1 && val <= 100000) {
                      setResultLimit(val);
                    }
                  }}
                  onBlur={(e) => {
                    const val = Number.parseInt(e.target.value);
                    if (Number.isNaN(val) || val < 1) {
                      setResultLimit(10000);
                    } else if (val > 100000) {
                      setResultLimit(100000);
                    }
                  }}
                  className="w-32 border-gray-300 rounded-md shadow-sm text-sm focus:ring-blue-500 focus:border-blue-500"
                  placeholder="1-100000"
                />
                <div className="flex flex-col text-xs text-gray-500">
                  <span>Any value 1-100,000</span>
                  <span className="text-gray-400">(larger values may impact performance)</span>
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={loading}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
              >
                {loading ? 'Loading...' : 'Execute Query'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error</h3>
              <p className="mt-2 text-sm text-red-700">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Graph Visualization */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-6 py-4 border-b border-gray-200 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Graph Visualization</h3>
              {graphData && (
                <p className="mt-1 text-sm text-gray-600">
                  {graphData.metadata.nodeCount} nodes ({graphData.metadata.nodeLabels.length}{' '}
                  types),
                  {graphData.metadata.relationshipCount} relationships (
                  {graphData.metadata.relationshipTypes.length} types)
                </p>
              )}
            </div>
            {loading && (
              <div className="flex items-center text-sm text-gray-500">
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-gray-500"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                Loading graph...
              </div>
            )}
          </div>

          {/* Graph Controls */}
          <div className="flex flex-wrap items-center gap-4 pt-2 border-t border-gray-200">
            {/* Filename Filter */}
            <div className="relative" ref={dropdownRef}>
              <button
                type="button"
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                className="px-3 py-1.5 text-left bg-white border border-gray-300 rounded-md shadow-sm text-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 flex items-center gap-2"
              >
                <span className="text-gray-700">
                  {filenameFilter.length === 0
                    ? `All files (${availableFiles.length})`
                    : `${filenameFilter.length} file${filenameFilter.length > 1 ? 's' : ''} selected`}
                </span>
                <svg className="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {/* Dropdown Menu */}
              {isDropdownOpen && (
                <div className="absolute z-10 mt-1 left-0 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto min-w-[300px]">
                  {/* Select All / Clear All */}
                  <div className="sticky top-0 bg-gray-50 border-b border-gray-200 px-3 py-2 flex justify-between items-center">
                    <button
                      type="button"
                      onClick={() => setFilenameFilter(availableFiles)}
                      className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                    >
                      Select All
                    </button>
                    <button
                      type="button"
                      onClick={() => setFilenameFilter([])}
                      className="text-xs text-gray-600 hover:text-gray-700 font-medium"
                    >
                      Clear All
                    </button>
                  </div>

                  {/* File Options */}
                  <div className="py-1">
                    {availableFiles.map((filename) => (
                      <label
                        key={filename}
                        className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={filenameFilter.includes(filename)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setFilenameFilter([...filenameFilter, filename]);
                            } else {
                              setFilenameFilter(filenameFilter.filter(f => f !== filename));
                            }
                          }}
                          className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                        />
                        <span className="ml-2 text-sm text-gray-700 truncate">{filename}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Layout Options */}
            <select
              value={selectedLayout}
              onChange={(e) => applyLayout(e.target.value)}
              className="border-gray-300 rounded-md shadow-sm text-sm focus:ring-blue-500 focus:border-blue-500 py-1.5"
            >
              {layoutOptions.map((option) => (
                <option key={option.value} value={option.value} title={option.description}>
                  {option.label}
                </option>
              ))}
            </select>

            {/* Node/Edge Label Toggles */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => toggleLabels('nodes')}
                className={`px-2 py-1 text-xs rounded ${showNodeLabels ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'}`}
              >
                Node Labels
              </button>
              <button
                type="button"
                onClick={() => toggleLabels('relationships')}
                className={`px-2 py-1 text-xs rounded ${showRelationshipLabels ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'}`}
              >
                Edge Labels
              </button>
            </div>

            {/* Zoom Controls */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  if (cyInstance.current) {
                    cyInstance.current.zoom(cyInstance.current.zoom() * 1.25);
                    cyInstance.current.center();
                  }
                }}
                className="px-2 py-1 text-xs rounded bg-gray-100 hover:bg-gray-200 text-gray-700"
                title="Zoom In"
              >
                Zoom +
              </button>
              <button
                type="button"
                onClick={() => {
                  if (cyInstance.current) {
                    cyInstance.current.zoom(cyInstance.current.zoom() * 0.75);
                    cyInstance.current.center();
                  }
                }}
                className="px-2 py-1 text-xs rounded bg-gray-100 hover:bg-gray-200 text-gray-700"
                title="Zoom Out"
              >
                Zoom -
              </button>
              <button
                type="button"
                onClick={() => {
                  if (cyInstance.current) {
                    cyInstance.current.fit();
                    cyInstance.current.center();
                  }
                }}
                className="px-2 py-1 text-xs rounded bg-green-100 hover:bg-green-200 text-green-700 font-medium"
                title="Fit all nodes to screen"
              >
                Fit to Screen
              </button>
            </div>

            {/* Show Resolved Entities Toggle - Far Right */}
            <label className="flex items-center space-x-2 cursor-pointer ml-auto">
              <input
                type="checkbox"
                checked={showResolvedEntities}
                onChange={(e) => setShowResolvedEntities(e.target.checked)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <span className="text-sm font-medium text-gray-700">Show Resolved Entities</span>
            </label>
          </div>
        </div>

        <div className="p-6">
          <div className="flex gap-6">
            {/* Graph Visualization */}
            <div className="flex-1">
              <div
                className="bg-gray-50 rounded-lg border-2 border-gray-200"
                style={{ height: '600px' }}
              >
                <div id="graph-viz" ref={cyRef} className="w-full h-full rounded-lg" />
              </div>
            </div>

            {/* Universal Legend Panel */}
            <div className="w-64 bg-gray-50 rounded-lg p-4">
              {graphData && (
                <>
                  <h4 className="text-sm font-semibold text-gray-900 mb-3">
                    Node Types ({graphData.metadata.nodeLabels.length})
                  </h4>
                  <div className="space-y-2 text-xs max-h-48 overflow-y-auto">
                    {graphData.metadata.nodeLabels.map((label, index) => {
                      const colors = generateDistinguishableColors(
                        graphData.metadata.nodeLabels.length
                      );
                      const color = colors[index];
                      return (
                        <div key={label} className="flex items-center gap-2">
                          <div
                            className="w-3 h-3 rounded-full border border-gray-300 flex-shrink-0"
                            style={{ backgroundColor: color }}
                          ></div>
                          <span className="truncate" title={label}>
                            {label}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  <h4 className="text-sm font-semibold text-gray-900 mt-4 mb-3">
                    Relationships ({graphData.metadata.relationshipTypes.length})
                  </h4>
                  <div className="space-y-2 text-xs max-h-40 overflow-y-auto">
                    {graphData.metadata.relationshipTypes.map((type, index) => {
                      const colors = generateDistinguishableColors(
                        graphData.metadata.relationshipTypes.length
                      );
                      const color = colors[index];
                      return (
                        <div key={type} className="flex items-center gap-2">
                          <div
                            className="w-4 h-0.5 flex-shrink-0"
                            style={{ backgroundColor: color }}
                          ></div>
                          <span className="truncate" title={type}>
                            {type}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}

              <div className="mt-4 pt-3 border-t border-gray-200">
                <p className="text-xs text-gray-600">
                  <strong>Controls:</strong>
                  <br />
                  • Click: View details in console
                  <br />
                  • Drag: Pan view
                  <br />
                  • Scroll: Zoom in/out
                  <br />
                  • Toggle labels on/off
                  <br />• Change layouts dynamically
                </p>
              </div>
            </div>
          </div>

          <div className="mt-4 text-xs text-gray-500">
            <p>
              <strong>Universal Graph Visualization</strong> - Shows ALL nodes and relationships
              from Neo4j, matching Neo4j Browser capabilities. Click nodes/edges for full details
              including semantic IDs, QNames, and augmentation properties. Drag to pan, scroll to
              zoom.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
