import { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';

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

// Data-agnostic color generation using HSL for consistent, distinguishable colors
const generateDistinguishableColors = (count: number): string[] => {
  const colors: string[] = [];
  const saturation = 70; // Good saturation for visibility
  const lightness = 50;  // Good lightness for contrast

  for (let i = 0; i < count; i++) {
    const hue = (i * 360 / count) % 360;
    colors.push(`hsl(${hue}, ${saturation}%, ${lightness}%)`);
  }

  return colors;
};

// Data-agnostic relationship styling based on frequency and type
const getRelationshipStyle = (relationshipType: string, allTypes: string[]) => {
  const typeIndex = allTypes.indexOf(relationshipType);
  const baseColors = ['#2E3440', '#3B4252', '#434C5E', '#4C566A', '#5E81AC', '#81A1C1', '#88C0D0', '#8FBCBB'];

  return {
    color: baseColors[typeIndex % baseColors.length],
    width: relationshipType.includes('CONTAINS') || relationshipType.includes('HAS') ? 1 : 2,
    style: relationshipType.includes('CONTAINS') || relationshipType.includes('PART_OF') ? 'dashed' : 'solid',
    opacity: relationshipType.includes('CONTAINS') ? 0.6 : 0.8
  };
};

// Data-agnostic node sizing based on connectivity
const getNodeSize = (node: GraphNode, relationships: GraphRelationship[]): number => {
  const connections = relationships.filter(rel =>
    rel.startNode === node.id || rel.endNode === node.id
  ).length;

  // Base size + scaling factor for connections
  return Math.max(30, Math.min(80, 30 + (connections * 3)));
};

// Data-agnostic label display prioritizing meaningful content
const getDisplayLabel = (node: GraphNode): string => {
  const props = node.properties;

  // Priority order for meaningful labels
  const labelPriority = [
    'name', 'title', 'label', 'id', 'identifier',
    'content', 'text', 'value', 'description',
    'xml_tag', 'tag', 'type'
  ];

  // Find the best property to display
  for (const key of labelPriority) {
    if (props[key] && typeof props[key] === 'string') {
      const value = props[key].toString();
      if (value.length > 0) {
        return value.length > 20 ? value.substring(0, 20) + '...' : value;
      }
    }
  }

  // Fallback to node label
  return node.label || node.labels[0] || `Node ${node.id}`;
};

export default function GraphPage() {
  const cyRef = useRef<HTMLDivElement>(null);
  const cyInstance = useRef<cytoscape.Core | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cypherQuery, setCypherQuery] = useState('MATCH (n) OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 200');
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [selectedLayout, setSelectedLayout] = useState('cose');
  const [showNodeLabels, setShowNodeLabels] = useState(true);
  const [showRelationshipLabels, setShowRelationshipLabels] = useState(true);

  useEffect(() => {
    loadInitialGraph();
  }, []);

  const loadInitialGraph = async () => {
    await executeQuery(cypherQuery);
  };

  const executeQuery = async (query: string) => {
    setLoading(true);
    setError(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/graph/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token') || 'devtoken'}`
        },
        body: JSON.stringify({ query, limit: 100 })
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
    if (!cyRef.current) return;

    // Generate data-agnostic colors
    const nodeColors = generateDistinguishableColors(data.metadata.nodeLabels.length);
    const labelColorMap: Record<string, string> = {};
    data.metadata.nodeLabels.forEach((label, index) => {
      labelColorMap[label] = nodeColors[index];
    });

    // Convert nodes to Cytoscape format with data-agnostic styling
    const cyNodes = data.nodes.map(node => {
      const displayLabel = getDisplayLabel(node);
      const nodeSize = getNodeSize(node, data.relationships);

      return {
        data: {
          id: node.id,
          label: showNodeLabels ? displayLabel : '',
          nodeType: node.label,
          nodeLabels: node.labels,
          properties: node.properties,
          color: labelColorMap[node.label] || '#95A5A6',
          size: nodeSize,
          // Tooltip with all available info
          tooltip: `${node.labels.join(', ')}\nID: ${node.id}\nProperties: ${Object.keys(node.properties).length} items`
        }
      };
    });

    // Convert relationships to Cytoscape format with data-agnostic styling
    const cyEdges = data.relationships.map(rel => {
      const relStyle = getRelationshipStyle(rel.type, data.metadata.relationshipTypes);

      return {
        data: {
          id: rel.id,
          source: rel.startNode,
          target: rel.endNode,
          label: showRelationshipLabels ? rel.type : '',
          type: rel.type,
          properties: rel.properties,
          color: relStyle.color,
          width: relStyle.width,
          lineStyle: relStyle.style,
          opacity: relStyle.opacity,
          tooltip: `${rel.type}\nID: ${rel.id}\nProperties: ${Object.keys(rel.properties).length} items`
        }
      };
    });

    // Destroy existing instance
    if (cyInstance.current) {
      cyInstance.current.destroy();
    }

    // Create new Cytoscape instance with data-agnostic styles
    cyInstance.current = cytoscape({
      container: cyRef.current,

      elements: [
        ...cyNodes,
        ...cyEdges
      ],

      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'color': '#000000',
            'text-outline-width': 2,
            'text-outline-color': '#ffffff',
            'font-size': '9px',
            'font-weight': 'bold',
            'width': 'data(size)',
            'height': 'data(size)',
            'border-width': 1,
            'border-color': '#333333',
            'text-wrap': 'wrap',
            'text-max-width': '60px'
          }
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 3,
            'border-color': '#FFA500',
            'text-outline-color': '#FFA500'
          }
        },
        {
          selector: 'node:hover',
          style: {
            'border-width': 2,
            'border-color': '#FF6B35'
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 'data(width)',
            'line-color': 'data(color)',
            'target-arrow-color': 'data(color)',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': '8px',
            'color': '#444444',
            'text-outline-width': 1,
            'text-outline-color': '#ffffff',
            'opacity': 'data(opacity)' as any,
            'line-style': 'data(lineStyle)' as any
          }
        },
        {
          selector: 'edge:selected',
          style: {
            'width': 3,
            'line-color': '#FFA500',
            'target-arrow-color': '#FFA500'
          }
        },
        {
          selector: 'edge:hover',
          style: {
            'width': 3,
            'opacity': 1
          }
        }
      ],

      layout: {
        name: selectedLayout as any,
        animate: true,
        animationDuration: 1000,
        fit: true,
        padding: 50,
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
          minTemp: 1.0
        }),
        ...(selectedLayout === 'cola' && {
          nodeSpacing: 10,
          edgeLengthVal: 100,
          animate: true,
          randomize: false,
          maxSimulationTime: 4000
        }),
        ...(selectedLayout === 'circle' && {
          radius: Math.min(200, Math.max(100, data.nodes.length * 8))
        }),
        ...(selectedLayout === 'concentric' && {
          concentric: function(node: any) {
            return node.data('size'); // Arrange by connectivity
          },
          levelWidth: function() {
            return 1;
          }
        })
      } as any
    });

    // Data-agnostic event handlers
    cyInstance.current.on('tap', 'node', function(evt) {
      const node = evt.target;
      const data = node.data();
      console.log('=== Node Details ===');
      console.log('Type:', data.nodeType);
      console.log('Labels:', data.nodeLabels);
      console.log('ID:', data.id);
      console.log('Properties:', data.properties);
      console.log('==================');
    });

    cyInstance.current.on('tap', 'edge', function(evt) {
      const edge = evt.target;
      const data = edge.data();
      console.log('=== Relationship Details ===');
      console.log('Type:', data.type);
      console.log('ID:', data.id);
      console.log('From:', data.source, '→', data.target);
      console.log('Properties:', data.properties);
      console.log('===========================');
    });

    // Fit to viewport
    cyInstance.current.fit();
  };

  const applyLayout = (layoutName: string) => {
    if (cyInstance.current && graphData) {
      const layout = cyInstance.current.layout({
        name: layoutName,
        animate: true,
        animationDuration: 1000,
        fit: true,
        padding: 50,
        // Generic layout configurations
        ...(layoutName === 'cose' && {
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
          minTemp: 1.0
        }),
        ...(layoutName === 'cola' && {
          nodeSpacing: 10,
          edgeLengthVal: 100,
          animate: true,
          randomize: false,
          maxSimulationTime: 4000
        }),
        ...(layoutName === 'circle' && {
          radius: Math.min(200, Math.max(100, graphData.nodes.length * 8))
        }),
        ...(layoutName === 'concentric' && {
          concentric: function(node: any) {
            return node.data('size');
          },
          levelWidth: function() {
            return 1;
          }
        })
      } as any);
      layout.run();
    }
    setSelectedLayout(layoutName);
  };

  const toggleLabels = (type: 'nodes' | 'relationships') => {
    if (!cyInstance.current) return;

    if (type === 'nodes') {
      setShowNodeLabels(!showNodeLabels);
      cyInstance.current.nodes().forEach(node => {
        const data = node.data();
        node.data('label', !showNodeLabels ? getDisplayLabel(data) : '');
      });
    } else {
      setShowRelationshipLabels(!showRelationshipLabels);
      cyInstance.current.edges().forEach(edge => {
        const data = edge.data();
        edge.data('label', !showRelationshipLabels ? data.type : '');
      });
    }
  };

  const handleQuerySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeQuery(cypherQuery);
  };

  // Complete data access queries - NO data loss
  const explorationQueries = [
    {
      name: 'Show Everything',
      query: 'MATCH (n) OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m',
      description: 'Complete graph - all nodes and all relationships (no limits)'
    },
    {
      name: 'Full Graph (500)',
      query: 'MATCH (n) OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 500',
      description: 'Complete graph structure with reasonable limit'
    },
    {
      name: 'All Relationships',
      query: 'MATCH (a)-[r]->(b) RETURN a, r, b',
      description: 'Every relationship with connected nodes (no limits)'
    },
    {
      name: 'Complete Paths',
      query: 'MATCH path = (a)-[*1..5]-(b) WHERE a <> b RETURN path LIMIT 100',
      description: 'All paths up to 5 hops between different nodes'
    },
    {
      name: 'Quick Overview',
      query: 'MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50',
      description: 'Basic sample for large databases'
    }
  ];

  const layoutOptions = [
    { value: 'cose', label: 'Force Physics', description: 'Smart force-directed layout' },
    { value: 'cola', label: 'Force Simulation', description: 'Advanced force-directed' },
    { value: 'circle', label: 'Circular', description: 'Nodes arranged in circle' },
    { value: 'grid', label: 'Grid', description: 'Systematic grid arrangement' },
    { value: 'breadthfirst', label: 'Hierarchical', description: 'Tree-like hierarchy' },
    { value: 'concentric', label: 'Concentric', description: 'Layered by importance' }
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Universal Graph Explorer</h1>
        <p className="mt-1 text-sm text-gray-600">
          Data-agnostic graph visualization for any Neo4j dataset. Explore nodes and relationships dynamically.
        </p>
      </div>

      {/* Query Input Section */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">Cypher Query</h3>
          <p className="mt-1 text-sm text-gray-600">
            Explore your data using Cypher patterns. Choose from exploration templates or write custom queries.
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

            {/* Exploration Query Templates */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Exploration Patterns
              </label>
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

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <select
                  value={selectedLayout}
                  onChange={(e) => applyLayout(e.target.value)}
                  className="border-gray-300 rounded-md shadow-sm text-sm focus:ring-blue-500 focus:border-blue-500"
                >
                  {layoutOptions.map(option => (
                    <option key={option.value} value={option.value} title={option.description}>
                      {option.label}
                    </option>
                  ))}
                </select>

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
              </div>

              <button
                type="submit"
                disabled={loading}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
              >
                {loading ? 'Executing...' : 'Execute Query'}
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
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Query Error</h3>
              <p className="mt-2 text-sm text-red-700">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Graph Visualization */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Graph Visualization</h3>
              {graphData && (
                <p className="mt-1 text-sm text-gray-600">
                  {graphData.metadata.nodeCount} nodes ({graphData.metadata.nodeLabels.length} types),
                  {graphData.metadata.relationshipCount} relationships ({graphData.metadata.relationshipTypes.length} types)
                </p>
              )}
            </div>
            {loading && (
              <div className="flex items-center text-sm text-gray-500">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Loading graph...
              </div>
            )}
          </div>
        </div>

        <div className="p-6">
          <div className="flex gap-6">
            {/* Graph Visualization */}
            <div className="flex-1">
              <div className="bg-gray-50 rounded-lg border-2 border-gray-200" style={{ height: '600px' }}>
                <div
                  id="graph-viz"
                  ref={cyRef}
                  className="w-full h-full rounded-lg"
                />
              </div>
            </div>

            {/* Dynamic Legend Panel */}
            <div className="w-64 bg-gray-50 rounded-lg p-4">
              {graphData && (
                <>
                  <h4 className="text-sm font-semibold text-gray-900 mb-3">
                    Node Types ({graphData.metadata.nodeLabels.length})
                  </h4>
                  <div className="space-y-2 text-xs max-h-48 overflow-y-auto">
                    {graphData.metadata.nodeLabels.map((label, index) => {
                      const colors = generateDistinguishableColors(graphData.metadata.nodeLabels.length);
                      const color = colors[index];
                      return (
                        <div key={label} className="flex items-center gap-2">
                          <div
                            className="w-3 h-3 rounded-full border border-gray-300"
                            style={{ backgroundColor: color }}
                          ></div>
                          <span className="truncate">{label}</span>
                        </div>
                      );
                    })}
                  </div>

                  <h4 className="text-sm font-semibold text-gray-900 mt-4 mb-3">
                    Relationships ({graphData.metadata.relationshipTypes.length})
                  </h4>
                  <div className="space-y-2 text-xs max-h-32 overflow-y-auto">
                    {graphData.metadata.relationshipTypes.map((type) => {
                      const style = getRelationshipStyle(type, graphData.metadata.relationshipTypes);
                      return (
                        <div key={type} className="flex items-center gap-2">
                          <div
                            className={`w-4 h-0.5 ${style.style === 'dashed' ? 'border-dashed border-t border-gray-600' : ''}`}
                            style={{
                              backgroundColor: style.style === 'solid' ? style.color : 'transparent',
                              borderColor: style.style === 'dashed' ? style.color : 'transparent'
                            }}
                          ></div>
                          <span className="truncate">{type}</span>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}

              <div className="mt-4 pt-3 border-t border-gray-200">
                <p className="text-xs text-gray-600">
                  <strong>Controls:</strong><br/>
                  • Click: View details in console<br/>
                  • Drag: Pan view<br/>
                  • Scroll: Zoom in/out<br/>
                  • Toggle labels on/off<br/>
                  • Change layouts dynamically
                </p>
              </div>
            </div>
          </div>

          <div className="mt-4 text-xs text-gray-500">
            <p>
              <strong>Universal Neo4j Visualization</strong> - Adapts to any graph structure with data-driven styling and layout optimization.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}