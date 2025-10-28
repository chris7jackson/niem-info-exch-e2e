import React, { useState, useEffect } from 'react';
import { NodeTypeInfo, EntityResolutionResponse, EntityResolutionStatusResponse } from '../lib/api';
import apiClient from '../lib/api';

interface EntityResolutionPanelProps {
  onResolutionComplete?: (response: EntityResolutionResponse) => void;
  onError?: (error: string) => void;
}

const EntityResolutionPanel: React.FC<EntityResolutionPanelProps> = ({
  onResolutionComplete,
  onError,
}) => {
  const [nodeTypes, setNodeTypes] = useState<NodeTypeInfo[]>([]);
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingTypes, setIsLoadingTypes] = useState(true);
  const [resolutionStatus, setResolutionStatus] = useState<EntityResolutionStatusResponse | null>(
    null
  );
  const [lastResult, setLastResult] = useState<EntityResolutionResponse | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  // Fetch available node types on mount
  useEffect(() => {
    fetchNodeTypes();
    fetchResolutionStatus();
  }, []);

  const fetchNodeTypes = async () => {
    try {
      setIsLoadingTypes(true);
      const response = await apiClient.getEntityResolutionNodeTypes();
      setNodeTypes(response.nodeTypes);
      // No types selected by default
      setSelectedTypes(new Set());
    } catch (error) {
      console.error('Failed to fetch node types:', error);
      onError?.('Failed to fetch available node types');
    } finally {
      setIsLoadingTypes(false);
    }
  };

  const fetchResolutionStatus = async () => {
    try {
      const status = await apiClient.getEntityResolutionStatus();
      setResolutionStatus(status);
    } catch (error) {
      console.error('Failed to fetch resolution status:', error);
    }
  };

  const handleRunResolution = async () => {
    if (selectedTypes.size === 0) {
      onError?.('Please select at least one node type');
      return;
    }

    setIsLoading(true);
    setLastResult(null);

    try {
      const response = await apiClient.runEntityResolution(Array.from(selectedTypes));
      setLastResult(response);
      onResolutionComplete?.(response);

      // Refresh status
      await fetchResolutionStatus();
    } catch (error: any) {
      console.error('Entity resolution failed:', error);
      onError?.(error.response?.data?.detail || 'Entity resolution failed');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetResolution = async () => {
    if (!confirm('Are you sure you want to reset all entity resolution data?')) {
      return;
    }

    setIsLoading(true);
    try {
      await apiClient.resetEntityResolution();
      setLastResult(null);
      await fetchResolutionStatus();
    } catch (error) {
      console.error('Failed to reset entity resolution:', error);
      onError?.('Failed to reset entity resolution');
    } finally {
      setIsLoading(false);
    }
  };

  const toggleNodeType = (qname: string) => {
    const newSelected = new Set(selectedTypes);
    if (newSelected.has(qname)) {
      newSelected.delete(qname);
    } else {
      newSelected.add(qname);
    }
    setSelectedTypes(newSelected);
  };

  const selectAll = () => {
    const filtered = getFilteredNodeTypes();
    setSelectedTypes(new Set(filtered.map((nt) => nt.qname)));
  };

  const selectNone = () => {
    setSelectedTypes(new Set());
  };

  const getFilteredNodeTypes = () => {
    let filtered = nodeTypes;

    if (searchTerm) {
      const lower = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (nt) => nt.qname.toLowerCase().includes(lower) || nt.category?.toLowerCase().includes(lower)
      );
    }

    return filtered;
  };

  const getCategoryColor = (category?: string) => {
    switch (category) {
      case 'person':
        return 'bg-blue-100 text-blue-800';
      case 'organization':
        return 'bg-green-100 text-green-800';
      case 'address':
        return 'bg-yellow-100 text-yellow-800';
      case 'vehicle':
        return 'bg-purple-100 text-purple-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const filteredNodeTypes = getFilteredNodeTypes();

  return (
    <div className="bg-white shadow rounded-lg">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-900">Entity Resolution</h3>
        <p className="mt-1 text-sm text-gray-600">
          Select entity types to resolve duplicates using{' '}
          {lastResult?.resolutionMethod === 'senzing'
            ? 'Senzing SDK'
            : 'text-based entity matching'}
        </p>
      </div>

      {/* Status Bar */}
      {resolutionStatus && resolutionStatus.is_active && (
        <div className="px-6 py-3 bg-blue-50 border-b border-blue-200">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-blue-900">Current Resolution Status</span>
            <div className="flex items-center space-x-4 text-sm text-blue-700">
              <span>{resolutionStatus.resolved_entity_clusters} clusters</span>
              <span>{resolutionStatus.entities_resolved} entities resolved</span>
            </div>
          </div>
        </div>
      )}

      {/* Node Type Selection */}
      <div className="px-6 py-4">
        <div className="mb-4 space-y-3">
          {/* Search Control */}
          <div className="flex items-center">
            <input
              type="text"
              placeholder="Search node types..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Selection Controls */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-700">
              {selectedTypes.size} of {filteredNodeTypes.length} types selected
            </span>
            <div className="space-x-2">
              <button
                onClick={selectAll}
                className="px-3 py-1 text-sm text-blue-600 hover:text-blue-800"
                disabled={isLoading}
              >
                Select All
              </button>
              <button
                onClick={selectNone}
                className="px-3 py-1 text-sm text-blue-600 hover:text-blue-800"
                disabled={isLoading}
              >
                Clear All
              </button>
            </div>
          </div>
        </div>

        {/* Node Type List */}
        {isLoadingTypes ? (
          <div className="py-8 text-center text-gray-500">Loading node types...</div>
        ) : (
          <div className="border border-gray-200 rounded-md max-h-64 overflow-y-auto">
            {filteredNodeTypes.length === 0 ? (
              <div className="py-4 text-center text-gray-500">No matching node types found</div>
            ) : (
              <div className="divide-y divide-gray-200">
                {filteredNodeTypes.map((nodeType) => (
                  <label
                    key={nodeType.qname}
                    className="flex items-center px-4 py-3 hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedTypes.has(nodeType.qname)}
                      onChange={() => toggleNodeType(nodeType.qname)}
                      disabled={isLoading}
                      className="mr-3"
                    />
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-sm text-gray-900">{nodeType.qname}</span>
                        {nodeType.category && (
                          <span
                            className={`px-2 py-0.5 text-xs rounded ${getCategoryColor(nodeType.category)}`}
                          >
                            {nodeType.category}
                          </span>
                        )}
                      </div>
                      {nodeType.hierarchyPath && nodeType.hierarchyPath.length > 0 && (
                        <div className="text-xs text-gray-400 mt-0.5">
                          <span className="font-mono">{nodeType.hierarchyPath.join(' → ')}</span>
                        </div>
                      )}
                      <div className="text-xs text-gray-500 mt-1">
                        {nodeType.count} entities • {nodeType.nameFields.join(', ')}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
        <div className="flex items-center justify-between">
          <button
            onClick={handleResetResolution}
            disabled={isLoading || !resolutionStatus?.is_active}
            className="px-4 py-2 text-sm font-medium text-red-600 bg-white border border-red-300 rounded-md hover:bg-red-50 disabled:opacity-50"
          >
            Reset Resolution
          </button>
          <button
            onClick={handleRunResolution}
            disabled={isLoading || selectedTypes.size === 0}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {isLoading ? 'Running...' : 'Run Entity Resolution'}
          </button>
        </div>
      </div>

      {/* Results */}
      {lastResult && (
        <div className="px-6 py-4 bg-green-50 border-t border-green-200">
          <h4 className="text-sm font-medium text-green-900 mb-2">Resolution Complete</h4>
          <div className="grid grid-cols-2 gap-2 text-sm text-green-700">
            <div>Entities Extracted: {lastResult.entitiesExtracted}</div>
            <div>Duplicate Groups: {lastResult.duplicateGroupsFound}</div>
            <div>Resolved Entities: {lastResult.resolvedEntitiesCreated}</div>
            <div>Relationships Created: {lastResult.relationshipsCreated}</div>
            <div className="col-span-2 mt-2 pt-2 border-t border-green-200">
              Method:{' '}
              {lastResult.resolutionMethod === 'senzing'
                ? 'Senzing SDK'
                : 'Text-Based Entity Matching'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EntityResolutionPanel;
