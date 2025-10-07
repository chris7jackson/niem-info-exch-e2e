'use client';

import { GraphNode, GraphEdge } from '@/lib/api';
import { XMarkIcon } from '@heroicons/react/24/outline';

export interface SchemaDetailPanelProps {
  node: GraphNode | null;
  edges: GraphEdge[];
  onClose: () => void;
  onNavigate?: (nodeId: string) => void;
}

/**
 * SchemaDetailPanel - Shows detailed information about a selected node
 *
 * Data-driven design: Displays all fields without hardcoded assumptions
 */
export default function SchemaDetailPanel({
  node,
  edges,
  onClose,
  onNavigate
}: SchemaDetailPanelProps) {
  if (!node) return null;

  // Find edges related to this node
  const outgoingEdges = edges.filter(e => e.source === node.id);
  const incomingEdges = edges.filter(e => e.target === node.id);

  // Get properties (outgoing property edges)
  const properties = outgoingEdges.filter(e => e.edgeType === 'property');

  // Get associations (association edges)
  const associations = outgoingEdges.filter(e => e.edgeType === 'association');

  // Get augmentations (incoming augmentation edges)
  const augmentations = incomingEdges.filter(e => e.edgeType === 'augmentation');

  // Get extends relationship
  const extendsEdge = outgoingEdges.find(e => e.edgeType === 'extends');

  // Get usage count from metadata
  const usageCount = node.metadata?.usageCount || 0;

  return (
    <div className="w-96 bg-white border-l border-gray-200 overflow-y-auto flex flex-col h-full">
      {/* Header */}
      <div className="sticky top-0 bg-white border-b border-gray-200 p-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 truncate">
          {node.label}
        </h2>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600"
          aria-label="Close panel"
        >
          <XMarkIcon className="h-5 w-5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 p-4 space-y-6">
        {/* Qualified Name */}
        <div>
          <h3 className="text-sm font-medium text-gray-500 mb-1">Qualified Name</h3>
          <p className="text-sm text-gray-900 font-mono">{node.id}</p>
        </div>

        {/* Namespace */}
        <div>
          <h3 className="text-sm font-medium text-gray-500 mb-1">Namespace</h3>
          <div className="space-y-1">
            <p className="text-sm text-gray-900">{node.namespace}</p>
            <p className="text-xs text-gray-500 break-all">{node.namespaceURI}</p>
            <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800">
              {node.namespaceCategory}
            </span>
          </div>
        </div>

        {/* Node Type */}
        <div>
          <h3 className="text-sm font-medium text-gray-500 mb-1">Type</h3>
          <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-gray-100 text-gray-800">
            {node.nodeType}
          </span>
        </div>

        {/* Documentation */}
        {node.documentation && (
          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-1">Documentation</h3>
            <p className="text-sm text-gray-700 leading-relaxed">{node.documentation}</p>
          </div>
        )}

        {/* Extends */}
        {extendsEdge && (
          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-2">Extends</h3>
            <button
              onClick={() => onNavigate && onNavigate(extendsEdge.target)}
              className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
            >
              {extendsEdge.target}
            </button>
          </div>
        )}

        {/* Properties */}
        {properties.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              Properties ({properties.length})
            </h3>
            <div className="space-y-2">
              {properties.map(prop => (
                <div key={prop.id} className="border border-gray-200 rounded p-2">
                  <div className="flex items-start justify-between">
                    <button
                      onClick={() => onNavigate && onNavigate(prop.target)}
                      className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      {prop.label}
                    </button>
                    {prop.cardinality && (
                      <span className="text-xs text-gray-500 ml-2">{prop.cardinality}</span>
                    )}
                  </div>
                  {prop.documentation && (
                    <p className="text-xs text-gray-600 mt-1">{prop.documentation}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Associations */}
        {associations.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              Associations ({associations.length})
            </h3>
            <div className="space-y-2">
              {associations.map(assoc => (
                <div key={assoc.id} className="border border-gray-200 rounded p-2">
                  <div className="flex items-start justify-between">
                    <button
                      onClick={() => onNavigate && onNavigate(assoc.target)}
                      className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      {assoc.label}
                    </button>
                    {assoc.cardinality && (
                      <span className="text-xs text-gray-500 ml-2">{assoc.cardinality}</span>
                    )}
                  </div>
                  {assoc.documentation && (
                    <p className="text-xs text-gray-600 mt-1">{assoc.documentation}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Augmentations */}
        {augmentations.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              Augmented By ({augmentations.length})
            </h3>
            <div className="space-y-2">
              {augmentations.map(aug => (
                <div key={aug.id} className="border border-gray-200 rounded p-2">
                  <button
                    onClick={() => onNavigate && onNavigate(aug.source)}
                    className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
                  >
                    {aug.label}
                  </button>
                  {aug.documentation && (
                    <p className="text-xs text-gray-600 mt-1">{aug.documentation}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Usage Count */}
        {usageCount > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-1">Usage</h3>
            <p className="text-sm text-gray-900">
              Referenced by {usageCount} other {usageCount === 1 ? 'type' : 'types'}
            </p>
          </div>
        )}

        {/* Metadata */}
        {node.metadata && Object.keys(node.metadata).length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-2">Metadata</h3>
            <div className="space-y-1">
              {Object.entries(node.metadata).map(([key, value]) => {
                // Skip metadata already shown elsewhere
                if (key === 'usageCount') return null;

                return (
                  <div key={key} className="flex justify-between text-xs">
                    <span className="text-gray-500 capitalize">{key}:</span>
                    <span className="text-gray-900 font-mono">
                      {typeof value === 'boolean' ? (value ? 'true' : 'false') : String(value)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
