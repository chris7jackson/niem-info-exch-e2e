import React, { useState } from 'react';
import {
  ExclamationTriangleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import { ValidationResult, ValidationError } from '../lib/api';

interface IngestValidationErrorsProps {
  readonly filename: string;
  readonly validationResult: ValidationResult;
}

export default function IngestValidationErrors({
  filename,
  validationResult,
}: IngestValidationErrorsProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const { errors, warnings, summary } = validationResult;
  const totalIssues = errors.length + warnings.length;

  if (totalIssues === 0) {
    return null;
  }

  const renderValidationError = (error: ValidationError, index: number | string) => {
    const location = (() => {
      if (!error.line) return error.file;
      const baseLocation = `${error.file}:${error.line}`;
      return error.column ? baseLocation + ':' + error.column : baseLocation;
    })();

    const severityColor = error.severity === 'error' ? 'text-red-700' : 'text-yellow-700';
    const bgColor = error.severity === 'error' ? 'bg-red-50' : 'bg-yellow-50';

    return (
      <div
        key={index}
        className={`${bgColor} p-3 rounded border-l-4 ${error.severity === 'error' ? 'border-red-500' : 'border-yellow-500'}`}
      >
        <div className="flex items-start">
          <ExclamationTriangleIcon
            className={`h-5 w-5 ${severityColor} mr-2 flex-shrink-0 mt-0.5`}
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-mono font-semibold text-gray-600">{location}</span>
              {error.rule && (
                <span className="text-xs bg-gray-200 px-2 py-0.5 rounded">{error.rule}</span>
              )}
              <span
                className="text-xs uppercase font-semibold"
                style={{ color: error.severity === 'error' ? '#991b1b' : '#92400e' }}
              >
                {error.severity}
              </span>
            </div>
            <p className={`mt-1 text-sm ${severityColor} break-words`}>{error.message}</p>
            {error.context && (
              <p className="mt-1 text-xs text-gray-600 font-mono">{error.context}</p>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="mt-2 border border-red-200 rounded-lg overflow-hidden">
      {/* Header - Always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full bg-red-50 px-4 py-3 flex items-center justify-between hover:bg-red-100 transition-colors"
      >
        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDownIcon className="h-5 w-5 text-red-600" />
          ) : (
            <ChevronRightIcon className="h-5 w-5 text-red-600" />
          )}
          <ExclamationTriangleIcon className="h-5 w-5 text-red-600" />
          <div className="text-left">
            <div className="text-sm font-medium text-red-900">Validation Failed: {filename}</div>
            <div className="text-xs text-red-700">{summary}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {errors.length > 0 && (
            <span className="bg-red-600 text-white text-xs px-2 py-1 rounded">
              {errors.length} error{errors.length !== 1 ? 's' : ''}
            </span>
          )}
          {warnings.length > 0 && (
            <span className="bg-yellow-600 text-white text-xs px-2 py-1 rounded">
              {warnings.length} warning{warnings.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </button>

      {/* Expandable Content */}
      {isExpanded && (
        <div className="bg-white p-4 space-y-3">
          {/* Errors Section */}
          {errors.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-red-900 mb-2">Errors ({errors.length})</h4>
              <div className="space-y-2">
                {errors.map((error, index) => renderValidationError(error, index))}
              </div>
            </div>
          )}

          {/* Warnings Section */}
          {warnings.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-yellow-900 mb-2">
                Warnings ({warnings.length})
              </h4>
              <div className="space-y-2">
                {warnings.map((warning, index) =>
                  renderValidationError(warning, `warning-${index}`)
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
