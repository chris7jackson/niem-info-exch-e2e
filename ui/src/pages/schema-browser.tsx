'use client';

import { useState, useEffect } from 'react';
import apiClient, { SchemaGraph as SchemaGraphData, GraphNode, Schema } from '@/lib/api';
import SchemaGraph from '@/components/SchemaGraph';
import SchemaDetailPanel from '@/components/SchemaDetailPanel';
import SchemaFilters from '@/components/SchemaFilters';
import { ChevronDownIcon, ArrowsPointingOutIcon, ArrowPathIcon } from '@heroicons/react/24/outline';

export default function SchemaBrowser() {
  // State management
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [selectedSchemaId, setSelectedSchemaId] = useState<string>('');
  const [graphData, setGraphData] = useState<SchemaGraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Graph view state
  const [layout, setLayout] = useState<'tree' | 'force'>('tree');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

  // Filter state
  const [selectedNamespaces, setSelectedNamespaces] = useState<string[]>([]);
  const [selectedNodeTypes, setSelectedNodeTypes] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [maxDepth, setMaxDepth] = useState(10);

  // Load schemas on mount
  useEffect(() => {
    loadSchemas();
  }, []);

  // Initialize filters when graph data loads
  useEffect(() => {
    if (graphData) {
      // Select all namespaces and node types by default
      setSelectedNamespaces(graphData.namespaces.map(ns => ns.prefix));
      const nodeTypes = Array.from(new Set(graphData.nodes.map(n => n.nodeType)));
      setSelectedNodeTypes(nodeTypes);
    }
  }, [graphData]);

  const loadSchemas = async () => {
    try {
      const data = await apiClient.getSchemas();
      setSchemas(data);

      // Auto-select active schema if available
      const activeSchema = data.find((s: Schema) => s.active);
      if (activeSchema) {
        setSelectedSchemaId(activeSchema.schema_id);
        loadSchemaGraph(activeSchema.schema_id);
      }
    } catch (err: any) {
      setError('Failed to load schemas');
      console.error(err);
    }
  };

  const loadSchemaGraph = async (schemaId: string) => {
    if (!schemaId) return;

    setLoading(true);
    setError(null);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);

    try {
      const data = await apiClient.getSchemaGraph(schemaId);
      setGraphData(data);
    } catch (err: any) {
      if (err.response?.status === 404) {
        setError('Schema not found. It may have been deleted.');
      } else if (err.response?.status === 500) {
        setError('Failed to parse schema. The schema file may be corrupted.');
      } else if (err.response?.status === 503) {
        setError('Storage service temporarily unavailable. Please try again.');
      } else {
        setError('Failed to load schema graph');
      }
      console.error(err);
      setGraphData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSchemaChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const schemaId = e.target.value;
    setSelectedSchemaId(schemaId);
    if (schemaId) {
      loadSchemaGraph(schemaId);
    } else {
      setGraphData(null);
    }
  };

  const handleNodeSelect = (nodeId: string | null) => {
    setSelectedNodeId(nodeId);
    setSelectedEdgeId(null);
  };

  const handleEdgeSelect = (edgeId: string | null) => {
    setSelectedEdgeId(edgeId);
    // Could show edge details in future
  };

  const handleNavigateToNode = (nodeId: string) => {
    setSelectedNodeId(nodeId);
    // Could also zoom/pan to node in graph
  };

  const handleClearFilters = () => {
    if (graphData) {
      setSelectedNamespaces(graphData.namespaces.map(ns => ns.prefix));
      const nodeTypes = Array.from(new Set(graphData.nodes.map(n => n.nodeType)));
      setSelectedNodeTypes(nodeTypes);
      setSearchTerm('');
      setMaxDepth(10);
    }
  };

  const handleFitToScreen = () => {
    // TODO: Implement fit to screen in SchemaGraph component
    console.log('Fit to screen');
  };

  const handleRefresh = () => {
    if (selectedSchemaId) {
      loadSchemaGraph(selectedSchemaId);
    }
  };

  const selectedNode = graphData && selectedNodeId
    ? graphData.nodes.find(n => n.id === selectedNodeId) || null
    : null;

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 shadow-sm">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">Schema Browser</h1>
            <div className="flex items-center gap-4">
              {graphData && (
                <div className="text-sm text-gray-600">
                  {graphData.metadata.totalNodes} nodes · {graphData.metadata.totalEdges} edges · {graphData.metadata.namespaceCount} namespaces
                </div>
              )}
            </div>
          </div>

          {/* Schema Selector */}
          <div className="mt-4 flex items-center gap-4">
            <div className="flex-1 max-w-md">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Select Schema
              </label>
              <div className="relative">
                <select
                  value={selectedSchemaId}
                  onChange={handleSchemaChange}
                  className="block w-full pl-3 pr-10 py-2 text-base border border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 rounded-md appearance-none bg-white"
                >
                  <option value="">Select a schema...</option>
                  {schemas.map((schema) => (
                    <option key={schema.schema_id} value={schema.schema_id}>
                      {schema.primary_filename || schema.schema_id.substring(0, 8)}{' '}
                      {schema.active && '(Active)'} · {new Date(schema.uploaded_at).toLocaleDateString()}
                    </option>
                  ))}
                </select>
                <div className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
                  <ChevronDownIcon className="h-5 w-5 text-gray-400" />
                </div>
              </div>
            </div>

            {/* Layout Toggle */}
            {graphData && (
              <div className="flex items-end gap-2">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Layout
                  </label>
                  <div className="flex rounded-md shadow-sm">
                    <button
                      onClick={() => setLayout('tree')}
                      className={`px-4 py-2 text-sm font-medium rounded-l-md border ${
                        layout === 'tree'
                          ? 'bg-blue-600 text-white border-blue-600'
                          : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                      }`}
                    >
                      Tree
                    </button>
                    <button
                      onClick={() => setLayout('force')}
                      className={`px-4 py-2 text-sm font-medium rounded-r-md border-t border-r border-b ${
                        layout === 'force'
                          ? 'bg-blue-600 text-white border-blue-600'
                          : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                      }`}
                    >
                      Force
                    </button>
                  </div>
                </div>

                {/* Action Buttons */}
                <button
                  onClick={handleFitToScreen}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 flex items-center gap-2"
                  title="Fit to screen"
                >
                  <ArrowsPointingOutIcon className="h-4 w-4" />
                  Fit
                </button>
                <button
                  onClick={handleRefresh}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 flex items-center gap-2"
                  title="Refresh"
                >
                  <ArrowPathIcon className="h-4 w-4" />
                  Refresh
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {loading && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
              <p className="text-gray-600">Loading schema graph...</p>
            </div>
          </div>
        )}

        {error && !loading && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center max-w-md">
              <div className="bg-red-50 border border-red-200 rounded-lg p-6">
                <h3 className="text-lg font-medium text-red-900 mb-2">Error Loading Schema</h3>
                <p className="text-sm text-red-700">{error}</p>
                <button
                  onClick={() => selectedSchemaId && loadSchemaGraph(selectedSchemaId)}
                  className="mt-4 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm font-medium"
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        )}

        {!loading && !error && !graphData && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center max-w-md">
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Schema Selected</h3>
              <p className="text-sm text-gray-600">
                Select a schema from the dropdown above to visualize its structure.
              </p>
            </div>
          </div>
        )}

        {!loading && !error && graphData && (
          <>
            {/* Filters */}
            <SchemaFilters
              namespaces={graphData.namespaces}
              nodes={graphData.nodes}
              selectedNamespaces={selectedNamespaces}
              selectedNodeTypes={selectedNodeTypes}
              searchTerm={searchTerm}
              maxDepth={maxDepth}
              onNamespaceChange={setSelectedNamespaces}
              onNodeTypeChange={setSelectedNodeTypes}
              onSearchChange={setSearchTerm}
              onDepthChange={setMaxDepth}
              onClearFilters={handleClearFilters}
            />

            {/* Graph Canvas */}
            <div className="flex-1 overflow-hidden">
              <SchemaGraph
                nodes={graphData.nodes}
                edges={graphData.edges}
                namespaces={graphData.namespaces}
                layout={layout}
                selectedNodeId={selectedNodeId}
                onNodeSelect={handleNodeSelect}
                onEdgeSelect={handleEdgeSelect}
                filterNamespaces={selectedNamespaces}
                filterNodeTypes={selectedNodeTypes}
                searchTerm={searchTerm}
                maxDepth={maxDepth}
              />
            </div>

            {/* Detail Panel */}
            {selectedNode && (
              <SchemaDetailPanel
                node={selectedNode}
                edges={graphData.edges}
                onClose={() => setSelectedNodeId(null)}
                onNavigate={handleNavigateToNode}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
