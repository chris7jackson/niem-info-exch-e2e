import React, { useState, useEffect, DragEvent } from 'react';
import {
  CheckCircleIcon,
  CloudArrowUpIcon,
  XMarkIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  StarIcon,
} from '@heroicons/react/24/outline';
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid';
import apiClient, { Schema } from '../lib/api';
import ExpandableError from './ExpandableError';
import ValidationResults from './ValidationResults';
import GraphSchemaDesigner from './GraphSchemaDesigner';

interface FilePreview {
  file: File;
  id: string;
  path: string; // Relative path from upload root
}

export default function SchemaManager() {
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filePreviews, setFilePreviews] = useState<FilePreview[]>([]);
  const [lastValidationResult, setLastValidationResult] = useState<unknown>(null);
  const [skipNiemNdr, setSkipNiemNdr] = useState(false);
  const [showDesigner, setShowDesigner] = useState(false);
  const [uploadedSchemaId, setUploadedSchemaId] = useState<string | null>(null);

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
    // Filter to only XSD files, ignore non-XSD files
    const xsdFiles = files.filter((file) => file.name.endsWith('.xsd'));
    const nonXsdCount = files.length - xsdFiles.length;

    // Show informational message if non-XSD files were filtered
    if (nonXsdCount > 0) {
      const xsdFilePlural = xsdFiles.length === 1 ? '' : 's';
      const nonXsdFilePlural = nonXsdCount === 1 ? '' : 's';

      let msg: string;
      if (xsdFiles.length > 0) {
        msg = `Added ${xsdFiles.length} XSD file${xsdFilePlural}, ignored ${nonXsdCount} non-XSD file${nonXsdFilePlural}`;
      } else {
        msg = `No XSD files found. ${nonXsdCount} non-XSD file${nonXsdFilePlural} ignored.`;
      }
      console.info(msg);
    }

    // Add XSD files to preview list, capturing directory paths
    const newPreviews: FilePreview[] = xsdFiles.map((file) => {
      // Try to get relative path from webkitRelativePath (when folder is selected)
      // Otherwise use just the filename
      const path = (file as any).webkitRelativePath || file.name;

      return {
        file,
        id: Math.random().toString(36).substring(7),
        path,
      };
    });
    setFilePreviews([...filePreviews, ...newPreviews]);
    setError(null);
  };

  const buildNdrErrorMessage = (result: any): string => {
    const errors = result.scheval_report.errors || [];
    const totalErrors = errors.length;
    const fileCount = errors.reduce((acc: any, e: any) => {
      acc.add(e.file || 'Unknown');
      return acc;
    }, new Set()).size;
    return `Found ${totalErrors} NIEM NDR violations across ${fileCount} file(s)`;
  };

  const buildImportErrorMessage = (result: any): string => {
    const missingCount = result.import_validation_report.missing_count || 0;
    return `Missing ${missingCount} required schema dependencies`;
  };

  const handleValidationErrors = (result: any) => {
    const ndrHasErrors =
      result.scheval_report &&
      (result.scheval_report.status === 'fail' || result.scheval_report.status === 'error');
    const importHasErrors =
      result.import_validation_report && result.import_validation_report.status === 'fail';

    if (ndrHasErrors || importHasErrors) {
      const errorParts = [];
      if (ndrHasErrors) errorParts.push(buildNdrErrorMessage(result));
      if (importHasErrors) errorParts.push(buildImportErrorMessage(result));
      setError(`Schema upload rejected: ${errorParts.join('. ')}. See details below.`);
    } else {
      loadSchemas();
      setFilePreviews([]);
    }
  };

  const handleUploadError = (err: any) => {
    console.log('Schema upload error:', err);
    console.log('Error response data:', err.response?.data);

    try {
      const detail = err.response?.data?.detail;
      console.log('Detail object:', detail);

      if (
        detail &&
        typeof detail === 'object' &&
        (detail.import_validation_report || detail.scheval_report)
      ) {
        setLastValidationResult({
          import_validation_report: detail.import_validation_report || null,
          scheval_report: detail.scheval_report || null,
        });
        setError(detail.message || 'Schema validation failed');
      } else if (typeof detail === 'string') {
        setError(detail);
      } else {
        console.error('Could not extract validation reports from error');
        setError(err.message || 'Upload failed');
      }
    } catch (parseError) {
      console.error('Error parsing response:', parseError);
      setError('Upload failed. Please check the console for details.');
    }
  };

  const handleSchemaUpload = async () => {
    if (filePreviews.length === 0) return;

    try {
      setUploading(true);
      setError(null);
      const files = filePreviews.map((fp) => fp.file);
      const filePaths = filePreviews.map((fp) => fp.path);
      const result = await apiClient.uploadSchema(files, filePaths, skipNiemNdr);

      setLastValidationResult(result);
      handleValidationErrors(result);

      // Show designer modal after successful upload
      if (result?.schema_id) {
        setUploadedSchemaId(result.schema_id);
        setShowDesigner(true);
      }
    } catch (err: any) {
      handleUploadError(err);
    } finally {
      setUploading(false);
    }
  };

  const handleDesignerClose = async (_applied: boolean) => {
    setShowDesigner(false);
    setUploadedSchemaId(null);

    // Refresh schemas list after design (whether applied or skipped)
    await loadSchemas();

    // Clear file previews after successful upload
    setFilePreviews([]);
    setLastValidationResult(null);
  };

  const removeFile = (id: string) => {
    setFilePreviews(filePreviews.filter((fp) => fp.id !== id));
  };

  const moveFile = (index: number, direction: 'up' | 'down') => {
    const newPreviews = [...filePreviews];
    const targetIndex = (() => {
      if (direction === 'up') {
        return index - 1;
      }
      return index + 1;
    })();

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

  const handleDownloadFile = async (
    schemaId: string,
    fileType: 'cmf' | 'json',
    filename: string
  ) => {
    try {
      const blob = await apiClient.downloadSchemaFile(schemaId, fileType);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Download failed');
    }
  };

  // Don't use react-dropzone's getRootProps/getInputProps since we want folder-only upload
  const [isDragActive, setIsDragActive] = useState(false);

  const handleDragEnter = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);

    const items = Array.from(e.dataTransfer.items);
    const files: File[] = [];

    // Recursively read all files from dropped folders
    const readEntries = async (entry: any) => {
      if (entry.isFile) {
        const file = await new Promise<File>((resolve) => entry.file(resolve));
        if (file.name.endsWith('.xsd')) {
          files.push(file);
        }
      } else if (entry.isDirectory) {
        const reader = entry.createReader();
        const entries = await new Promise<any[]>((resolve) => {
          reader.readEntries(resolve);
        });
        for (const subEntry of entries) {
          await readEntries(subEntry);
        }
      }
    };

    (async () => {
      for (const item of items) {
        const entry = item.webkitGetAsEntry();
        if (entry) {
          await readEntries(entry);
        }
      }
      if (files.length > 0) {
        handleFilesSelected(files);
      }
    })();
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Schema Management</h2>
        <p className="mt-1 text-sm text-gray-600">
          Upload and manage NIEM XSD schemas for data validation. You must upload ALL required files
          together, including the main schema, all NIEM reference schemas, and any custom reference
          schemas.
        </p>
      </div>

      {error && <ExpandableError title="Schema Upload Error" message={error} maxLength={300} />}

      {/* Validation Results */}
      {lastValidationResult &&
      typeof lastValidationResult === 'object' &&
      lastValidationResult !== null ? (
        <ValidationResults
          importReport={(lastValidationResult as any).import_validation_report}
          schevalReport={(lastValidationResult as any).scheval_report}
        />
      ) : null}

      {/* Upload Area */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Upload XSD Schema(s)</h3>

        {/* Important Notice */}
        <div className="mb-6 bg-amber-50 border border-amber-200 rounded-lg p-4">
          <div className="flex items-start">
            <svg
              className="h-5 w-5 text-amber-600 mt-0.5 mr-3 flex-shrink-0"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
            <div className="flex-1 text-sm">
              <p className="font-semibold text-amber-900 mb-1">Upload Complete Schema Set</p>
              <p className="text-amber-800">You must upload ALL required XSD files together:</p>
              <ul className="list-disc list-inside mt-2 space-y-1 text-amber-800">
                <li>Main schema file (will be set as primary)</li>
                <li>All NIEM reference schemas (niem-core.xsd, structures.xsd, etc.)</li>
                <li>All custom reference schemas your schema imports</li>
              </ul>
              <p className="mt-2 text-amber-800">
                All files will be validated against NIEM NDR rules and checked for missing
                dependencies.
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {/* Hidden folder input */}
          <input
            type="file"
            ref={(input) => {
              if (input) {
                input.setAttribute('webkitdirectory', '');
                input.setAttribute('directory', '');
              }
            }}
            onChange={(e) => {
              const files = Array.from(e.target.files || []);
              handleFilesSelected(files);
              e.target.value = ''; // Reset input
            }}
            style={{ display: 'none' }}
            id="folder-input"
          />

          {/* Drop Zone - Folder only */}
          <div
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => document.getElementById('folder-input')?.click()}
            className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
              isDragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
            }`}
          >
            <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
            {isDragActive ? (
              <p className="mt-2 text-sm text-gray-600">Drop the folder here</p>
            ) : (
              <>
                <p className="mt-2 text-sm font-medium text-gray-900">Select Schema Folder</p>
                <p className="mt-1 text-sm text-gray-600">
                  Drag and drop a folder containing XSD schemas, or click to browse
                </p>
                <p className="mt-1 text-xs text-gray-500">
                  All .xsd files in the folder and subfolders will be uploaded
                </p>
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
                    <strong>Primary file:</strong> The first file in the list will be used as the
                    primary schema. Use the controls to reorder files or set a different file as
                    primary.
                  </div>
                </div>
              </div>

              <div className="border border-gray-200 rounded-lg divide-y divide-gray-200">
                {filePreviews.map((fp, index) => (
                  <div
                    key={fp.id}
                    className={`p-4 ${(() => {
                      return index === 0 ? 'bg-blue-50' : 'bg-white';
                    })()}`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center flex-1 min-w-0">
                        {index === 0 && (
                          <StarIconSolid className="h-5 w-5 text-blue-600 mr-2 flex-shrink-0" />
                        )}
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center">
                            <p className="text-sm font-medium text-gray-900 truncate">{fp.path}</p>
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
                <div className="flex items-center space-x-4">
                  <button
                    onClick={() => setFilePreviews([])}
                    className="text-sm text-gray-600 hover:text-gray-800"
                  >
                    Clear all
                  </button>
                  <label className="inline-flex items-center text-sm text-gray-700">
                    <input
                      type="checkbox"
                      checked={skipNiemNdr}
                      onChange={(e) => setSkipNiemNdr(e.target.checked)}
                      className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    />
                    <span className="ml-2">Skip NIEM NDR validation</span>
                  </label>
                </div>
                <button
                  onClick={handleSchemaUpload}
                  disabled={uploading || filePreviews.length === 0}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {uploading ? (
                    <>
                      <svg
                        className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        ></circle>
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        ></path>
                      </svg>
                      Uploading...
                    </>
                  ) : (
                    <>
                      <CloudArrowUpIcon className="h-5 w-5 mr-2" />
                      Upload {filePreviews.length}{' '}
                      {(() => {
                        return filePreviews.length === 1 ? 'File' : 'Files';
                      })()}
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

        {(() => {
          if (loading) {
            return (
              <div className="p-6 text-center">
                <div className="text-sm text-gray-500">Loading schemas...</div>
              </div>
            );
          }
          if (schemas.length === 0) {
            return (
              <div className="p-6 text-center">
                <div className="text-sm text-gray-500">No schemas uploaded yet</div>
              </div>
            );
          }
          return (
            <div className="divide-y divide-gray-200">
              {schemas.map((schema) => (
                <div key={schema.schema_id} className="p-6">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center">
                        <h4 className="text-sm font-medium text-gray-900">
                          {(() => {
                            return schema.primary_filename || schema.filename;
                          })()}
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
                      <div className="mt-2 flex flex-wrap gap-2">
                        <span className="text-xs text-gray-500 mr-2">Generated files:</span>
                        {schema.cmf_filename && (
                          <button
                            onClick={() =>
                              handleDownloadFile(schema.schema_id, 'cmf', schema.cmf_filename!)
                            }
                            className="inline-flex items-center px-2 py-1 text-xs font-medium text-blue-700 bg-blue-50 rounded hover:bg-blue-100"
                          >
                            <svg
                              className="h-3 w-3 mr-1"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                              />
                            </svg>
                            {schema.cmf_filename}
                          </button>
                        )}
                        {schema.json_schema_filename && (
                          <button
                            onClick={() =>
                              handleDownloadFile(
                                schema.schema_id,
                                'json',
                                schema.json_schema_filename!
                              )
                            }
                            className="inline-flex items-center px-2 py-1 text-xs font-medium text-green-700 bg-green-50 rounded hover:bg-green-100"
                          >
                            <svg
                              className="h-3 w-3 mr-1"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                              />
                            </svg>
                            {schema.json_schema_filename}
                          </button>
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
          );
        })()}
      </div>

      {/* Graph Schema Designer Modal */}
      {uploadedSchemaId && (
        <GraphSchemaDesigner
          schemaId={uploadedSchemaId}
          open={showDesigner}
          onClose={handleDesignerClose}
        />
      )}
    </div>
  );
}
