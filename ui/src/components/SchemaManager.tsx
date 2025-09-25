import { useState, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { CheckCircleIcon, CloudArrowUpIcon } from '@heroicons/react/24/outline';
import apiClient, { Schema } from '../lib/api';
import ExpandableError from './ExpandableError';

export default function SchemaManager() {
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadSchemas();
  }, []);

  const loadSchemas = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getSchemas();
      setSchemas(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load schemas');
    } finally {
      setLoading(false);
    }
  };

  const handleSchemaUpload = async (files: File[]) => {
    if (files.length === 0) return;

    const file = files[0];
    if (!file.name.endsWith('.xsd')) {
      setError('Please upload an XSD file');
      return;
    }

    try {
      setUploading(true);
      setError(null);
      const result = await apiClient.uploadSchema(file);

      // Check NIEM NDR validation status
      if (result.niem_ndr_report && result.niem_ndr_report.status === 'pass') {
        await loadSchemas();
      } else if (result.niem_ndr_report && result.niem_ndr_report.status === 'fail') {
        const errors = result.niem_ndr_report.violations
          .filter((v: any) => v.type === 'error')
          .map((v: any) => v.message);
        const errorMessage = `Schema upload rejected due to NIEM NDR validation failures. Found ${errors.length} NIEM NDR violations: ${errors.join('; ')}.`;
        setError(errorMessage);
      } else {
        // If no validation report or other status, assume success
        await loadSchemas();
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleActivateSchema = async (schemaId: string) => {
    try {
      await apiClient.activateSchema(schemaId);
      await loadSchemas();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Activation failed');
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleSchemaUpload,
    accept: {
      'application/xml': ['.xsd'],
      'text/xml': ['.xsd'],
    },
    maxFiles: 1,
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Schema Management</h2>
        <p className="mt-1 text-sm text-gray-600">
          Upload and manage NIEM XSD schemas for data validation.
        </p>
      </div>

      {error && (
        <ExpandableError
          title="Schema Upload Error"
          message={error}
          maxLength={150}
        />
      )}

      {/* Upload Area */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Upload XSD Schema</h3>

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

          {uploading ? (
            <p className="mt-2 text-sm text-gray-600">Uploading and validating...</p>
          ) : isDragActive ? (
            <p className="mt-2 text-sm text-gray-600">Drop the XSD file here</p>
          ) : (
            <>
              <p className="mt-2 text-sm text-gray-600">
                Drag and drop an XSD file here, or click to select
              </p>
              <p className="text-xs text-gray-500">XSD files only, up to 20MB</p>
            </>
          )}
        </div>
      </div>

      {/* Schemas List */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">Uploaded Schemas</h3>
        </div>

        {loading ? (
          <div className="p-6 text-center">
            <div className="text-sm text-gray-500">Loading schemas...</div>
          </div>
        ) : schemas.length === 0 ? (
          <div className="p-6 text-center">
            <div className="text-sm text-gray-500">No schemas uploaded yet</div>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {schemas.map((schema) => (
              <div key={schema.schema_id} className="p-6">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center">
                      <h4 className="text-sm font-medium text-gray-900">
                        {schema.filename}
                      </h4>
                      {schema.active && (
                        <CheckCircleIcon className="ml-2 h-5 w-5 text-green-500" />
                      )}
                    </div>
                    <div className="mt-1 text-sm text-gray-500">
                      <span>Schema ID: {schema.schema_id.substring(0, 8)}...</span>
                      <span className="ml-4">
                        Uploaded: {new Date(schema.uploaded_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    {schema.active ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        Active
                      </span>
                    ) : (
                      <button
                        onClick={() => handleActivateSchema(schema.schema_id)}
                        className="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded text-blue-700 bg-blue-100 hover:bg-blue-200"
                      >
                        Activate
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}