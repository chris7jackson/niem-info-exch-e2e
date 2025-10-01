import { useState, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { CheckCircleIcon, CloudArrowUpIcon, XMarkIcon, ArrowUpIcon, ArrowDownIcon, StarIcon } from '@heroicons/react/24/outline';
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid';
import apiClient, { Schema } from '../lib/api';
import ExpandableError from './ExpandableError';

interface FilePreview {
  file: File;
  id: string;
}

export default function SchemaManager() {
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [skipNiemResolution, setSkipNiemResolution] = useState(false);
  const [filePreviews, setFilePreviews] = useState<FilePreview[]>([]);

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

  const handleFilesSelected = (files: File[]) => {
    // Validate all files are XSD
    const invalidFiles = files.filter(file => !file.name.endsWith('.xsd'));
    if (invalidFiles.length > 0) {
      setError(`Please upload only XSD files. Invalid files: ${invalidFiles.map(f => f.name).join(', ')}`);
      return;
    }

    // Add files to preview list
    const newPreviews: FilePreview[] = files.map(file => ({
      file,
      id: Math.random().toString(36).substring(7)
    }));
    setFilePreviews([...filePreviews, ...newPreviews]);
    setError(null);
  };

  const handleSchemaUpload = async () => {
    if (filePreviews.length === 0) return;

    try {
      setUploading(true);
      setError(null);
      const files = filePreviews.map(fp => fp.file);
      const result = await apiClient.uploadSchema(files, skipNiemResolution);

      // Check NIEM NDR validation status
      if (result.niem_ndr_report && result.niem_ndr_report.status === 'pass') {
        await loadSchemas();
        setFilePreviews([]); // Clear previews on success
      } else if (result.niem_ndr_report && result.niem_ndr_report.status === 'fail') {
        const errors = result.niem_ndr_report.violations
          .filter((v: any) => v.type === 'error')
          .map((v: any) => v.message);
        const errorMessage = `Schema upload rejected due to NIEM NDR validation failures. Found ${errors.length} NIEM NDR violations: ${errors.join('; ')}.`;
        setError(errorMessage);
      } else {
        // If no validation report or other status, assume success
        await loadSchemas();
        setFilePreviews([]); // Clear previews on success
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const removeFile = (id: string) => {
    setFilePreviews(filePreviews.filter(fp => fp.id !== id));
  };

  const moveFile = (index: number, direction: 'up' | 'down') => {
    const newPreviews = [...filePreviews];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;

    if (targetIndex < 0 || targetIndex >= newPreviews.length) return;

    [newPreviews[index], newPreviews[targetIndex]] = [newPreviews[targetIndex], newPreviews[index]];
    setFilePreviews(newPreviews);
  };

  const setPrimaryFile = (index: number) => {
    if (index === 0) return; // Already primary
    const newPreviews = [...filePreviews];
    const [file] = newPreviews.splice(index, 1);
    newPreviews.unshift(file);
    setFilePreviews(newPreviews);
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
    onDrop: handleFilesSelected,
    accept: {
      'application/xml': ['.xsd'],
      'text/xml': ['.xsd'],
    },
    maxFiles: 10,
  });

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Schema Management</h2>
        <p className="mt-1 text-sm text-gray-600">
          Upload and manage NIEM XSD schemas for data validation. You can upload multiple related XSD files together.
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
        <h3 className="text-lg font-medium text-gray-900 mb-4">Upload XSD Schema(s)</h3>

        {/* Skip NIEM Resolution Option */}
        <div className="mb-6">
          <label className="flex items-start space-x-3">
            <input
              type="checkbox"
              checked={skipNiemResolution}
              onChange={(e) => setSkipNiemResolution(e.target.checked)}
              className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <div className="min-w-0 flex-1">
              <span className="text-sm font-medium text-gray-700">
                Skip NIEM dependency resolution
              </span>
              <p className="text-sm text-gray-500 mt-1">
                Use this option when uploading complete, self-contained schema sets that include all required NIEM dependencies.
                This will skip automatic NIEM schema resolution and use only the files you upload.
              </p>
            </div>
          </label>
        </div>

        <div className="space-y-4">
          {/* Drop Zone - Always visible */}
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
              <p className="mt-2 text-sm text-gray-600">Drop the XSD file(s) here</p>
            ) : (
              <>
                <p className="mt-2 text-sm text-gray-600">
                  {filePreviews.length > 0
                    ? 'Drag and drop more XSD file(s) here, or click to select'
                    : 'Drag and drop XSD file(s) here, or click to select'}
                </p>
                <p className="text-xs text-gray-500">XSD files only, up to 10 files, 20MB total</p>
              </>
            )}
          </div>

          {/* File Preview List */}
          {filePreviews.length > 0 && (
            <>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="flex items-start">
                <StarIconSolid className="h-5 w-5 text-blue-600 mr-2 mt-0.5" />
                <div className="text-sm text-blue-800">
                  <strong>Primary file:</strong> The first file in the list will be used as the primary schema.
                  Use the controls to reorder files or set a different file as primary.
                </div>
              </div>
            </div>

            <div className="border border-gray-200 rounded-lg divide-y divide-gray-200">
              {filePreviews.map((fp, index) => (
                <div key={fp.id} className={`p-4 ${index === 0 ? 'bg-blue-50' : 'bg-white'}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center flex-1 min-w-0">
                      {index === 0 && (
                        <StarIconSolid className="h-5 w-5 text-blue-600 mr-2 flex-shrink-0" />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {fp.file.name}
                          </p>
                          {index === 0 && (
                            <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                              Primary
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {formatFileSize(fp.file.size)}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center space-x-1 ml-4">
                      {index !== 0 && (
                        <button
                          onClick={() => setPrimaryFile(index)}
                          className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                          title="Set as primary"
                        >
                          <StarIcon className="h-5 w-5" />
                        </button>
                      )}
                      <button
                        onClick={() => moveFile(index, 'up')}
                        disabled={index === 0}
                        className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed rounded hover:bg-gray-100"
                        title="Move up"
                      >
                        <ArrowUpIcon className="h-5 w-5" />
                      </button>
                      <button
                        onClick={() => moveFile(index, 'down')}
                        disabled={index === filePreviews.length - 1}
                        className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed rounded hover:bg-gray-100"
                        title="Move down"
                      >
                        <ArrowDownIcon className="h-5 w-5" />
                      </button>
                      <button
                        onClick={() => removeFile(fp.id)}
                        className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Remove"
                      >
                        <XMarkIcon className="h-5 w-5" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between pt-2">
              <button
                onClick={() => setFilePreviews([])}
                className="text-sm text-gray-600 hover:text-gray-800"
              >
                Clear all
              </button>
              <button
                onClick={handleSchemaUpload}
                disabled={uploading || filePreviews.length === 0}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploading ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Uploading...
                  </>
                ) : (
                  <>
                    <CloudArrowUpIcon className="h-5 w-5 mr-2" />
                    Upload {filePreviews.length} {filePreviews.length === 1 ? 'File' : 'Files'}
                  </>
                )}
              </button>
            </div>
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
                        {schema.primary_filename || schema.filename}
                        {schema.all_filenames && schema.all_filenames.length > 1 && (
                          <span className="ml-2 text-xs text-gray-500">
                            (+{schema.all_filenames.length - 1} more files)
                          </span>
                        )}
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
                      {schema.all_filenames && schema.all_filenames.length > 1 && (
                        <div className="mt-1 text-xs text-gray-400">
                          Files: {schema.all_filenames.join(', ')}
                        </div>
                      )}
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