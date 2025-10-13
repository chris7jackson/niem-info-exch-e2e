import { useState, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { CloudArrowUpIcon, DocumentIcon } from '@heroicons/react/24/outline';
import apiClient, { Schema, IngestResult } from '../lib/api';
import IngestResults from './IngestResults';
import UploadedFilesList from './UploadedFilesList';

interface UploadPanelProps {
  readonly contentType: 'xml' | 'json';
}

export default function UploadPanel({ contentType }: UploadPanelProps) {
  const [activeSchema, setActiveSchema] = useState<Schema | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ingestResult, setIngestResult] = useState<IngestResult | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  useEffect(() => {
    loadActiveSchema();
  }, []);

  const loadActiveSchema = async () => {
    try {
      const schemas = await apiClient.getSchemas();
      const active = schemas.find(s => s.active);
      setActiveSchema(active || null);
    } catch (err: any) {
      setError(err.message || 'Failed to load active schema');
    }
  };

  const handleFileDrop = (acceptedFiles: File[]) => {
    setFiles(prev => [...prev, ...acceptedFiles]);
    setError(null);
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      setError('Please select files to upload');
      return;
    }

    if (!activeSchema) {
      setError('No active schema found. Please upload and activate a schema first.');
      return;
    }

    try {
      setUploading(true);
      setError(null);

      let result: IngestResult;
      if (contentType === 'xml') {
        result = await apiClient.ingestXml(files);
      } else {
        result = await apiClient.ingestJson(files);
      }

      setIngestResult(result);
      setFiles([]);
      // Trigger refresh of uploaded files list
      setRefreshTrigger(prev => prev + 1);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleFileDrop,
    accept: contentType === 'xml'
      ? { 'application/xml': ['.xml'], 'text/xml': ['.xml'] }
      : { 'application/json': ['.json'] },
    multiple: true,
  });

  const fileExtension = contentType === 'xml' ? 'XML' : 'JSON';

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Upload {fileExtension} Data</h2>
        <p className="mt-1 text-sm text-gray-600">
          Upload {fileExtension} files for validation and ingestion into the graph database.
        </p>
      </div>

      {/* Active Schema Status */}
      <div className="bg-white shadow rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <h3 className="text-sm font-medium text-gray-900">
              {contentType === 'json' ? 'Validation Schema' : 'Active Schema'}
            </h3>
            {activeSchema ? (
              <>
                {contentType === 'xml' ? (
                  <p className="text-sm text-gray-600">
                    {activeSchema.primary_filename}
                  </p>
                ) : (
                  <div className="mt-1">
                    <p className="text-sm text-gray-900 font-medium">
                      {activeSchema.primary_filename.replace(/\.xsd$/i, '.json')}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      Generated via cmftool from {activeSchema.primary_filename}
                    </p>
                  </div>
                )}
              </>
            ) : (
              <p className="text-sm text-red-600">
                No active schema. Please upload and activate a schema first.
              </p>
            )}
          </div>
          <button
            onClick={loadActiveSchema}
            className="text-sm text-blue-600 hover:text-blue-500 ml-4"
          >
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-4">
          <div className="text-sm text-red-700">{error}</div>
        </div>
      )}

      {/* File Upload Area */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Select {fileExtension} Files</h3>

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
            <p className="mt-2 text-sm text-gray-600">Drop the {fileExtension} files here</p>
          ) : (
            <>
              <p className="mt-2 text-sm text-gray-600">
                Drag and drop {fileExtension} files here, or click to select
              </p>
              <p className="text-xs text-gray-500">{fileExtension} files only, multiple files supported</p>
            </>
          )}
        </div>

        {/* Selected Files */}
        {files.length > 0 && (
          <div className="mt-4 space-y-2">
            <h4 className="text-sm font-medium text-gray-900">Selected Files ({files.length})</h4>
            <div className="space-y-1">
              {files.map((file, index) => (
                <div key={`${file.name}-${file.size}-${index}`} className="flex items-center justify-between bg-gray-50 p-2 rounded">
                  <div className="flex items-center">
                    <DocumentIcon className="h-4 w-4 text-gray-400 mr-2" />
                    <span className="text-sm text-gray-900">{file.name}</span>
                    <span className="text-xs text-gray-500 ml-2">
                      ({(file.size / 1024).toFixed(1)} KB)
                    </span>
                  </div>
                  <button
                    onClick={() => removeFile(index)}
                    className="text-sm text-red-600 hover:text-red-500"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Upload Button */}
        <div className="mt-6">
          <button
            onClick={handleUpload}
            disabled={uploading || files.length === 0 || !activeSchema}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {(() => {
              if (uploading) return 'Uploading...';
              const fileText = files.length !== 1 ? 's' : '';
              return `Upload ${files.length} file${fileText}`;
            })()}
          </button>
        </div>
      </div>

      {/* Ingest Results */}
      {ingestResult && (
        <IngestResults results={ingestResult} />
      )}

      {/* Uploaded Files List */}
      <UploadedFilesList
        contentType={contentType}
        refreshTrigger={refreshTrigger}
      />
    </div>
  );
}