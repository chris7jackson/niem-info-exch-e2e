import React, { useState, useMemo, useEffect } from 'react';
import { ElementTreeNode } from '../lib/api';

interface SchemaElementTreeProps {
  nodes: ElementTreeNode[];
  selections: Record<string, boolean>;
  onSelectionChange: (qname: string, selected: boolean) => void;
  onNodeClick: (node: ElementTreeNode) => void;
  selectedNodeQname: string | null;
}

const SchemaElementTree: React.FC<SchemaElementTreeProps> = ({
  nodes,
  selections,
  onSelectionChange,
  onNodeClick,
  selectedNodeQname,
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  // Build parent-child relationship map
  const nodeMap = useMemo(() => {
    const map = new Map<string, ElementTreeNode>();
    nodes.forEach((node) => map.set(node.qname, node));
    return map;
  }, [nodes]);

  // Build children map
  const childrenMap = useMemo(() => {
    const map = new Map<string, ElementTreeNode[]>();
    nodes.forEach((node) => {
      if (node.parent_qname) {
        const children = map.get(node.parent_qname) || [];
        children.push(node);
        map.set(node.parent_qname, children);
      }
    });
    return map;
  }, [nodes]);

  // Initialize all parent nodes as expanded
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  // Update expanded nodes when nodes change (expand all by default)
  useEffect(() => {
    const allParentNodes = new Set<string>();
    nodes.forEach((node) => {
      // If node has children, expand it by default
      const hasChildren = childrenMap.has(node.qname);
      if (hasChildren) {
        allParentNodes.add(node.qname);
      }
    });
    setExpandedNodes(allParentNodes);
  }, [nodes, childrenMap]);

  // Get root nodes (no parent)
  const rootNodes = useMemo(() => {
    return nodes.filter((node) => !node.parent_qname);
  }, [nodes]);

  // Filter nodes by search query
  const filteredNodes = useMemo(() => {
    if (!searchQuery.trim()) return nodes;

    const query = searchQuery.toLowerCase();
    return nodes.filter((node) => node.qname.toLowerCase().includes(query));
  }, [nodes, searchQuery]);

  const toggleExpand = (qname: string) => {
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(qname)) {
      newExpanded.delete(qname);
    } else {
      newExpanded.add(qname);
    }
    setExpandedNodes(newExpanded);
  };

  const handleSelectAll = () => {
    filteredNodes.forEach((node) => {
      if (!selections[node.qname]) {
        onSelectionChange(node.qname, true);
      }
    });
  };

  const handleClearAll = () => {
    filteredNodes.forEach((node) => {
      if (selections[node.qname]) {
        onSelectionChange(node.qname, false);
      }
    });
  };

  // Warnings disabled - deep nesting warnings removed for NIEM schemas
  // const getWarningIcon = (warnings: string[]) => {
  //   if (warnings.length === 0) return null;
  //   return (
  //     <span className="text-yellow-500 text-xs" title={warnings.join(', ')}>
  //       ⚠️
  //     </span>
  //   );
  // };

  const getAssociationBadge = (node: ElementTreeNode) => {
    if (node.node_type !== 'association') return null;

    let color = 'bg-gray-100 text-gray-600';
    let icon = '🔗';

    if (node.nested_object_count >= 2) {
      color = 'bg-green-100 text-green-700';
      icon = '🔗';
    } else if (node.nested_object_count === 1) {
      color = 'bg-yellow-100 text-yellow-700';
      icon = '⚠️';
    } else {
      color = 'bg-gray-100 text-gray-600';
      icon = '⊘';
    }

    const label = node.is_nested_association ? 'Nested' : 'Top-level';

    return (
      <span className={`px-2 py-0.5 text-xs rounded ${color} flex items-center space-x-1`}>
        <span>{icon}</span>
        <span>{label}</span>
      </span>
    );
  };

  // Suggestions disabled - removed for NIEM schemas
  // const getSuggestionBadge = (suggestions: string[]) => {
  //   if (suggestions.length === 0) return null;
  //   return (
  //     <span className="text-blue-500 text-xs" title={suggestions.join(', ')}>
  //       💡
  //     </span>
  //   );
  // };

  const TreeNode: React.FC<{ node: ElementTreeNode; depth: number }> = ({ node, depth }) => {
    const children = childrenMap.get(node.qname) || [];
    const hasChildren = children.length > 0;
    const isExpanded = expandedNodes.has(node.qname);
    const isSelected = selections[node.qname] !== false; // Default true
    const isHighlighted = selectedNodeQname === node.qname;

    // Check if node matches search
    const matchesSearch = !searchQuery.trim() || node.qname.toLowerCase().includes(searchQuery.toLowerCase());
    if (!matchesSearch && !hasChildren) return null;

    return (
      <div>
        <div
          className={`flex items-center py-2 px-2 hover:bg-gray-50 cursor-pointer ${
            isHighlighted ? 'bg-blue-50 border-l-4 border-blue-500' : ''
          }`}
          style={{ paddingLeft: `${depth * 1.5 + 0.5}rem` }}
          onClick={() => onNodeClick(node)}
        >
          {/* Expand/Collapse Icon */}
          {hasChildren ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                toggleExpand(node.qname);
              }}
              className="mr-2 text-gray-400 hover:text-gray-600 focus:outline-none"
            >
              {isExpanded ? (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              )}
            </button>
          ) : (
            <div className="w-4 mr-2" />
          )}

          {/* Checkbox */}
          <input
            type="checkbox"
            checked={isSelected}
            onChange={(e) => {
              e.stopPropagation();
              onSelectionChange(node.qname, e.target.checked);
            }}
            className="mr-3"
          />

          {/* Node Info */}
          <div className="flex-1 flex items-center space-x-2 min-w-0">
            <span className="font-mono text-sm text-gray-900 truncate">{node.qname}</span>

            {/* Node Type Badge */}
            <span
              className={`px-2 py-0.5 text-xs rounded flex-shrink-0 ${
                node.node_type === 'object'
                  ? 'bg-blue-100 text-blue-700'
                  : node.node_type === 'association'
                  ? 'bg-purple-100 text-purple-700'
                  : 'bg-green-100 text-green-700'
              }`}
            >
              {node.node_type}
            </span>

            {/* Association Badge */}
            {getAssociationBadge(node)}

            {/* Warnings - Disabled since deep nesting warnings are removed */}
            {/* {getWarningIcon(node.warnings)} */}

            {/* Suggestions - Disabled since suggestions are removed */}
            {/* {getSuggestionBadge(node.suggestions)} */}

            {/* Counts */}
            <span className="text-xs text-gray-500 flex-shrink-0">
              {node.property_count > 0 && `${node.property_count}p`}
              {node.property_count > 0 && node.nested_object_count > 0 && ' • '}
              {node.nested_object_count > 0 && `${node.nested_object_count}n`}
            </span>
          </div>
        </div>

        {/* Children */}
        {hasChildren && isExpanded && (
          <div>
            {children.map((child) => (
              <TreeNode key={child.qname} node={child} depth={depth + 1} />
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col">
      {/* Search and Controls */}
      <div className="p-4 border-b border-gray-200 space-y-3">
        {/* Search */}
        <div className="relative">
          <input
            type="text"
            placeholder="Search by qname..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-3 py-2 pl-10 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
          />
          <svg
            className="absolute left-3 top-2.5 h-5 w-5 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>

        {/* Bulk Actions */}
        <div className="flex items-center space-x-2">
          <button
            onClick={handleSelectAll}
            className="px-3 py-1 text-sm text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded"
          >
            Select All
          </button>
          <button
            onClick={handleClearAll}
            className="px-3 py-1 text-sm text-gray-600 hover:text-gray-700 hover:bg-gray-100 rounded"
          >
            Clear All
          </button>
          <div className="flex-1 text-right text-xs text-gray-500">
            {filteredNodes.filter((n) => selections[n.qname] !== false).length} / {filteredNodes.length} selected
          </div>
        </div>

        {/* Legend */}
        <div className="text-xs text-gray-600 space-y-1">
          <div className="flex items-center space-x-3">
            <span className="font-semibold">Legend:</span>
            <span>p = properties</span>
            <span>n = nested objects</span>
          </div>
        </div>
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto">
        {filteredNodes.length === 0 ? (
          <div className="py-8 text-center text-gray-500">No nodes match your search</div>
        ) : (
          <div className="divide-y divide-gray-100">
            {rootNodes.map((node) => (
              <TreeNode key={node.qname} node={node} depth={0} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SchemaElementTree;
