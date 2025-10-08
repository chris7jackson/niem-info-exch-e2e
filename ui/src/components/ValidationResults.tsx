import { useState } from 'react';
import { ChevronDownIcon, ChevronRightIcon, CheckCircleIcon, ExclamationTriangleIcon, XCircleIcon } from '@heroicons/react/24/outline';

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

interface NiemNdrViolation {
  type: string;
  rule: string;
  message: string;
  location: string;
  file?: string;
}

interface NiemNdrReport {
  status: string;
  message: string;
  conformance_target: string;
  violations: NiemNdrViolation[];
  summary: { [key: string]: number };
}

interface ValidationResultsProps {
  readonly ndrReport?: NiemNdrReport;
  readonly importReport?: ImportValidationReport;
}

export default function ValidationResults({ ndrReport, importReport }: ValidationResultsProps) {
  const [expandedNdr, setExpandedNdr] = useState(false);
  const [expandedImports, setExpandedImports] = useState(false);
  const [expandedFiles, setExpandedFiles] = useState<{ [key: string]: boolean }>({});

  if (!ndrReport && !importReport) {
    return null;
  }

  const toggleFile = (filename: string) => {
    setExpandedFiles(prev => ({ ...prev, [filename]: !prev[filename] }));
  };

  // Group NDR violations by file
  const violationsByFile: { [key: string]: NiemNdrViolation[] } = {};
  if (ndrReport) {
    ndrReport.violations.forEach(v => {
      const file = v.file || 'unknown';
      if (!violationsByFile[file]) {
        violationsByFile[file] = [];
      }
      violationsByFile[file].push(v);
    });
  }

  const ndrStatus = ndrReport?.status || 'unknown';
  const importStatus = importReport?.status || 'unknown';
  const overallSuccess = ndrStatus === 'pass' && importStatus === 'pass';

  // Debug logging
  console.log('ValidationResults - ndrReport:', ndrReport);
  console.log('ValidationResults - importReport:', importReport);
  console.log('ValidationResults - importStatus:', importStatus);
  console.log('ValidationResults - importReport?.status:', importReport?.status);

  return (
    <div className="bg-white shadow rounded-lg p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-gray-900">Validation Results</h3>
        {overallSuccess && (
          <CheckCircleIcon className="h-6 w-6 text-green-500" />
        )}
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm font-medium text-gray-500">NIEM NDR Validation</div>
          <div className="mt-2 flex items-center">
            {(() => {
              if (ndrStatus === 'pass') {
                return (
                  <>
                    <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                    <span className="text-sm text-green-700">Passed</span>
                  </>
                );
              }
              if (ndrStatus === 'fail') {
                return (
                  <>
                    <XCircleIcon className="h-5 w-5 text-red-500 mr-2" />
                    <span className="text-sm text-red-700">{ndrReport?.summary.error_count || 0} errors</span>
                  </>
                );
              }
              return <span className="text-sm text-gray-500">Unknown</span>;
            })()}
          </div>
          {ndrReport && ndrReport.summary.warning_count > 0 && (
            <div className="mt-1 text-xs text-yellow-600">
              {ndrReport.summary.warning_count} warnings
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
                    <span className="text-sm text-red-700">{importReport.missing_count || 0} missing</span>
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

      {/* NDR Details */}
      {ndrReport && ndrReport.violations.length > 0 && (
        <div className="border border-gray-200 rounded-lg">
          <button
            onClick={() => setExpandedNdr(!expandedNdr)}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50"
          >
            <div className="flex items-center">
              {expandedNdr ? (
                <ChevronDownIcon className="h-5 w-5 text-gray-400 mr-2" />
              ) : (
                <ChevronRightIcon className="h-5 w-5 text-gray-400 mr-2" />
              )}
              <span className="text-sm font-medium text-gray-900">
                NIEM NDR Violations by File ({ndrReport.violations.length})
              </span>
            </div>
          </button>
          {expandedNdr && (
            <div className="px-4 pb-4 space-y-2">
              {Object.entries(violationsByFile).map(([filename, violations]) => (
                <div key={filename} className="border border-gray-200 rounded">
                  <button
                    onClick={() => toggleFile(`ndr-${filename}`)}
                    className="w-full flex items-center justify-between p-3 hover:bg-gray-50"
                  >
                    <div className="flex items-center">
                      {expandedFiles[`ndr-${filename}`] ? (
                        <ChevronDownIcon className="h-4 w-4 text-gray-400 mr-2" />
                      ) : (
                        <ChevronRightIcon className="h-4 w-4 text-gray-400 mr-2" />
                      )}
                      <span className="text-sm font-medium text-gray-700">{filename}</span>
                      <span className="ml-2 text-xs text-gray-500">
                        ({violations.filter(v => v.type === 'error').length} errors,{' '}
                        {violations.filter(v => v.type === 'warning').length} warnings)
                      </span>
                    </div>
                  </button>
                  {expandedFiles[`ndr-${filename}`] && (
                    <div className="px-3 pb-3 space-y-2">
                      {violations.map((v, idx) => (
                        <div key={`${v.rule}-${v.location}-${idx}`} className="text-xs">
                          <div className="flex items-start">
                            {v.type === 'error' ? (
                              <XCircleIcon className="h-4 w-4 text-red-500 mr-2 mt-0.5 flex-shrink-0" />
                            ) : (
                              <ExclamationTriangleIcon className="h-4 w-4 text-yellow-500 mr-2 mt-0.5 flex-shrink-0" />
                            )}
                            <div className="flex-1">
                              <div className="font-medium text-gray-900">{v.rule}</div>
                              <div className="text-gray-600 mt-1">{v.message}</div>
                              <div className="text-gray-400 mt-1">{v.location}</div>
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
                const missingImports = file.imports.filter(i => i.status === 'missing').length;
                const missingNamespaces = file.namespaces_used.filter(n => n.status === 'missing').length;
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
                              <div key={`import-${imp.schema_location}-${idx}`} className="flex items-center text-xs py-1">
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
                            <div className="text-xs font-medium text-gray-500 mb-1">Namespaces:</div>
                            {file.namespaces_used.map((ns, idx) => (
                              <div key={`namespace-${ns.prefix}-${ns.namespace_uri}-${idx}`} className="flex items-center text-xs py-1">
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
