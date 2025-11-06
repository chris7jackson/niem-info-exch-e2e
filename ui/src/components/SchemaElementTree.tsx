import React, { useState, useMemo } from 'react';
import { List } from 'react-window';
import { ElementTreeNode } from '../lib/api';

interface SchemaElementTreeProps {
  nodes: ElementTreeNode[];
  selections: Record<string, boolean>;
  onSelectionChange: (qname: string, selected: boolean) => void;
  onNodeClick: (node: ElementTreeNode) => void;
  selectedNodeQname: string | null;
}

interface TreeRow {
  node: ElementTreeNode;
  depth: number;
  hasChildren: boolean;
  isExpanded: boolean;
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

  // Initialize with all nodes collapsed for better performance with large schemas
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  // Get root nodes (no parent)
  const rootNodes = useMemo(() => {
    return nodes.filter((node) => !node.parent_qname);
  }, [nodes]);

  // Filter nodes by search query - include matching nodes and their ancestors
  const filteredNodes = useMemo(() => {
    if (!searchQuery.trim()) return nodes;

    const query = searchQuery.toLowerCase();
    const matchingQnames = new Set<string>();

    // Find all nodes that match the search
    nodes.forEach((node) => {
      if (node.qname.toLowerCase().includes(query)) {
        matchingQnames.add(node.qname);

        // Add all ancestors to show the path to root
        let currentParent = node.parent_qname;
        while (currentParent) {
          matchingQnames.add(currentParent);
          const parentNode = nodeMap.get(currentParent);
          currentParent = parentNode?.parent_qname || null;
        }
      }
    });

    return nodes.filter((node) => matchingQnames.has(node.qname));
  }, [nodes, searchQuery, nodeMap]);

  // Flatten tree into array of visible rows for virtualization
  const visibleRows = useMemo(() => {
    const rows: TreeRow[] = [];
    const filteredQnames = new Set(filteredNodes.map(n => n.qname));

    const addNodeAndChildren = (node: ElementTreeNode, depth: number) => {
      const allChildren = childrenMap.get(node.qname) || [];
      const children = allChildren.filter(child => filteredQnames.has(child.qname));
      const hasChildren = children.length > 0;
      const isExpanded = expandedNodes.has(node.qname);

      rows.push({
        node,
        depth,
        hasChildren,
        isExpanded,
      });

      // Only add children if node is expanded
      if (isExpanded && hasChildren) {
        children.forEach(child => addNodeAndChildren(child, depth + 1));
      }
    };

    // Start with root nodes
    rootNodes
      .filter(node => filteredQnames.has(node.qname))
      .forEach(node => addNodeAndChildren(node, 0));

    return rows;
  }, [filteredNodes, rootNodes, childrenMap, expandedNodes]);

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

  // Row component for virtual list
  const RowComponent = ({ index, style }: { index: number; style: React.CSSProperties }) => {
    const row = visibleRows[index];

    // Safety check - if row doesn't exist, return empty div
    if (!row) {
      return <div style={{ ...style, height: 48 }} />;
    }

    const { node, depth, hasChildren, isExpanded } = row;
    const isSelected = selections[node.qname] !== false; // Default true
    const isHighlighted = selectedNodeQname === node.qname;

    return (
      <div
        style={style}
        className={`flex items-center py-2 px-2 hover:bg-gray-50 cursor-pointer ${
          isHighlighted ? 'bg-blue-50 border-l-4 border-blue-500' : ''
        }`}
        onClick={() => onNodeClick(node)}
      >
        <div
          className="flex items-center w-full"
          style={{ paddingLeft: `${depth * 1.5 + 0.5}rem` }}
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

      {/* Tree - Virtualized */}
      <div className="flex-1 overflow-hidden">
        {visibleRows.length === 0 ? (
          <div className="py-8 text-center text-gray-500">No nodes match your search</div>
        ) : (
          <List<Record<string, never>>
            defaultHeight={600}
            rowCount={visibleRows.length}
            rowHeight={() => 48}
            rowComponent={RowComponent}
            rowProps={{}}
            className="scrollbar-thin"
            style={{ width: '100%', height: '100%' }}
          />
        )}
      </div>
    </div>
  );
};

export default SchemaElementTree;
