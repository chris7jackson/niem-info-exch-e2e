import React, { useState, useEffect } from 'react';
import { ElementTreeNode, ElementTreeResponse, ApplyDesignResponse, SchemaValidationMessage, apiClient } from '../lib/api';
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
  const [validationErrors, setValidationErrors] = useState<SchemaValidationMessage[]>([]);
  const [validationWarnings, setValidationWarnings] = useState<SchemaValidationMessage[]>([]);

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

      // Try to load saved selections and merge them
      try {
        const savedSelections = await apiClient.getSchemaSelections(schemaId);
        if (savedSelections) {
          // Merge saved selections with initial selections
          // Saved selections take precedence
          Object.keys(savedSelections).forEach((qname) => {
            if (qname in initialSelections) {
              initialSelections[qname] = savedSelections[qname];
            }
          });
        }
      } catch (err) {
        console.log('No saved selections found, using defaults');
      }

      setSelections(initialSelections);
    } catch (err: any) {
      console.error('Failed to fetch element tree:', err);
      setError(err.response?.data?.detail || 'Failed to load schema structure');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectionChange = (qname: string, selected: boolean) => {
    setSelections((prev) => {
      const newSelections = {
        ...prev,
        [qname]: selected,
      };

      // Auto-select association endpoints when association is selected
      if (selected && elementTree) {
        const node = elementTree.nodes.find(n => n.qname === qname);
        if (node && node.node_type === 'association' && node.endpoints) {
          // Auto-select all entity endpoints (property wrappers already filtered out)
          node.endpoints.forEach((endpointQname: string) => {
            newSelections[endpointQname] = true;
          });
        }
      }

      return newSelections;
    });
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
    setValidationErrors([]);
    setValidationWarnings([]);

    try {
      const response = await apiClient.applySchemaDesign(schemaId, selections);

      // Check if validation failed
      if (!response.can_proceed && response.errors) {
        setValidationErrors(response.errors);
        setIsApplying(false);
        return;
      }

      // Check if there are warnings
      if (response.warnings && response.warnings.length > 0) {
        setValidationWarnings(response.warnings);
        setIsApplying(false);
        return;
      }

      // Success - no errors or warnings
      onClose(true);
    } catch (err: any) {
      console.error('Failed to apply schema design:', err);
      const errorData = err.response?.data;

      // Check if it's a validation error response
      if (errorData?.errors) {
        setValidationErrors(errorData.errors);
      } else {
        setError(errorData?.detail || 'Failed to apply design');
      }
      setIsApplying(false);
    }
  };

  const handleProceedWithWarnings = async () => {
    // User acknowledged warnings, proceed with application
    setValidationWarnings([]);
    onClose(true);
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

        {/* Validation Errors Display */}
        {validationErrors.length > 0 && (
          <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg max-h-[60vh] flex flex-col">
            <div className="flex items-start mb-3">
              <svg className="w-5 h-5 text-red-500 mt-0.5 mr-3" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <div className="flex-1">
                <p className="text-sm font-medium text-red-800">Validation Failed ({validationErrors.length} issue{validationErrors.length !== 1 ? 's' : ''})</p>
                <p className="text-sm text-red-700 mt-1">Please fix the following issues before applying:</p>
              </div>
            </div>
            <div className="space-y-2 ml-8 overflow-y-auto flex-1 max-h-[40vh] pr-2">
              {validationErrors.map((err, idx) => (
                <div key={idx} className="text-sm">
                  <p className="font-medium text-red-800">{err.message}</p>
                  {err.recommendation && (
                    <p className="text-red-700 mt-1">💡 {err.recommendation}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Validation Warnings Display */}
        {validationWarnings.length > 0 && (
          <div className="mx-6 mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg max-h-[60vh] flex flex-col">
            <div className="flex items-start mb-3">
              <svg className="w-5 h-5 text-yellow-500 mt-0.5 mr-3" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <div className="flex-1">
                <p className="text-sm font-medium text-yellow-800">Design Warnings ({validationWarnings.length})</p>
                <p className="text-sm text-yellow-700 mt-1">The following issues may affect analysis quality:</p>
              </div>
            </div>
            <div className="space-y-3 ml-8 mb-4 overflow-y-auto flex-1 max-h-[40vh] pr-2">
              {validationWarnings.map((warn, idx) => (
                <div key={idx} className="text-sm">
                  <p className="font-medium text-yellow-800">{warn.message}</p>
                  {warn.recommendation && (
                    <p className="text-yellow-700 mt-1">💡 {warn.recommendation}</p>
                  )}
                  {warn.impact && (
                    <p className="text-xs text-yellow-600 mt-1">Impact: {warn.impact}</p>
                  )}
                </div>
              ))}
            </div>
            <div className="ml-8 flex space-x-3 pt-2 border-t border-yellow-200">
              <button
                onClick={() => setValidationWarnings([])}
                className="px-3 py-1.5 text-sm font-medium text-yellow-700 bg-white border border-yellow-300 rounded-md hover:bg-yellow-50"
              >
                Go Back
              </button>
              <button
                onClick={handleProceedWithWarnings}
                className="px-3 py-1.5 text-sm font-medium text-white bg-yellow-600 border border-transparent rounded-md hover:bg-yellow-700"
              >
                Proceed Anyway
              </button>
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
              <SchemaNodeInspector selectedNode={selectedNode} selections={selections} />
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
