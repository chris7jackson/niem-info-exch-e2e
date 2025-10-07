import React from 'react';
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline';
import { IngestResult, IngestFileResult } from '../lib/api';
import IngestValidationErrors from './IngestValidationErrors';

interface IngestResultsProps {
  results: IngestResult;
}

export default function IngestResults({ results }: IngestResultsProps) {
  const successfulFiles = results.results.filter(r => r.status === 'success').length;
  const failedFiles = results.results.filter(r => r.status === 'failed').length;

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">Ingestion Results</h3>

      {/* Summary */}
      <div className="bg-gray-50 p-4 rounded-lg mb-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-gray-900">{results.files_processed}</div>
            <div className="text-sm text-gray-600">Files Processed</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-green-600">{successfulFiles}</div>
            <div className="text-sm text-gray-600">Successful</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-red-600">{failedFiles}</div>
            <div className="text-sm text-gray-600">Failed</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-blue-600">{results.total_nodes_created}</div>
            <div className="text-sm text-gray-600">Nodes Created</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-purple-600">{results.total_relationships_created}</div>
            <div className="text-sm text-gray-600">Relationships</div>
          </div>
        </div>
      </div>

      {/* File Details */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-gray-900">File Details</h4>
        {results.results.map((file, index) => (
          <div key={index} className="space-y-2">
            <div className="flex items-center justify-between bg-gray-50 p-3 rounded">
              <div className="flex items-center">
                {file.status === 'success' ? (
                  <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                ) : (
                  <XCircleIcon className="h-5 w-5 text-red-500 mr-2" />
                )}
                <span className="text-sm font-medium text-gray-900">{file.filename}</span>
              </div>
              <div className="text-right">
                {file.status === 'success' ? (
                  <div className="text-sm text-gray-600">
                    {file.nodes_created || 0} nodes, {file.relationships_created || 0} relationships
                  </div>
                ) : (
                  <div className="text-sm text-red-600">
                    {file.validation_details ? 'Validation failed' : (file.error || 'Unknown error')}
                  </div>
                )}
              </div>
            </div>
            {/* Show detailed validation errors if available */}
            {file.status === 'failed' && file.validation_details && (
              <IngestValidationErrors
                filename={file.filename}
                validationResult={file.validation_details}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}