import React from 'react';
import { ElementTreeNode } from '../lib/api';

interface SchemaNodeInspectorProps {
  selectedNode: ElementTreeNode | null;
}

const SchemaNodeInspector: React.FC<SchemaNodeInspectorProps> = ({ selectedNode }) => {
  if (!selectedNode) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400 p-6">
        <div className="text-center">
          <svg className="mx-auto h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p className="mt-2 text-sm">Select a node to view details</p>
        </div>
      </div>
    );
  }

  const getNodeTypeColor = (type: string) => {
    switch (type) {
      case 'object':
        return 'bg-blue-100 text-blue-800';
      case 'association':
        return 'bg-purple-100 text-purple-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getWarningExplanation = (warning: string) => {
    switch (warning) {
      case 'deep_nesting':
        return 'This node is deeply nested (>3 levels). Consider selecting intermediate nodes to reduce property path complexity.';
      case 'sparse_connectivity':
        return 'This node may have sparse connectivity. Some incoming references are from unselected nodes.';
      case 'insufficient_endpoints':
        return 'Association requires at least 2 selected endpoints to create a relationship.';
      default:
        return warning;
    }
  };

  const getSuggestionExplanation = (suggestion: string) => {
    switch (suggestion) {
      case 'association_candidate':
        return 'This element has characteristics of an n-ary relationship. May be better modeled as a relationship node if endpoints are selected.';
      case 'flatten_wrapper':
        return 'This container has only 1-2 simple properties with no relationships. Consider flattening it into the parent node.';
      default:
        return suggestion;
    }
  };

  return (
    <div className="h-full overflow-y-auto p-6 bg-gray-50">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{selectedNode.qname}</h3>
          <div className="mt-2 flex items-center space-x-2">
            <span className={`px-2 py-1 text-xs font-medium rounded ${getNodeTypeColor(selectedNode.node_type)}`}>
              {selectedNode.node_type}
            </span>
            {selectedNode.is_nested_association && (
              <span className="px-2 py-1 text-xs font-medium rounded bg-yellow-100 text-yellow-800">
                Nested Association
              </span>
            )}
          </div>
        </div>

        {/* Neo4j Mapping */}
        <div className="bg-white rounded-lg p-4 shadow-sm">
          <h4 className="text-sm font-semibold text-gray-700 mb-3">Neo4j Mapping</h4>
          <div className="space-y-2 text-sm">
            <div>
              <span className="text-gray-600">Label:</span>
              <span className="ml-2 font-mono text-gray-900">{selectedNode.label}</span>
            </div>
            {selectedNode.namespace && (
              <div>
                <span className="text-gray-600">Namespace:</span>
                <span className="ml-2 font-mono text-gray-900">{selectedNode.namespace}</span>
              </div>
            )}
          </div>
        </div>

        {/* Metadata */}
        <div className="bg-white rounded-lg p-4 shadow-sm">
          <h4 className="text-sm font-semibold text-gray-700 mb-3">Metadata</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Depth:</span>
              <span className="text-gray-900">{selectedNode.depth}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Scalar Properties:</span>
              <span className="text-gray-900">{selectedNode.property_count}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Nested Objects:</span>
              <span className="text-gray-900">{selectedNode.nested_object_count}</span>
            </div>
            {selectedNode.cardinality && (
              <div className="flex justify-between">
                <span className="text-gray-600">Cardinality:</span>
                <span className="font-mono text-gray-900">{selectedNode.cardinality}</span>
              </div>
            )}
            {selectedNode.children.length > 0 && (
              <div className="flex justify-between">
                <span className="text-gray-600">Child Nodes:</span>
                <span className="text-gray-900">{selectedNode.children.length}</span>
              </div>
            )}
          </div>
        </div>

        {/* Selection Impact */}
        <div className="bg-white rounded-lg p-4 shadow-sm">
          <h4 className="text-sm font-semibold text-gray-700 mb-3">Selection Impact</h4>
          <div className="text-sm text-gray-600">
            {selectedNode.selected ? (
              <div className="space-y-2">
                <p className="text-green-700 font-medium">✓ Will create Neo4j node</p>
                <p className="text-xs">
                  This element will become a node with label <span className="font-mono">{selectedNode.label}</span>.
                  {selectedNode.property_count > 0 && ` It will have ${selectedNode.property_count} scalar properties.`}
                  {selectedNode.nested_object_count > 0 && ` It will have ${selectedNode.nested_object_count} nested objects.`}
                </p>
                {selectedNode.children.length > 0 && !selectedNode.selected && (
                  <p className="text-xs text-amber-700">
                    Unselected child nodes will be flattened into this node as properties.
                  </p>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-gray-700 font-medium">⊘ Will be flattened</p>
                <p className="text-xs">
                  This element will not become a node. Its data will be flattened as properties on the nearest selected ancestor node.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Warnings */}
        {selectedNode.warnings.length > 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-yellow-900 mb-2 flex items-center">
              <span className="mr-2">⚠️</span> Warnings
            </h4>
            <div className="space-y-2">
              {selectedNode.warnings.map((warning, idx) => (
                <div key={idx} className="text-xs text-yellow-800">
                  <p className="font-medium">{warning.replace('_', ' ')}</p>
                  <p className="mt-1 text-yellow-700">{getWarningExplanation(warning)}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Suggestions */}
        {selectedNode.suggestions.length > 0 && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-blue-900 mb-2 flex items-center">
              <span className="mr-2">💡</span> Suggestions
            </h4>
            <div className="space-y-2">
              {selectedNode.suggestions.map((suggestion, idx) => (
                <div key={idx} className="text-xs text-blue-800">
                  <p className="font-medium">{suggestion.replace('_', ' ')}</p>
                  <p className="mt-1 text-blue-700">{getSuggestionExplanation(suggestion)}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Description */}
        {selectedNode.description && (
          <div className="bg-white rounded-lg p-4 shadow-sm">
            <h4 className="text-sm font-semibold text-gray-700 mb-2">Description</h4>
            <p className="text-sm text-gray-600">{selectedNode.description}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default SchemaNodeInspector;
