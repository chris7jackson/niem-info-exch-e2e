import React, { useState, useEffect } from 'react';
import { ElementTreeNode, ElementTreeResponse, ApplyDesignResponse, apiClient } from '../lib/api';
import SchemaElementTree from './SchemaElementTree';
import SchemaNodeInspector from './SchemaNodeInspector';

interface GraphSchemaDesignerProps {
  schemaId: string;
  open: boolean;
  onClose: (applied: boolean) => void;
}

const GraphSchemaDesigner: React.FC<GraphSchemaDesignerProps> = ({ schemaId, open, onClose }) => {
  const [elementTree, setElementTree] = useState<ElementTreeResponse | null>(null);
  const [selections, setSelections] = useState<Record<string, boolean>>({});
  const [selectedNode, setSelectedNode] = useState<ElementTreeNode | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch element tree when modal opens
  useEffect(() => {
    if (open && schemaId) {
      fetchElementTree();
    }
  }, [open, schemaId]);

  const fetchElementTree = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.getElementTree(schemaId);
      setElementTree(response);

      // Initialize selections from nodes (all selected by default)
      const initialSelections: Record<string, boolean> = {};
      response.nodes.forEach((node) => {
        initialSelections[node.qname] = node.selected;
      });
      setSelections(initialSelections);
    } catch (err: any) {
      console.error('Failed to fetch element tree:', err);
      setError(err.response?.data?.detail || 'Failed to load schema structure');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectionChange = (qname: string, selected: boolean) => {
    setSelections((prev) => ({
      ...prev,
      [qname]: selected,
    }));
  };

  const handleNodeClick = (node: ElementTreeNode) => {
    setSelectedNode(node);
  };

  const handleSkip = () => {
    onClose(false);
  };

  const handleApply = async () => {
    setIsApplying(true);
    setError(null);

    try {
      await apiClient.applySchemaDesign(schemaId, selections);
      onClose(true);
    } catch (err: any) {
      console.error('Failed to apply schema design:', err);
      setError(err.response?.data?.detail || 'Failed to apply design');
      setIsApplying(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-75 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full h-full max-w-7xl max-h-[90vh] flex flex-col m-4">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Design Graph Schema</h2>
            <p className="text-sm text-gray-600 mt-1">
              Select which elements should become Neo4j nodes. Unselected elements will be flattened as properties.
            </p>
            {elementTree && (
              <p className="text-xs text-gray-500 mt-1">
                Schema: {elementTree.metadata.schema_name || schemaId} • {elementTree.total_nodes} elements
              </p>
            )}
          </div>
          <button
            onClick={handleSkip}
            className="text-gray-400 hover:text-gray-600 focus:outline-none"
            disabled={isApplying}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start">
            <svg className="w-5 h-5 text-red-500 mt-0.5 mr-3" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            <div className="flex-1">
              <p className="text-sm font-medium text-red-800">Error</p>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <p className="mt-4 text-gray-600">Loading schema structure...</p>
            </div>
          </div>
        )}

        {/* Content: Split View */}
        {!isLoading && elementTree && (
          <div className="flex-1 flex overflow-hidden">
            {/* Left: Tree */}
            <div className="w-1/2 border-r border-gray-200 overflow-hidden">
              <SchemaElementTree
                nodes={elementTree.nodes}
                selections={selections}
                onSelectionChange={handleSelectionChange}
                onNodeClick={handleNodeClick}
                selectedNodeQname={selectedNode?.qname || null}
              />
            </div>

            {/* Right: Inspector */}
            <div className="w-1/2 overflow-hidden">
              <SchemaNodeInspector selectedNode={selectedNode} />
            </div>
          </div>
        )}

        {/* Footer: Actions */}
        {!isLoading && elementTree && (
          <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between bg-gray-50">
            <div className="text-sm text-gray-600">
              <p>
                <strong>{Object.values(selections).filter(Boolean).length}</strong> elements selected
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Tip: Select nodes you want to query independently. Unselected nodes will be flattened.
              </p>
            </div>
            <div className="flex space-x-3">
              <button
                onClick={handleSkip}
                disabled={isApplying}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
              >
                Skip (Use Defaults)
              </button>
              <button
                onClick={handleApply}
                disabled={isApplying}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 flex items-center"
              >
                {isApplying ? (
                  <>
                    <div className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Applying...
                  </>
                ) : (
                  'Apply Design'
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GraphSchemaDesigner;
