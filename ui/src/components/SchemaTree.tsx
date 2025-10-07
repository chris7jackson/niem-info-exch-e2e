import { useState } from 'react';
import { ChevronRightIcon, ChevronDownIcon } from '@heroicons/react/24/outline';

interface SchemaTreeProps {
  structure: {
    schema_id: string;
    primary_filename: string;
    files: FileStructure[];
  };
}

interface FileStructure {
  file_name: string;
  target_namespace: string;
  elements: ElementInfo[];
  complex_types: ComplexTypeInfo[];
  simple_types: SimpleTypeInfo[];
}

interface ElementInfo {
  name: string;
  type: string;
  documentation?: string;
  min_occurs: string;
  max_occurs: string;
  abstract: boolean;
  substitution_group?: string;
  children?: any[];
  inline_type?: any;
}

interface ComplexTypeInfo {
  name: string;
  documentation?: string;
  abstract: boolean;
  base_type?: string;
  attributes: AttributeInfo[];
  elements: ElementInfo[];
}

interface SimpleTypeInfo {
  name: string;
  documentation?: string;
  base_type?: string;
  restrictions: RestrictionInfo[];
}

interface AttributeInfo {
  name: string;
  type: string;
  use: string;
  documentation?: string;
}

interface RestrictionInfo {
  type: string;
  value: string;
}

export default function SchemaTree({ structure }: SchemaTreeProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());
  const [expandedElements, setExpandedElements] = useState<Set<string>>(new Set());
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set());
  const [expandAll, setExpandAll] = useState(false);

  const toggleFile = (fileName: string) => {
    const newExpanded = new Set(expandedFiles);
    if (newExpanded.has(fileName)) {
      newExpanded.delete(fileName);
    } else {
      newExpanded.add(fileName);
    }
    setExpandedFiles(newExpanded);
  };

  const toggleElement = (id: string) => {
    const newExpanded = new Set(expandedElements);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedElements(newExpanded);
  };

  const toggleType = (id: string) => {
    const newExpanded = new Set(expandedTypes);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedTypes(newExpanded);
  };

  const handleExpandAll = () => {
    if (expandAll) {
      // Collapse all
      setExpandedFiles(new Set());
      setExpandedElements(new Set());
      setExpandedTypes(new Set());
      setExpandAll(false);
    } else {
      // Expand all
      const allFiles = new Set(structure.files.map(f => f.file_name));
      const allElements = new Set<string>();
      const allTypes = new Set<string>();

      structure.files.forEach((file, fileIdx) => {
        file.elements.forEach((el, elIdx) => {
          allElements.add(`${fileIdx}-el-${elIdx}`);
        });
        file.complex_types.forEach((ct, ctIdx) => {
          allTypes.add(`${fileIdx}-ct-${ctIdx}`);
        });
        file.simple_types.forEach((st, stIdx) => {
          allTypes.add(`${fileIdx}-st-${stIdx}`);
        });
      });

      setExpandedFiles(allFiles);
      setExpandedElements(allElements);
      setExpandedTypes(allTypes);
      setExpandAll(true);
    }
  };

  const matchesSearch = (text: string): boolean => {
    if (!searchQuery) return true;
    return text.toLowerCase().includes(searchQuery.toLowerCase());
  };

  const filterFile = (file: FileStructure): boolean => {
    if (!searchQuery) return true;

    // Check file name
    if (matchesSearch(file.file_name)) return true;

    // Check elements
    if (file.elements.some(el => matchesSearch(el.name) || (el.type && matchesSearch(el.type)))) {
      return true;
    }

    // Check complex types
    if (file.complex_types.some(ct => matchesSearch(ct.name))) {
      return true;
    }

    // Check simple types
    if (file.simple_types.some(st => matchesSearch(st.name))) {
      return true;
    }

    return false;
  };

  const renderAttribute = (attr: AttributeInfo, idx: number) => (
    <div key={idx} className="ml-6 py-1 text-sm">
      <span className="text-purple-600">@{attr.name}</span>
      <span className="text-gray-500 ml-2">: {attr.type}</span>
      {attr.use !== 'optional' && (
        <span className="ml-2 text-xs bg-red-100 text-red-800 px-1 rounded">{attr.use}</span>
      )}
      {attr.documentation && (
        <div className="ml-2 text-xs text-gray-600 italic">{attr.documentation}</div>
      )}
    </div>
  );

  const renderElement = (element: ElementInfo, idx: number, fileIdx: number, parentId?: string) => {
    const elementId = parentId ? `${parentId}-${idx}` : `${fileIdx}-el-${idx}`;
    const isExpanded = expandedElements.has(elementId);
    const hasChildren = element.children && element.children.length > 0;
    const hasInlineType = element.inline_type && (
      (element.inline_type.elements && element.inline_type.elements.length > 0) ||
      (element.inline_type.attributes && element.inline_type.attributes.length > 0)
    );
    const isExpandable = hasChildren || hasInlineType;

    // Filter by search
    if (searchQuery && !matchesSearch(element.name) && !matchesSearch(element.type || '')) {
      return null;
    }

    return (
      <div key={elementId} className="ml-4">
        <div className="flex items-start py-1 hover:bg-gray-50 rounded">
          {isExpandable ? (
            <button
              onClick={() => toggleElement(elementId)}
              className="flex-shrink-0 mr-1 text-gray-400 hover:text-gray-600"
            >
              {isExpanded ? (
                <ChevronDownIcon className="h-4 w-4" />
              ) : (
                <ChevronRightIcon className="h-4 w-4" />
              )}
            </button>
          ) : (
            <span className="flex-shrink-0 mr-1 w-4" />
          )}

          <div className="flex-1 min-w-0">
            <div className="flex items-center flex-wrap gap-2">
              <span className="text-blue-600 font-medium">{element.name}</span>
              {element.type && (
                <span className="text-gray-500 text-sm">: {element.type}</span>
              )}
              {element.abstract && (
                <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded">abstract</span>
              )}
              {element.max_occurs !== '1' && (
                <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">
                  [{element.min_occurs}..{element.max_occurs === 'unbounded' ? '∞' : element.max_occurs}]
                </span>
              )}
              {element.substitution_group && (
                <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded">
                  ↔ {element.substitution_group}
                </span>
              )}
            </div>

            {element.documentation && (
              <div className="mt-1 text-xs text-gray-600 italic">{element.documentation}</div>
            )}

            {isExpanded && element.inline_type && (
              <div className="mt-2 ml-4 border-l-2 border-gray-200 pl-2">
                <div className="text-xs text-gray-500 font-semibold mb-1">Inline Type</div>
                {element.inline_type.base_type && (
                  <div className="text-sm text-gray-600 mb-1">
                    extends: <span className="text-indigo-600">{element.inline_type.base_type}</span>
                  </div>
                )}
                {element.inline_type.attributes?.map((attr: AttributeInfo, i: number) => renderAttribute(attr, i))}
                {element.inline_type.elements?.map((el: ElementInfo, i: number) =>
                  renderElement(el, i, fileIdx, elementId)
                )}
              </div>
            )}

            {isExpanded && hasChildren && (
              <div className="mt-2 ml-4 border-l-2 border-gray-200 pl-2">
                {element.children.map((child: ElementInfo, i: number) => renderElement(child, i, fileIdx, elementId))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderComplexType = (complexType: ComplexTypeInfo, idx: number, fileIdx: number) => {
    const typeId = `${fileIdx}-ct-${idx}`;
    const isExpanded = expandedTypes.has(typeId);
    const hasContent = (complexType.elements && complexType.elements.length > 0) ||
                      (complexType.attributes && complexType.attributes.length > 0);

    // Filter by search
    if (searchQuery && !matchesSearch(complexType.name)) {
      return null;
    }

    return (
      <div key={typeId} className="ml-4">
        <div className="flex items-start py-1 hover:bg-gray-50 rounded">
          {hasContent ? (
            <button
              onClick={() => toggleType(typeId)}
              className="flex-shrink-0 mr-1 text-gray-400 hover:text-gray-600"
            >
              {isExpanded ? (
                <ChevronDownIcon className="h-4 w-4" />
              ) : (
                <ChevronRightIcon className="h-4 w-4" />
              )}
            </button>
          ) : (
            <span className="flex-shrink-0 mr-1 w-4" />
          )}

          <div className="flex-1 min-w-0">
            <div className="flex items-center flex-wrap gap-2">
              <span className="text-indigo-600 font-medium">{complexType.name}</span>
              <span className="text-xs bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded">complexType</span>
              {complexType.abstract && (
                <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded">abstract</span>
              )}
              {complexType.base_type && (
                <span className="text-xs text-gray-600">extends: {complexType.base_type}</span>
              )}
            </div>

            {complexType.documentation && (
              <div className="mt-1 text-xs text-gray-600 italic">{complexType.documentation}</div>
            )}

            {isExpanded && (
              <div className="mt-2 ml-4 border-l-2 border-gray-200 pl-2">
                {complexType.attributes?.length > 0 && (
                  <div className="mb-2">
                    <div className="text-xs text-gray-500 font-semibold mb-1">Attributes</div>
                    {complexType.attributes.map((attr, i) => renderAttribute(attr, i))}
                  </div>
                )}
                {complexType.elements?.length > 0 && (
                  <div>
                    <div className="text-xs text-gray-500 font-semibold mb-1">Elements</div>
                    {complexType.elements.map((el, i) => renderElement(el, i, fileIdx, typeId))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderSimpleType = (simpleType: SimpleTypeInfo, idx: number, fileIdx: number) => {
    const typeId = `${fileIdx}-st-${idx}`;
    const isExpanded = expandedTypes.has(typeId);
    const hasRestrictions = simpleType.restrictions && simpleType.restrictions.length > 0;

    // Filter by search
    if (searchQuery && !matchesSearch(simpleType.name)) {
      return null;
    }

    return (
      <div key={typeId} className="ml-4">
        <div className="flex items-start py-1 hover:bg-gray-50 rounded">
          {hasRestrictions ? (
            <button
              onClick={() => toggleType(typeId)}
              className="flex-shrink-0 mr-1 text-gray-400 hover:text-gray-600"
            >
              {isExpanded ? (
                <ChevronDownIcon className="h-4 w-4" />
              ) : (
                <ChevronRightIcon className="h-4 w-4" />
              )}
            </button>
          ) : (
            <span className="flex-shrink-0 mr-1 w-4" />
          )}

          <div className="flex-1 min-w-0">
            <div className="flex items-center flex-wrap gap-2">
              <span className="text-green-600 font-medium">{simpleType.name}</span>
              <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded">simpleType</span>
              {simpleType.base_type && (
                <span className="text-xs text-gray-600">: {simpleType.base_type}</span>
              )}
            </div>

            {simpleType.documentation && (
              <div className="mt-1 text-xs text-gray-600 italic">{simpleType.documentation}</div>
            )}

            {isExpanded && hasRestrictions && (
              <div className="mt-2 ml-4 border-l-2 border-gray-200 pl-2">
                <div className="text-xs text-gray-500 font-semibold mb-1">Restrictions</div>
                {simpleType.restrictions.map((restriction, i) => (
                  <div key={i} className="ml-2 py-1 text-sm">
                    <span className="text-gray-600">{restriction.type}:</span>
                    <span className="ml-2 text-gray-800">{restriction.value}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderFile = (file: FileStructure, fileIdx: number) => {
    const isExpanded = expandedFiles.has(file.file_name);
    const filtered = filterFile(file);

    if (!filtered) return null;

    return (
      <div key={file.file_name} className="mb-4 border border-gray-200 rounded-lg overflow-hidden">
        <button
          onClick={() => toggleFile(file.file_name)}
          className="w-full bg-gray-100 hover:bg-gray-200 px-4 py-3 flex items-center justify-between"
        >
          <div className="flex items-center">
            {isExpanded ? (
              <ChevronDownIcon className="h-5 w-5 mr-2 text-gray-600" />
            ) : (
              <ChevronRightIcon className="h-5 w-5 mr-2 text-gray-600" />
            )}
            <div className="text-left">
              <div className="font-semibold text-gray-900">{file.file_name}</div>
              <div className="text-xs text-gray-500 mt-1">{file.target_namespace}</div>
            </div>
          </div>
          <div className="flex gap-3 text-xs text-gray-600">
            <span>{file.elements.length} elements</span>
            <span>{file.complex_types.length} complex types</span>
            <span>{file.simple_types.length} simple types</span>
          </div>
        </button>

        {isExpanded && (
          <div className="bg-white p-4">
            {/* Elements Section */}
            {file.elements.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-semibold text-gray-700 mb-2 border-b pb-1">
                  Elements ({file.elements.length})
                </h3>
                {file.elements.map((el, idx) => renderElement(el, idx, fileIdx))}
              </div>
            )}

            {/* Complex Types Section */}
            {file.complex_types.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-semibold text-gray-700 mb-2 border-b pb-1">
                  Complex Types ({file.complex_types.length})
                </h3>
                {file.complex_types.map((ct, idx) => renderComplexType(ct, idx, fileIdx))}
              </div>
            )}

            {/* Simple Types Section */}
            {file.simple_types.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-2 border-b pb-1">
                  Simple Types ({file.simple_types.length})
                </h3>
                {file.simple_types.map((st, idx) => renderSimpleType(st, idx, fileIdx))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div>
      {/* Search and Controls */}
      <div className="mb-4 flex gap-4">
        <div className="flex-1">
          <input
            type="text"
            placeholder="Search elements, types..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <button
          onClick={handleExpandAll}
          className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md font-medium"
        >
          {expandAll ? 'Collapse All' : 'Expand All'}
        </button>
      </div>

      {/* Schema Info */}
      <div className="mb-4 p-3 bg-indigo-50 rounded-lg">
        <div className="text-sm text-indigo-900">
          <span className="font-semibold">Schema ID:</span> {structure.schema_id}
        </div>
        <div className="text-sm text-indigo-900 mt-1">
          <span className="font-semibold">Primary File:</span> {structure.primary_filename}
        </div>
        <div className="text-sm text-indigo-900 mt-1">
          <span className="font-semibold">Total Files:</span> {structure.files.length}
        </div>
      </div>

      {/* File Tree */}
      <div>
        {structure.files.map((file, idx) => renderFile(file, idx))}
      </div>

      {searchQuery && structure.files.every(f => !filterFile(f)) && (
        <div className="text-center py-8 text-gray-500">
          No results found for "{searchQuery}"
        </div>
      )}
    </div>
  );
}
