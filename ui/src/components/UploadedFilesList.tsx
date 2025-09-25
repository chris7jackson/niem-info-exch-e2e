import { useState, useEffect } from 'react';
import { DocumentIcon, CalendarIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import apiClient, { UploadedFile } from '../lib/api';

interface UploadedFilesListProps {
  contentType?: 'xml' | 'json' | 'all';
  refreshTrigger?: number; // Used to trigger refresh from parent
}

export default function UploadedFilesList({ contentType = 'all', refreshTrigger }: UploadedFilesListProps) {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadFiles();
  }, [refreshTrigger]);

  const loadFiles = async () => {
    try {
      setLoading(true);
      setError(null);
      const uploadedFiles = await apiClient.getUploadedFiles();

      // Filter by content type if specified
      let filteredFiles = uploadedFiles;
      if (contentType !== 'all') {
        filteredFiles = uploadedFiles.filter(file => {
          const extension = file.original_name.toLowerCase().split('.').pop();
          return extension === contentType;
        });
      }

      setFiles(filteredFiles);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load uploaded files');
    } finally {
      setLoading(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatDate = (isoString: string | null): string => {
    if (!isoString) return 'Unknown';
    try {
      return new Date(isoString).toLocaleString();
    } catch {
      return 'Unknown';
    }
  };

  const getFileIcon = (filename: string) => {
    const extension = filename.toLowerCase().split('.').pop();
    return <DocumentIcon className="h-5 w-5 text-gray-400" />;
  };

  const getFileTypeColor = (filename: string) => {
    const extension = filename.toLowerCase().split('.').pop();
    switch (extension) {
      case 'xml':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'json':
        return 'bg-green-50 text-green-700 border-green-200';
      default:
        return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  if (loading) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-center py-8">
          <ArrowPathIcon className="h-6 w-6 text-gray-400 animate-spin mr-3" />
          <span className="text-gray-600">Loading uploaded files...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">
          Uploaded Files {contentType !== 'all' && `(${contentType.toUpperCase()})`}
        </h3>
        <div className="flex items-center space-x-4">
          <span className="text-sm text-gray-500">
            {files.length} file{files.length !== 1 ? 's' : ''}
          </span>
          <button
            onClick={loadFiles}
            className="text-sm text-blue-600 hover:text-blue-500 flex items-center"
          >
            <ArrowPathIcon className="h-4 w-4 mr-1" />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-4 mb-4">
          <div className="text-sm text-red-700">{error}</div>
        </div>
      )}

      {files.length === 0 ? (
        <div className="text-center py-8">
          <DocumentIcon className="mx-auto h-12 w-12 text-gray-300 mb-3" />
          <p className="text-gray-500">
            No {contentType !== 'all' ? contentType.toUpperCase() : ''} files have been uploaded yet.
          </p>
          <p className="text-sm text-gray-400 mt-1">
            Files will appear here after successful upload and ingestion.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {files.map((file) => (
            <div
              key={file.stored_name}
              className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50"
            >
              <div className="flex items-center space-x-3 flex-1">
                {getFileIcon(file.original_name)}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {file.original_name}
                    </p>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${getFileTypeColor(file.original_name)}`}
                    >
                      {file.original_name.toLowerCase().split('.').pop()?.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center text-xs text-gray-500 mt-1 space-x-4">
                    <span>{formatFileSize(file.size)}</span>
                    <span className="flex items-center">
                      <CalendarIcon className="h-3 w-3 mr-1" />
                      {formatDate(file.last_modified)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}