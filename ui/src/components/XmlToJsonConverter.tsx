import { useState, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { CloudArrowUpIcon, DocumentIcon, XMarkIcon } from '@heroicons/react/24/outline';
import apiClient, { Schema, BatchConversionResult } from '../lib/api';
import ConversionResults from './ConversionResults';

export default function XmlToJsonConverter() {
  const [activeSchema, setActiveSchema] = useState<Schema | null>(null);
  const [allSchemas, setAllSchemas] = useState<Schema[]>([]);
  const [selectedSchemaId, setSelectedSchemaId] = useState<string>('');
  const [files, setFiles] = useState<File[]>([]);
  const [includeContext, setIncludeContext] = useState(false);
  const [converting, setConverting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [batchResult, setBatchResult] = useState<BatchConversionResult | null>(null);

  useEffect(() => {
    loadSchemas();
  }, []);

  const loadSchemas = async () => {
    try {
      const schemas = await apiClient.getSchemas();
      setAllSchemas(schemas);
      const active = schemas.find(s => s.active);
      setActiveSchema(active || null);
      // Default to active schema
      if (active) {
        setSelectedSchemaId(active.schema_id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load schemas');
    }
  };

  const handleFileDrop = (acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setFiles(prev => [...prev, ...acceptedFiles]);
      setError(null);
      setBatchResult(null); // Clear previous results
    }
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
    if (files.length === 1) {
      // If removing the last file, clear results
      setBatchResult(null);
    }
  };

  const clearAllFiles = () => {
    setFiles([]);
    setBatchResult(null);
  };

  const handleConvert = async () => {
    if (files.length === 0) {
      setError('Please select at least one XML file to convert');
      return;
    }

    if (files.length > 10) {
      setError('Maximum 10 files allowed per batch. Please remove some files.');
      return;
    }

    if (!selectedSchemaId && !activeSchema) {
      setError('No schema selected. Please upload and activate a schema first.');
      return;
    }

    try {
      setConverting(true);
      setError(null);
      setBatchResult(null);

      const result = await apiClient.convertXmlToJson(
        files,
        selectedSchemaId || undefined,
        includeContext
      );

      setBatchResult(result);
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail;
      if (typeof errorDetail === 'string') {
        setError(errorDetail);
      } else if (typeof errorDetail === 'object' && errorDetail.message) {
        setError(errorDetail.message);
      } else {
        setError(err.message || 'Conversion failed');
      }
    } finally {
      setConverting(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleFileDrop,
    accept: {
      'application/xml': ['.xml'],
      'text/xml': ['.xml']
    },
    multiple: true,
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">XML to JSON Converter</h2>
        <p className="mt-1 text-sm text-gray-600">
          Convert NIEM XML messages to JSON format using the NIEMTran tool.
          Supports batch processing (max 10 files). This is a demo utility that converts files without storing or ingesting them.
        </p>
      </div>

      {/* Schema Selection */}
      <div className="bg-white shadow rounded-lg p-4">
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-medium text-gray-900">Schema Selection</h3>
            {allSchemas.length === 0 ? (
              <p className="text-sm text-red-600 mt-2">
                No schemas available. Please upload and activate a schema first.
              </p>
            ) : (
              <div className="mt-2">
                <select
                  value={selectedSchemaId}
                  onChange={(e) => setSelectedSchemaId(e.target.value)}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                >
                  {allSchemas.map((schema) => (
                    <option key={schema.schema_id} value={schema.schema_id}>
                      {schema.primary_filename || schema.filename}
                      {schema.active ? ' (Active)' : ''}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-500">
                  Select the schema to use for conversion
                </p>
              </div>
            )}
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              id="includeContext"
              checked={includeContext}
              onChange={(e) => setIncludeContext(e.target.checked)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <label htmlFor="includeContext" className="ml-2 block text-sm text-gray-900">
              Include complete @context in result
            </label>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-4">
          <div className="text-sm font-medium text-red-800">{error}</div>
        </div>
      )}

      {/* File Upload Area */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Select XML Files</h3>

        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
            isDragActive
              ? 'border-blue-400 bg-blue-50'
              : 'border-gray-300 hover:border-gray-400'
          }`}
        >
          <input {...getInputProps()} />
          <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />

          {isDragActive ? (
            <p className="mt-2 text-sm text-gray-600">Drop the XML files here</p>
          ) : (
            <>
              <p className="mt-2 text-sm text-gray-600">
                Drag and drop XML files here, or click to select
              </p>
              <p className="text-xs text-gray-500">XML files only (max 10 files)</p>
            </>
          )}
        </div>

        {/* Selected Files */}
        {files.length > 0 && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-medium text-gray-900">
                Selected Files ({files.length})
              </h4>
              {files.length > 1 && (
                <button
                  onClick={clearAllFiles}
                  className="text-sm text-red-600 hover:text-red-500"
                >
                  Clear All
                </button>
              )}
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {files.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between bg-gray-50 p-3 rounded"
                >
                  <div className="flex items-center min-w-0 flex-1">
                    <DocumentIcon className="h-5 w-5 text-gray-400 mr-2 flex-shrink-0" />
                    <span className="text-sm text-gray-900 truncate">{file.name}</span>
                    <span className="text-xs text-gray-500 ml-2 flex-shrink-0">
                      ({(file.size / 1024).toFixed(1)} KB)
                    </span>
                  </div>
                  <button
                    onClick={() => removeFile(index)}
                    className="ml-2 text-gray-400 hover:text-red-500 flex-shrink-0"
                    aria-label="Remove file"
                  >
                    <XMarkIcon className="h-5 w-5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Convert Button */}
        <div className="mt-6">
          <button
            onClick={handleConvert}
            disabled={converting || files.length === 0 || allSchemas.length === 0}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {converting
              ? `Converting ${files.length} file${files.length > 1 ? 's' : ''}...`
              : `Convert ${files.length} file${files.length > 1 ? 's' : ''} to JSON`}
          </button>
          {files.length > 0 && (
            <p className="mt-2 text-xs text-center text-gray-500">
              Files will be processed with controlled concurrency (max 3 at a time)
            </p>
          )}
        </div>
      </div>

      {/* Conversion Results */}
      {batchResult && (
        <ConversionResults results={batchResult} />
      )}
    </div>
  );
}
