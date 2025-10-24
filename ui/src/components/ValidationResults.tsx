import { useState } from 'react';
import {
  ChevronDownIcon,
  ChevronRightIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';

interface ImportInfo {
  schema_location: string;
  namespace: string;
  status: string;
  expected_filename?: string;
}

interface NamespaceUsage {
  prefix: string;
  namespace_uri: string;
  status: string;
}

interface FileImportInfo {
  filename: string;
  imports: ImportInfo[];
  namespaces_used: NamespaceUsage[];
}

interface ImportValidationReport {
  status: string;
  files: FileImportInfo[];
  summary: string;
  total_files: number;
  total_imports: number;
  total_namespaces: number;
  missing_count: number;
}

interface SchevalIssue {
  file: string;
  line: number;
  column: number;
  message: string;
  severity: string;
  rule?: string;
}

interface SchevalReport {
  status: string;
  message: string;
  conformance_target: string;
  errors: SchevalIssue[];
  warnings: SchevalIssue[];
  summary: { [key: string]: number };
  metadata?: { [key: string]: any };
}

interface ValidationResultsProps {
  readonly importReport?: ImportValidationReport;
  readonly schevalReport?: SchevalReport;
}

export default function ValidationResults({ importReport, schevalReport }: ValidationResultsProps) {
  const [expandedImports, setExpandedImports] = useState(false);
  const [expandedScheval, setExpandedScheval] = useState(true); // Default expanded for scheval
  const [expandedFiles, setExpandedFiles] = useState<{ [key: string]: boolean }>({});

  if (!importReport && !schevalReport) {
    return null;
  }

  const toggleFile = (filename: string) => {
    setExpandedFiles((prev) => ({ ...prev, [filename]: !prev[filename] }));
  };

  // Group scheval issues by file
  const schevalIssuesByFile: { [key: string]: SchevalIssue[] } = {};
  if (schevalReport) {
    [...schevalReport.errors, ...schevalReport.warnings].forEach((issue) => {
      const file = issue.file;
      if (!schevalIssuesByFile[file]) {
        schevalIssuesByFile[file] = [];
      }
      schevalIssuesByFile[file].push(issue);
    });
  }

  const importStatus = importReport?.status || 'unknown';
  const schevalStatus = schevalReport?.status || 'unknown';
  const overallSuccess = importStatus === 'pass' && schevalStatus === 'pass';

  // Debug logging
  console.log('ValidationResults - importReport:', importReport);
  console.log('ValidationResults - schevalReport:', schevalReport);

  return (
    <div className="bg-white shadow rounded-lg p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-gray-900">Validation Results</h3>
        {overallSuccess && <CheckCircleIcon className="h-6 w-6 text-green-500" />}
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm font-medium text-gray-500">NIEM NDR Validation</div>
          <div className="mt-2 flex items-center">
            {(() => {
              if (!schevalReport) {
                return <span className="text-sm text-gray-500">Not checked</span>;
              }
              if (schevalStatus === 'pass') {
                return (
                  <>
                    <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                    <span className="text-sm text-green-700">Passed</span>
                  </>
                );
              }
              if (schevalStatus === 'fail' || schevalStatus === 'error') {
                return (
                  <>
                    <XCircleIcon className="h-5 w-5 text-red-500 mr-2" />
                    <span className="text-sm text-red-700">
                      {schevalReport?.summary.error_count || 0} errors
                    </span>
                  </>
                );
              }
              return <span className="text-sm text-gray-500">Unknown</span>;
            })()}
          </div>
          {schevalReport && schevalReport.summary.warning_count > 0 && (
            <div className="mt-1 text-xs text-yellow-600">
              {schevalReport.summary.warning_count} warnings
            </div>
          )}
        </div>

        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm font-medium text-gray-500">Import Validation</div>
          <div className="mt-2 flex items-center">
            {(() => {
              if (!importReport) {
                return <span className="text-sm text-gray-500">Not checked</span>;
              }
              if (importStatus === 'pass') {
                return (
                  <>
                    <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                    <span className="text-sm text-green-700">All resolved</span>
                  </>
                );
              }
              if (importStatus === 'fail') {
                return (
                  <>
                    <XCircleIcon className="h-5 w-5 text-red-500 mr-2" />
                    <span className="text-sm text-red-700">
                      {importReport.missing_count || 0} missing
                    </span>
                  </>
                );
              }
              return <span className="text-sm text-gray-500">Unknown</span>;
            })()}
          </div>
          {importReport && importReport.status !== 'unknown' && (
            <div className="mt-1 text-xs text-gray-600">
              {importReport.total_imports} imports, {importReport.total_namespaces} namespaces
            </div>
          )}
        </div>
      </div>

      {/* NIEM NDR Violations */}
      {schevalReport && (schevalReport.errors.length > 0 || schevalReport.warnings.length > 0) && (
        <div className="border border-gray-200 rounded-lg">
          <button
            onClick={() => setExpandedScheval(!expandedScheval)}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50"
          >
            <div className="flex items-center">
              {expandedScheval ? (
                <ChevronDownIcon className="h-5 w-5 text-gray-400 mr-2" />
              ) : (
                <ChevronRightIcon className="h-5 w-5 text-gray-400 mr-2" />
              )}
              <span className="text-sm font-medium text-gray-900">
                NIEM NDR Violations by File (
                {schevalReport.errors.length + schevalReport.warnings.length})
              </span>
            </div>
          </button>
          {expandedScheval && (
            <div className="px-4 pb-4 space-y-2">
              {Object.entries(schevalIssuesByFile).map(([filename, issues]) => (
                <div key={filename} className="border border-gray-200 rounded">
                  <button
                    onClick={() => toggleFile(`scheval-${filename}`)}
                    className="w-full flex items-center justify-between p-3 hover:bg-gray-50"
                  >
                    <div className="flex items-center">
                      {expandedFiles[`scheval-${filename}`] ? (
                        <ChevronDownIcon className="h-4 w-4 text-gray-400 mr-2" />
                      ) : (
                        <ChevronRightIcon className="h-4 w-4 text-gray-400 mr-2" />
                      )}
                      <span className="text-sm font-medium text-gray-700">{filename}</span>
                      <span className="ml-2 text-xs text-gray-500">
                        ({issues.filter((i) => i.severity === 'error').length} errors,{' '}
                        {
                          issues.filter((i) => i.severity === 'warn' || i.severity === 'warning')
                            .length
                        }{' '}
                        warnings)
                      </span>
                    </div>
                  </button>
                  {expandedFiles[`scheval-${filename}`] && (
                    <div className="px-3 pb-3 space-y-2">
                      {issues.map((issue, idx) => (
                        <div
                          key={`${issue.file}-${issue.line}-${issue.column}-${idx}`}
                          className="text-xs border-l-2 pl-3 py-2"
                          style={{
                            borderLeftColor: issue.severity === 'error' ? '#ef4444' : '#f59e0b',
                          }}
                        >
                          <div className="flex items-start">
                            {issue.severity === 'error' ? (
                              <XCircleIcon className="h-4 w-4 text-red-500 mr-2 mt-0.5 flex-shrink-0" />
                            ) : (
                              <ExclamationTriangleIcon className="h-4 w-4 text-yellow-500 mr-2 mt-0.5 flex-shrink-0" />
                            )}
                            <div className="flex-1">
                              <div className="flex items-center space-x-2">
                                <code className="font-mono text-xs bg-gray-100 px-2 py-0.5 rounded">
                                  {issue.file}:{issue.line}:{issue.column}
                                </code>
                                {issue.rule && (
                                  <span className="font-medium text-blue-700">{issue.rule}</span>
                                )}
                              </div>
                              <div className="text-gray-700 mt-1.5 leading-relaxed">
                                {issue.message}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Import Details */}
      {importReport && importReport.files.length > 0 && (
        <div className="border border-gray-200 rounded-lg">
          <button
            onClick={() => setExpandedImports(!expandedImports)}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50"
          >
            <div className="flex items-center">
              {expandedImports ? (
                <ChevronDownIcon className="h-5 w-5 text-gray-400 mr-2" />
              ) : (
                <ChevronRightIcon className="h-5 w-5 text-gray-400 mr-2" />
              )}
              <span className="text-sm font-medium text-gray-900">
                Import Validation by File ({importReport.total_files})
              </span>
            </div>
          </button>
          {expandedImports && (
            <div className="px-4 pb-4 space-y-2">
              {importReport.files.map((file) => {
                const missingImports = file.imports.filter((i) => i.status === 'missing').length;
                const missingNamespaces = file.namespaces_used.filter(
                  (n) => n.status === 'missing'
                ).length;
                const hasMissing = missingImports > 0 || missingNamespaces > 0;

                return (
                  <div key={file.filename} className="border border-gray-200 rounded">
                    <button
                      onClick={() => toggleFile(`import-${file.filename}`)}
                      className="w-full flex items-center justify-between p-3 hover:bg-gray-50"
                    >
                      <div className="flex items-center flex-1">
                        {expandedFiles[`import-${file.filename}`] ? (
                          <ChevronDownIcon className="h-4 w-4 text-gray-400 mr-2" />
                        ) : (
                          <ChevronRightIcon className="h-4 w-4 text-gray-400 mr-2" />
                        )}
                        {hasMissing ? (
                          <XCircleIcon className="h-4 w-4 text-red-500 mr-2" />
                        ) : (
                          <CheckCircleIcon className="h-4 w-4 text-green-500 mr-2" />
                        )}
                        <span className="text-sm font-medium text-gray-700">{file.filename}</span>
                        <span className="ml-2 text-xs text-gray-500">
                          ({file.imports.length} imports, {file.namespaces_used.length} namespaces)
                        </span>
                      </div>
                    </button>
                    {expandedFiles[`import-${file.filename}`] && (
                      <div className="px-3 pb-3 space-y-3">
                        {file.imports.length > 0 && (
                          <div>
                            <div className="text-xs font-medium text-gray-500 mb-1">Imports:</div>
                            {file.imports.map((imp, idx) => (
                              <div
                                key={`import-${imp.schema_location}-${idx}`}
                                className="flex items-center text-xs py-1"
                              >
                                {imp.status === 'satisfied' ? (
                                  <CheckCircleIcon className="h-3 w-3 text-green-500 mr-2 flex-shrink-0" />
                                ) : (
                                  <XCircleIcon className="h-3 w-3 text-red-500 mr-2 flex-shrink-0" />
                                )}
                                <span className="text-gray-700">{imp.schema_location}</span>
                              </div>
                            ))}
                          </div>
                        )}
                        {file.namespaces_used.length > 0 && (
                          <div>
                            <div className="text-xs font-medium text-gray-500 mb-1">
                              Namespaces:
                            </div>
                            {file.namespaces_used.map((ns, idx) => (
                              <div
                                key={`namespace-${ns.prefix}-${ns.namespace_uri}-${idx}`}
                                className="flex items-center text-xs py-1"
                              >
                                {ns.status === 'satisfied' ? (
                                  <CheckCircleIcon className="h-3 w-3 text-green-500 mr-2 flex-shrink-0" />
                                ) : (
                                  <XCircleIcon className="h-3 w-3 text-red-500 mr-2 flex-shrink-0" />
                                )}
                                <span className="text-gray-700">
                                  {ns.prefix}: {ns.namespace_uri}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
