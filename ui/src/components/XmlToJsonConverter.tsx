import { useState, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { CloudArrowUpIcon, DocumentIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import apiClient, { Schema, ConversionResult } from '../lib/api';

export default function XmlToJsonConverter() {
  const [activeSchema, setActiveSchema] = useState<Schema | null>(null);
  const [allSchemas, setAllSchemas] = useState<Schema[]>([]);
  const [selectedSchemaId, setSelectedSchemaId] = useState<string>('');
  const [file, setFile] = useState<File | null>(null);
  const [includeContext, setIncludeContext] = useState(false);
  const [converting, setConverting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[] | null>(null);
  const [conversionResult, setConversionResult] = useState<ConversionResult | null>(null);

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
      setFile(acceptedFiles[0]);
      setError(null);
      setConversionResult(null); // Clear previous result
    }
  };

  const removeFile = () => {
    setFile(null);
    setConversionResult(null);
    setValidationErrors(null);
  };

  const handleConvert = async () => {
    if (!file) {
      setError('Please select an XML file to convert');
      return;
    }

    if (!selectedSchemaId && !activeSchema) {
      setError('No schema selected. Please upload and activate a schema first.');
      return;
    }

    try {
      setConverting(true);
      setError(null);
      setValidationErrors(null);

      const result = await apiClient.convertXmlToJson(
        file,
        selectedSchemaId || undefined,
        includeContext
      );

      if (result.success) {
        setConversionResult(result);
      } else {
        setError(result.error || 'Conversion failed');
      }
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail;
      if (typeof errorDetail === 'object') {
        // Handle validation errors with detailed structure
        if (errorDetail.errors && Array.isArray(errorDetail.errors)) {
          setError(errorDetail.message || 'XML validation failed');
          setValidationErrors(errorDetail.errors);
        } else if (errorDetail.message) {
          setError(errorDetail.message);
        } else {
          setError('Conversion failed');
        }
      } else if (typeof errorDetail === 'string') {
        setError(errorDetail);
      } else {
        setError(err.message || 'Conversion failed');
      }
    } finally {
      setConverting(false);
    }
  };

  const downloadJson = () => {
    if (!conversionResult?.json_string) return;

    const blob = new Blob([conversionResult.json_string], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = file?.name?.replace('.xml', '.json') || 'converted.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleFileDrop,
    accept: {
      'application/xml': ['.xml'],
      'text/xml': ['.xml']
    },
    multiple: false,
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">XML to JSON Converter</h2>
        <p className="mt-1 text-sm text-gray-600">
          Convert NIEM XML messages to JSON format using the NIEMTran tool.
          This is a demo utility that converts files without storing or ingesting them.
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
          <div className="text-sm font-medium text-red-800 mb-2">{error}</div>
          {validationErrors && validationErrors.length > 0 && (
            <div className="mt-2 text-xs text-red-700">
              <div className="font-medium mb-1">Validation Errors:</div>
              <ul className="list-disc list-inside space-y-1">
                {validationErrors.map((err, idx) => (
                  <li key={idx} className="font-mono">{err}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* File Upload Area */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Select XML File</h3>

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
            <p className="mt-2 text-sm text-gray-600">Drop the XML file here</p>
          ) : (
            <>
              <p className="mt-2 text-sm text-gray-600">
                Drag and drop an XML file here, or click to select
              </p>
              <p className="text-xs text-gray-500">XML files only</p>
            </>
          )}
        </div>

        {/* Selected File */}
        {file && (
          <div className="mt-4">
            <h4 className="text-sm font-medium text-gray-900 mb-2">Selected File</h4>
            <div className="flex items-center justify-between bg-gray-50 p-3 rounded">
              <div className="flex items-center">
                <DocumentIcon className="h-5 w-5 text-gray-400 mr-2" />
                <span className="text-sm text-gray-900">{file.name}</span>
                <span className="text-xs text-gray-500 ml-2">
                  ({(file.size / 1024).toFixed(1)} KB)
                </span>
              </div>
              <button
                onClick={removeFile}
                className="text-sm text-red-600 hover:text-red-500"
              >
                Remove
              </button>
            </div>
          </div>
        )}

        {/* Convert Button */}
        <div className="mt-6">
          <button
            onClick={handleConvert}
            disabled={converting || !file || allSchemas.length === 0}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {converting ? 'Converting...' : 'Convert to JSON'}
          </button>
        </div>
      </div>

      {/* Conversion Result */}
      {conversionResult && conversionResult.success && (
        <div className="bg-white shadow rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">Conversion Result</h3>
            <button
              onClick={downloadJson}
              className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
            >
              <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
              Download JSON
            </button>
          </div>

          <div className="space-y-3">
            <div className="bg-green-50 rounded-md p-3">
              <p className="text-sm text-green-800">
                {conversionResult.message || 'Conversion successful'}
              </p>
            </div>

            {conversionResult.schema_filename && (
              <div className="text-xs text-gray-600">
                <span className="font-medium">Schema used:</span> {conversionResult.schema_filename}
              </div>
            )}

            {conversionResult.json_string && (
              <div>
                <label className="block text-sm font-medium text-gray-900 mb-2">
                  JSON Output Preview
                </label>
                <div className="relative">
                  <pre className="bg-gray-50 rounded-md p-4 text-xs overflow-x-auto max-h-96 overflow-y-auto border border-gray-200">
                    <code>{conversionResult.json_string}</code>
                  </pre>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
