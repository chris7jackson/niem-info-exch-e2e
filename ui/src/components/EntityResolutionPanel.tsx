import React, { useState, useEffect } from 'react';
import { NodeTypeInfo, EntityResolutionResponse, EntityResolutionStatusResponse } from '../lib/api';
import apiClient from '../lib/api';

interface EntityResolutionPanelProps {
  onResolutionComplete?: (response: EntityResolutionResponse) => void;
  onError?: (error: string) => void;
}

// Tooltip component for displaying helpful information
const Tooltip: React.FC<{ text: string; children: React.ReactNode }> = ({ text, children }) => {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <div className="relative inline-flex items-center">
      <div
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
        className="cursor-help inline-flex"
      >
        {children}
      </div>
      {isVisible && (
        <div className="absolute z-10 w-64 p-2 text-xs text-white bg-gray-900 rounded shadow-lg left-full ml-2 top-1/2 transform -translate-y-1/2">
          {text}
          <div className="absolute top-1/2 right-full transform -translate-y-1/2">
            <div className="border-4 border-transparent border-r-gray-900"></div>
          </div>
        </div>
      )}
    </div>
  );
};

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
  const [showMatchDetails, setShowMatchDetails] = useState(false);

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
    setIsLoading(true);
    try {
      await apiClient.resetEntityResolution();
      setLastResult(null);
      // Refresh all data
      await Promise.all([fetchResolutionStatus(), fetchNodeTypes()]);
      // Notify parent to refresh (e.g., graph visualization)
      onResolutionComplete?.({
        status: 'success',
        message: 'Entity resolution reset successfully',
        entitiesExtracted: 0,
        duplicateGroupsFound: 0,
        resolvedEntitiesCreated: 0,
        relationshipsCreated: 0,
        entitiesResolved: 0,
        resolutionMethod: 'text_based',
        nodeTypesProcessed: [],
      });
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

  const formatMatchKey = (matchKey: string) => {
    // Handle special Senzing match keys
    if (matchKey === 'Exactly_same' || matchKey === 'EXACTLY_SAME') {
      return 'Exact match (all attributes identical)';
    }
    if (matchKey === 'SAME_ID') {
      return 'Same identifier';
    }
    if (!matchKey || matchKey === '') {
      return 'Unknown match criteria';
    }

    // Convert "+NAME+DOB+ADDRESS" to "Name + Date of Birth + Address"
    const parts = matchKey
      .split('+')
      .filter(Boolean)
      .map((key) => {
        // Convert common abbreviations
        let formatted = key
          .replace(/^DOB$/i, 'Date of Birth')
          .replace(/^SSN$/i, 'SSN')
          .replace(/^ADDR$/i, 'Address')
          .replace(/^PHONE$/i, 'Phone')
          .replace(/^EMAIL$/i, 'Email')
          .replace(/^ADDRESS$/i, 'Address')
          .replace(/_/g, ' '); // Replace underscores with spaces

        // Title case each word
        formatted = formatted
          .split(' ')
          .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
          .join(' ');

        return formatted;
      });

    return parts.join(' + ');
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

          {/* Match Details Section - Only shown for Senzing results */}
          {lastResult.matchDetails && lastResult.resolutionMethod === 'senzing' && (
            <div className="mt-4 pt-4 border-t border-green-200">
              <button
                onClick={() => setShowMatchDetails(!showMatchDetails)}
                className="flex items-center justify-between w-full text-sm font-medium text-green-900 hover:text-green-700"
              >
                <span>Match Details</span>
                <svg
                  className={`w-5 h-5 transform transition-transform ${showMatchDetails ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>

              {showMatchDetails && (
                <div className="mt-3 space-y-4">
                  {/* Match Quality Distribution */}
                  <div>
                    <div className="flex items-center gap-1 mb-2">
                      <h5 className="text-xs font-semibold text-green-900">
                        Match Quality Distribution
                      </h5>
                      <Tooltip text="Shows how confident Senzing is about each entity match. High confidence means strong evidence that entities are the same person/organization. This counts individual record-level matches, not entity groups.">
                        <svg
                          className="w-4 h-4 text-green-700"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path
                            fillRule="evenodd"
                            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </Tooltip>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div className="bg-white rounded p-2 border border-green-200">
                        <div className="text-gray-500">High Confidence</div>
                        <div className="text-lg font-semibold text-green-700">
                          {lastResult.matchDetails.matchQualityDistribution.high}
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5">record matches</div>
                      </div>
                      <div className="bg-white rounded p-2 border border-green-200">
                        <div className="text-gray-500">Medium Confidence</div>
                        <div className="text-lg font-semibold text-yellow-600">
                          {lastResult.matchDetails.matchQualityDistribution.medium}
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5">record matches</div>
                      </div>
                      <div className="bg-white rounded p-2 border border-green-200">
                        <div className="text-gray-500">Low Confidence</div>
                        <div className="text-lg font-semibold text-orange-600">
                          {lastResult.matchDetails.matchQualityDistribution.low}
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5">record matches</div>
                      </div>
                    </div>
                  </div>

                  {/* Common Match Keys */}
                  {Object.keys(lastResult.matchDetails.commonMatchKeys).length > 0 && (
                    <div>
                      <div className="flex items-center gap-1 mb-2">
                        <h5 className="text-xs font-semibold text-green-900">
                          How Entities Were Matched
                        </h5>
                        <Tooltip text="Shows which combinations of attributes Senzing used to determine entities are the same. For example, 'Name + Date of Birth' means Senzing matched entities that had the same name AND date of birth. The count shows how many times each combination was used.">
                          <svg
                            className="w-4 h-4 text-green-700"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                          >
                            <path
                              fillRule="evenodd"
                              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </Tooltip>
                      </div>
                      <div className="bg-white rounded p-3 border border-green-200 space-y-1">
                        {Object.entries(lastResult.matchDetails.commonMatchKeys)
                          .slice(0, 5)
                          .map(([key, count]) => (
                            <div key={key} className="flex justify-between text-xs items-center">
                              <span className="text-gray-700">{formatMatchKey(key)}</span>
                              <span className="font-medium text-green-700">
                                {count} record{count !== 1 ? 's' : ''} matched this way
                              </span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}

                  {/* Feature Scores - Only show if we have scores > 0 */}
                  {(() => {
                    const featuresWithScores = Object.entries(
                      lastResult.matchDetails.featureScores || {}
                    ).filter(([_, scores]) => scores.average > 0);

                    if (featuresWithScores.length === 0) {
                      return null; // Don't show section at all if no scores
                    }

                    return (
                      <div>
                        <div className="flex items-center gap-1 mb-2">
                          <h5 className="text-xs font-semibold text-green-900">Attributes Used</h5>
                          <Tooltip text="Shows which types of attributes were found in the matched entities. A score of 100 means the attribute was present in all matched records. Lower scores indicate the attribute was found in some but not all records, or match quality varies.">
                            <svg
                              className="w-4 h-4 text-green-700"
                              fill="currentColor"
                              viewBox="0 0 20 20"
                            >
                              <path
                                fillRule="evenodd"
                                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                                clipRule="evenodd"
                              />
                            </svg>
                          </Tooltip>
                        </div>
                        <div className="bg-white rounded p-3 border border-green-200 space-y-1">
                          {featuresWithScores.map(([feature, scores]) => (
                            <div
                              key={feature}
                              className="flex justify-between text-xs items-center"
                            >
                              <span className="text-gray-700 font-medium">{feature}</span>
                              <div className="flex items-center gap-2">
                                <div className="w-24 bg-gray-200 rounded-full h-2">
                                  <div
                                    className="bg-green-600 h-2 rounded-full"
                                    style={{ width: `${Math.min(100, scores.average)}%` }}
                                  />
                                </div>
                                <span className="font-medium text-green-700 w-8 text-right">
                                  {scores.average}%
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })()}

                  {/* Resolution Rules */}
                  {Object.keys(lastResult.matchDetails.resolutionRules).length > 0 && (
                    <div>
                      <div className="flex items-center gap-1 mb-2">
                        <h5 className="text-xs font-semibold text-green-900">Senzing Rules Used</h5>
                        <Tooltip text="Shows which Senzing resolution rules were applied during entity matching. Each rule defines specific criteria for when entities should be considered the same. The count shows how many times each rule was triggered.">
                          <svg
                            className="w-4 h-4 text-green-700"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                          >
                            <path
                              fillRule="evenodd"
                              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </Tooltip>
                      </div>
                      <div className="bg-white rounded p-3 border border-green-200 space-y-1">
                        {Object.entries(lastResult.matchDetails.resolutionRules)
                          .slice(0, 5)
                          .map(([rule, count]) => (
                            <div key={rule} className="flex justify-between text-xs items-center">
                              <span className="text-gray-700 font-mono text-xs">{rule}</span>
                              <span className="font-medium text-green-700">
                                {count} time{count !== 1 ? 's' : ''}
                              </span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default EntityResolutionPanel;
