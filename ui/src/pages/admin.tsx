import { useState } from 'react';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import apiClient from '../lib/api';

interface ResetCounts {
  minio_objects?: number;
  minio_buckets?: number;
  neo4j_nodes?: number;
  neo4j_relationships?: number;
  neo4j_indexes?: number;
  neo4j_constraints?: number;
  schemas: number;
}

export default function AdminPage() {
  const [resetOptions, setResetOptions] = useState({
    minio: false,
    neo4j: false,
    schema: false,
  });
  const [counts, setCounts] = useState<ResetCounts | null>(null);
  const [confirmToken, setConfirmToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDryRun = async () => {
    try {
      setLoading(true);
      setError(null);

      const result = await apiClient.resetSystem({
        ...resetOptions,
        dry_run: true
      });

      setCounts(result.counts);
      setConfirmToken(result.confirm_token);
      setMessage(result.message);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Dry run failed');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (!confirmToken) {
      setError('No confirm token available. Please run dry run first.');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const result = await apiClient.resetSystem({
        ...resetOptions,
        dry_run: false,
        confirm_token: confirmToken
      });

      setMessage(result.message);
      setCounts(null);
      setConfirmToken(null);
      setResetOptions({
        minio: false,
        neo4j: false,
        schema: false,
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Reset failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">System Administration</h1>
        <p className="mt-1 text-sm text-gray-600">
          Administrative tools for managing the NIEM system.
        </p>
      </div>

      {/* Warning Banner */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
        <div className="flex">
          <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400" />
          <div className="ml-3">
            <h3 className="text-sm font-medium text-yellow-800">Warning</h3>
            <p className="mt-1 text-sm text-yellow-700">
              These administrative actions can permanently delete data. Use with caution.
              Always run a dry run first to see what will be affected.
            </p>
          </div>
        </div>
      </div>

      {message && (
        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <div className="text-sm text-blue-700">{message}</div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="text-sm text-red-700">{error}</div>
        </div>
      )}

      {/* Reset System */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Reset System Components</h2>

        <div className="space-y-4">
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-gray-900">Select components to reset:</h3>

            <div className="space-y-2">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={resetOptions.minio}
                  onChange={(e) => setResetOptions(prev => ({ ...prev, minio: e.target.checked }))}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">
                  MinIO Object Storage (removes all objects and buckets)
                </span>
              </label>


              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={resetOptions.neo4j}
                  onChange={(e) => setResetOptions(prev => ({ ...prev, neo4j: e.target.checked }))}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">
                  Neo4j Graph Database (all nodes and relationships)
                </span>
              </label>

              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={resetOptions.schema}
                  onChange={(e) => setResetOptions(prev => ({ ...prev, schema: e.target.checked }))}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">
                  Schema Registry (uploaded schemas and metadata)
                </span>
              </label>
            </div>
          </div>

          {/* Current Counts */}
          {counts && (
            <div className="bg-gray-50 rounded-md p-4">
              <h4 className="text-sm font-medium text-gray-900 mb-2">Current System Counts:</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">Schemas:</span>
                  <span className="ml-2 font-medium">{counts.schemas}</span>
                </div>
                {counts.minio_objects !== undefined && (
                  <div>
                    <span className="text-gray-600">MinIO Objects:</span>
                    <span className="ml-2 font-medium">{counts.minio_objects}</span>
                  </div>
                )}
                {counts.minio_buckets !== undefined && (
                  <div>
                    <span className="text-gray-600">MinIO Buckets:</span>
                    <span className="ml-2 font-medium">{counts.minio_buckets}</span>
                  </div>
                )}
                {counts.neo4j_nodes !== undefined && (
                  <div>
                    <span className="text-gray-600">Neo4j Nodes:</span>
                    <span className="ml-2 font-medium">{counts.neo4j_nodes}</span>
                  </div>
                )}
                {counts.neo4j_relationships !== undefined && (
                  <div>
                    <span className="text-gray-600">Neo4j Relationships:</span>
                    <span className="ml-2 font-medium">{counts.neo4j_relationships}</span>
                  </div>
                )}
                {counts.neo4j_indexes !== undefined && (
                  <div>
                    <span className="text-gray-600">Neo4j Indexes:</span>
                    <span className="ml-2 font-medium">{counts.neo4j_indexes}</span>
                  </div>
                )}
                {counts.neo4j_constraints !== undefined && (
                  <div>
                    <span className="text-gray-600">Neo4j Constraints:</span>
                    <span className="ml-2 font-medium">{counts.neo4j_constraints}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex space-x-3">
            <button
              onClick={handleDryRun}
              disabled={loading}
              className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            >
              {loading ? 'Running...' : 'Dry Run'}
            </button>

            {confirmToken && (
              <button
                onClick={handleReset}
                disabled={loading}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
              >
                {loading ? 'Resetting...' : 'Execute Reset'}
              </button>
            )}
          </div>

          {confirmToken && (
            <div className="text-xs text-gray-500">
              Confirm token generated. You can now execute the reset operation.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}