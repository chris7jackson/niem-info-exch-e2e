import axios, { AxiosInstance } from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const DEV_TOKEN = 'devtoken'; // In production, this would come from environment or auth

export interface Schema {
  schema_id: string;
  filename: string;
  primary_filename?: string;
  json_schema_filename?: string;
  cmf_filename?: string;
  all_filenames?: string[];
  uploaded_at: string;
  active: boolean;
}

export interface ValidationError {
  file: string;
  line?: number;
  column?: number;
  message: string;
  severity: string;
  rule?: string;
  context?: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  summary: string;
}

export interface IngestFileResult {
  filename: string;
  status: string;
  nodes_created?: number;
  relationships_created?: number;
  error?: string;
  validation_details?: ValidationResult;
}

export interface IngestResponse {
  schema_id: string;
  files_processed: number;
  total_nodes_created: number;
  total_relationships_created: number;
  results: IngestFileResult[];
}

// Direct execution returns IngestResponse immediately
export type IngestResult = IngestResponse;

export interface Neo4jStats {
  nodes: number;
  relationships: number;
  indexes: number;
  constraints: number;
}

export interface UploadedFile {
  original_name: string;
  stored_name: string;
  size: number;
  last_modified: string | null;
  content_type: string;
}

export interface ConversionFileResult {
  filename: string;
  status: string;
  json_content?: any;
  json_string?: string;
  schema_id?: string;
  schema_filename?: string;
  error?: string;
  validation_details?: ValidationResult;
}

export interface BatchConversionResult {
  files_processed: number;
  successful: number;
  failed: number;
  results: ConversionFileResult[];
}

// Deprecated: Use BatchConversionResult for new code
export interface ConversionResult {
  success: boolean;
  json_content?: any;
  json_string?: string;
  message?: string;
  schema_id?: string;
  schema_filename?: string;
  source_filename?: string;
  error?: string;
}

export interface HealthResponse {
  status: string;
  timestamp: number;
  uptime: number;
  api_version: string;
  git_commit: string;
  build_date: string;
  niem_version: string;
}

// Entity Resolution Types
export interface NodeTypeInfo {
  qname: string;
  label: string;
  count: number;
  nameFields: string[];
  category?: 'person' | 'organization' | 'location' | 'address' | 'vehicle' | 'other';
  recommended?: boolean;
}

export interface EntityResolutionNodeTypesResponse {
  status: string;
  nodeTypes: NodeTypeInfo[];
  totalTypes: number;
}

export interface EntityResolutionRequest {
  selectedNodeTypes: string[];
}

export interface EntityResolutionResponse {
  status: string;
  message: string;
  entitiesExtracted: number;
  duplicateGroupsFound: number;
  resolvedEntitiesCreated: number;
  relationshipsCreated: number;
  entitiesResolved: number;
  nodeTypesProcessed?: string[];
}

export interface EntityResolutionStatusResponse {
  status: string;
  resolved_entity_clusters: number;
  entities_resolved: number;
  is_active: boolean;
}

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_URL,
      headers: {
        'Authorization': `Bearer ${DEV_TOKEN}`,
      },
    });
  }

  // Schema Management
  async uploadSchema(files: File[], filePaths: string[], skipNiemNdr: boolean = false): Promise<any> {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    // Send file paths as JSON array
    formData.append('file_paths', JSON.stringify(filePaths));
    formData.append('skip_niem_ndr', skipNiemNdr.toString());

    const response = await this.client.post('/api/schema/xsd', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async getSchemas(): Promise<Schema[]> {
    const response = await this.client.get('/api/schema');
    return response.data;
  }

  async activateSchema(schemaId: string): Promise<any> {
    const response = await this.client.post(`/api/schema/activate/${schemaId}`);
    return response.data;
  }

  async downloadSchemaFile(schemaId: string, fileType: 'cmf' | 'json'): Promise<Blob> {
    const response = await this.client.get(`/api/schema/${schemaId}/file/${fileType}`, {
      responseType: 'blob'
    });
    return response.data;
  }

  // Data Ingestion - Direct to Neo4j
  async ingestXml(files: File[]): Promise<IngestResult> {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    const response = await this.client.post('/api/ingest/xml', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async ingestJson(files: File[]): Promise<IngestResult> {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    const response = await this.client.post('/api/ingest/json', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  // Format Conversion
  async convertXmlToJson(
    files: File | File[],
    schemaId?: string,
    contextUri?: string
  ): Promise<BatchConversionResult> {
    const formData = new FormData();

    // Handle both single file and array of files
    const fileArray = Array.isArray(files) ? files : [files];
    fileArray.forEach(file => {
      formData.append('files', file);
    });

    if (schemaId) {
      formData.append('schema_id', schemaId);
    }
    if (contextUri) {
      formData.append('context_uri', contextUri);
    }

    const response = await this.client.post('/api/convert/xml-to-json', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  // Neo4j Administration
  async getNeo4jStats(): Promise<Neo4jStats> {
    const response = await this.client.get('/api/admin/neo4j/stats');
    return response.data.stats;
  }

  // System Reset
  async resetSystem(options: {
    schemas?: boolean;
    data?: boolean;
    neo4j?: boolean;
    dry_run?: boolean;
    confirm_token?: string;
  }): Promise<any> {
    const response = await this.client.post('/api/admin/reset', options);
    return response.data;
  }

  // Get uploaded files
  async getUploadedFiles(): Promise<UploadedFile[]> {
    const response = await this.client.get('/api/ingest/files');
    return response.data.files;
  }

  // Health check and version info
  async getHealth(): Promise<HealthResponse> {
    const response = await this.client.get('/healthz');
    return response.data;
  }

  // Entity Resolution
  async getEntityResolutionNodeTypes(): Promise<EntityResolutionNodeTypesResponse> {
    const response = await this.client.get('/api/entity-resolution/node-types');
    return response.data;
  }

  async runEntityResolution(selectedNodeTypes?: string[]): Promise<EntityResolutionResponse> {
    const request: EntityResolutionRequest | undefined = selectedNodeTypes
      ? { selectedNodeTypes }
      : undefined;

    const response = await this.client.post('/api/entity-resolution/run', request);
    return response.data;
  }

  async getEntityResolutionStatus(): Promise<EntityResolutionStatusResponse> {
    const response = await this.client.get('/api/entity-resolution/status');
    return response.data;
  }

  async resetEntityResolution(): Promise<any> {
    const response = await this.client.delete('/api/entity-resolution/reset');
    return response.data;
  }
}

export const apiClient = new ApiClient();
export default apiClient;