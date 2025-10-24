import React, { useState } from 'react';
import { CheckCircleIcon, XCircleIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import { BatchConversionResult } from '../lib/api';
import IngestValidationErrors from './IngestValidationErrors';

interface ConversionResultsProps {
  readonly results: BatchConversionResult;
}

export default function ConversionResults({ results }: ConversionResultsProps) {
  const [downloadingZip, setDownloadingZip] = useState(false);

  const downloadJson = (filename: string, jsonString: string) => {
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename.replace('.xml', '.json');
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const downloadAllAsZip = async () => {
    setDownloadingZip(true);
    try {
      // Lazy-load JSZip only when needed (saves ~100KB on initial load)
      const JSZip = (await import('jszip')).default;
      const zip = new JSZip();

      // Add all successful conversions to ZIP
      results.results
        .filter((r) => r.status === 'success' && r.json_string)
        .forEach((r) => {
          const jsonFilename = r.filename.replace('.xml', '.json');
          zip.file(jsonFilename, r.json_string!);
        });

      // Generate ZIP file
      const content = await zip.generateAsync({ type: 'blob' });

      // Trigger download
      const url = URL.createObjectURL(content);
      const a = document.createElement('a');
      a.href = url;
      a.download = `xml-to-json-conversions-${new Date().toISOString().split('T')[0]}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to create ZIP:', error);
      alert('Failed to create ZIP file. Please try downloading files individually.');
    } finally {
      setDownloadingZip(false);
    }
  };

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">Conversion Results</h3>
        {results.successful > 1 && (
          <button
            onClick={downloadAllAsZip}
            disabled={downloadingZip}
            className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
            {downloadingZip ? 'Creating ZIP...' : 'Download All as ZIP'}
          </button>
        )}
      </div>

      {/* Summary */}
      <div className="bg-gray-50 p-4 rounded-lg mb-4">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-gray-900">{results.files_processed}</div>
            <div className="text-sm text-gray-600">Files Processed</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-green-600">{results.successful}</div>
            <div className="text-sm text-gray-600">Successful</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-red-600">{results.failed}</div>
            <div className="text-sm text-gray-600">Failed</div>
          </div>
        </div>
      </div>

      {/* File Details */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-gray-900">File Details</h4>
        {results.results.map((file, index) => (
          <div key={index} className="space-y-2">
            <div className="flex items-center justify-between bg-gray-50 p-3 rounded">
              <div className="flex items-center flex-1">
                {file.status === 'success' ? (
                  <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2 flex-shrink-0" />
                ) : (
                  <XCircleIcon className="h-5 w-5 text-red-500 mr-2 flex-shrink-0" />
                )}
                <span className="text-sm font-medium text-gray-900">{file.filename}</span>
              </div>
              <div className="flex items-center gap-3">
                {file.status === 'success' ? (
                  <>
                    <div className="text-sm text-gray-600">Converted successfully</div>
                    <button
                      onClick={() => downloadJson(file.filename, file.json_string!)}
                      className="inline-flex items-center px-2 py-1 border border-transparent text-xs font-medium rounded text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                    >
                      <ArrowDownTrayIcon className="h-3 w-3 mr-1" />
                      Download
                    </button>
                  </>
                ) : (
                  <div className="text-sm text-red-600">
                    {file.validation_details ? 'Validation failed' : file.error || 'Unknown error'}
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
