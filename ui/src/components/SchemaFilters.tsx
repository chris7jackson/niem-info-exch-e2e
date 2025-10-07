'use client';

import { useState } from 'react';
import { Namespace, GraphNode } from '@/lib/api';
import { MagnifyingGlassIcon, FunnelIcon } from '@heroicons/react/24/outline';

export interface SchemaFiltersProps {
  namespaces: Namespace[];
  nodes: GraphNode[];
  selectedNamespaces: string[];
  selectedNodeTypes: string[];
  searchTerm: string;
  maxDepth: number;
  onNamespaceChange: (namespaces: string[]) => void;
  onNodeTypeChange: (nodeTypes: string[]) => void;
  onSearchChange: (term: string) => void;
  onDepthChange: (depth: number) => void;
  onClearFilters: () => void;
}

/**
 * SchemaFilters - Filter controls for graph visualization
 *
 * Data-driven design: Dynamically builds filter options from actual data
 */
export default function SchemaFilters({
  namespaces,
  nodes,
  selectedNamespaces,
  selectedNodeTypes,
  searchTerm,
  maxDepth,
  onNamespaceChange,
  onNodeTypeChange,
  onSearchChange,
  onDepthChange,
  onClearFilters
}: SchemaFiltersProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  // Extract unique node types from data
  const availableNodeTypes = Array.from(new Set(nodes.map(n => n.nodeType))).sort();

  // Handle namespace checkbox toggle
  const handleNamespaceToggle = (prefix: string) => {
    if (selectedNamespaces.includes(prefix)) {
      onNamespaceChange(selectedNamespaces.filter(ns => ns !== prefix));
    } else {
      onNamespaceChange([...selectedNamespaces, prefix]);
    }
  };

  // Handle node type checkbox toggle
  const handleNodeTypeToggle = (nodeType: string) => {
    if (selectedNodeTypes.includes(nodeType)) {
      onNodeTypeChange(selectedNodeTypes.filter(nt => nt !== nodeType));
    } else {
      onNodeTypeChange([...selectedNodeTypes, nodeType]);
    }
  };

  // Handle select/deselect all namespaces
  const handleSelectAllNamespaces = () => {
    if (selectedNamespaces.length === namespaces.length) {
      onNamespaceChange([]);
    } else {
      onNamespaceChange(namespaces.map(ns => ns.prefix));
    }
  };

  // Handle select/deselect all node types
  const handleSelectAllNodeTypes = () => {
    if (selectedNodeTypes.length === availableNodeTypes.length) {
      onNodeTypeChange([]);
    } else {
      onNodeTypeChange(availableNodeTypes);
    }
  };

  const hasActiveFilters =
    selectedNamespaces.length < namespaces.length ||
    selectedNodeTypes.length < availableNodeTypes.length ||
    searchTerm !== '' ||
    maxDepth !== 10;

  return (
    <div className="w-64 bg-white border-r border-gray-200 overflow-y-auto flex flex-col h-full">
      {/* Header */}
      <div className="sticky top-0 bg-white border-b border-gray-200 p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <FunnelIcon className="h-5 w-5 text-gray-500" />
            <h2 className="text-lg font-semibold text-gray-900">Filters</h2>
          </div>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            {isExpanded ? '−' : '+'}
          </button>
        </div>

        {hasActiveFilters && (
          <button
            onClick={onClearFilters}
            className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
          >
            Clear all filters
          </button>
        )}
      </div>

      {isExpanded && (
        <div className="flex-1 p-4 space-y-6">
          {/* Search */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Search
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <MagnifyingGlassIcon className="h-4 w-4 text-gray-400" />
              </div>
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder="Search nodes..."
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            {searchTerm && (
              <p className="mt-1 text-xs text-gray-500">
                Highlighting matching nodes
              </p>
            )}
          </div>

          {/* Depth Slider */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Max Depth: {maxDepth}
            </label>
            <input
              type="range"
              min="1"
              max="10"
              value={maxDepth}
              onChange={(e) => onDepthChange(parseInt(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>1</span>
              <span>10</span>
            </div>
          </div>

          {/* Namespaces */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Namespaces
              </label>
              <button
                onClick={handleSelectAllNamespaces}
                className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
              >
                {selectedNamespaces.length === namespaces.length ? 'Deselect all' : 'Select all'}
              </button>
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {namespaces.map(ns => (
                <label key={ns.id} className="flex items-start gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedNamespaces.includes(ns.prefix)}
                    onChange={() => handleNamespaceToggle(ns.prefix)}
                    className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900">{ns.prefix}</span>
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                        {ns.category}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 truncate">{ns.label}</p>
                    <p className="text-xs text-gray-400">
                      {ns.classCount} {ns.classCount === 1 ? 'class' : 'classes'}
                    </p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Node Types */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Node Types
              </label>
              <button
                onClick={handleSelectAllNodeTypes}
                className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
              >
                {selectedNodeTypes.length === availableNodeTypes.length ? 'Deselect all' : 'Select all'}
              </button>
            </div>
            <div className="space-y-2">
              {availableNodeTypes.map(nodeType => {
                const count = nodes.filter(n => n.nodeType === nodeType).length;
                return (
                  <label key={nodeType} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedNodeTypes.includes(nodeType)}
                      onChange={() => handleNodeTypeToggle(nodeType)}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <div className="flex-1 flex items-center justify-between">
                      <span className="text-sm text-gray-900 capitalize">{nodeType}</span>
                      <span className="text-xs text-gray-500">({count})</span>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Stats */}
          <div className="pt-4 border-t border-gray-200">
            <h3 className="text-xs font-medium text-gray-500 mb-2">Statistics</h3>
            <div className="space-y-1 text-xs text-gray-600">
              <div className="flex justify-between">
                <span>Total Nodes:</span>
                <span className="font-medium">{nodes.length}</span>
              </div>
              <div className="flex justify-between">
                <span>Namespaces:</span>
                <span className="font-medium">{namespaces.length}</span>
              </div>
              <div className="flex justify-between">
                <span>Node Types:</span>
                <span className="font-medium">{availableNodeTypes.length}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
